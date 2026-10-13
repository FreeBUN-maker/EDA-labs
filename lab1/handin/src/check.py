#!/usr/bin/env python3
"""HW1 P3 submission checker.

    python3 check.py --aag fixtures/subj_alu4.aag \
        --lib fixtures/lib.json \
        --golden fixtures/subj_alu4_golden.json \
        --net mapped.blif [--report report.json]

Checks, in order:
  format   mapped.blif is well-formed .gate BLIF: one model, .inputs and
           .outputs exactly the subject's ports, every instance a known
           library gate with all of its pins bound, every net driven once,
           every output driven, combinational (topologically sortable),
           no undriven or dangling logic.
  function the netlist is simulated against the subject's golden vectors
           (exhaustive for <=16 inputs, else the shipped sampled set);
           every output bit must match.
  area     total area = sum of gate areas, must not exceed the subject's
           threshold (table below, printed as "area (threshold)").

With --report, additionally cross-checks that report.json agrees with the
netlist actually submitted.

This is the student-facing format/function checker; the grading checker
verifies exact functional equivalence.
"""

import argparse
import json
import sys

THRESHOLDS = {          # per-subject acceptance bound on total area
                        # (reference cover's area + 3% margin)
    "subj_p2func": 0.2704,
    "subj_alu4":   4.4902,
    "subj_sbox":   52.3207,
    "subj_riscv":  122.5420,
}
EPS = 1e-4


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


# ------------------------------------------------------------- blif parse

def parse_blif(path):
    ins, outs, gates = [], [], []
    model = None
    for raw in open(path):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("."):
            tok = line.split(None, 1)
            cmd, rest = tok[0], tok[1] if len(tok) > 1 else ""
            if cmd == ".model":
                model = rest.split()[0]
            elif cmd == ".inputs":
                ins.extend(rest.split())
            elif cmd == ".outputs":
                outs.extend(rest.split())
            elif cmd == ".gate":
                parts = rest.split()
                gname, pins = parts[0], {}
                for kv in parts[1:]:
                    if "=" not in kv:
                        fail(f"{path}: malformed .gate line {line!r}")
                    k, v = kv.split("=", 1)
                    if k in pins:
                        fail(f"{path}: pin {k} bound twice in {line!r}")
                    pins[k] = v
                gates.append((gname, pins))
            elif cmd == ".end":
                break
            else:
                fail(f"{path}: unsupported directive {cmd}")
    if model is None:
        fail(f"{path}: missing .model")
    return model, ins, outs, gates


# ------------------------------------------------------- library helpers

def eval_pattern(node, env):
    """Value of a pattern tree under pin->bit env."""
    if "leaf" in node:
        return env[node["leaf"]]
    v0 = eval_edge(node["and"][0], env)
    v1 = eval_edge(node["and"][1], env)
    return v0 & v1


def eval_edge(e, env):
    v = eval_pattern(e["node"], env)
    return v ^ (1 if e["inv"] else 0)


def gate_eval(g, env):
    return eval_pattern(g["pattern"], env) ^ (1 if g["out_inv"] else 0)


# ----------------------------------------------------------------- check

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aag", required=True)
    ap.add_argument("--lib", required=True)
    ap.add_argument("--golden", required=True)
    ap.add_argument("--net", required=True)
    ap.add_argument("--report")
    args = ap.parse_args()

    lib = {g["name"]: g for g in json.load(open(args.lib))["gates"]}
    golden = json.load(open(args.golden))
    subject = golden["subject"]
    import os
    if os.path.splitext(os.path.basename(args.aag))[0] != subject:
        fail(f"--aag {args.aag} does not name subject {subject}")
    model, ins, outs, gates = parse_blif(args.net)

    # ---- interface: ports must match the subject exactly
    want_in = golden["inputs"]
    want_out = golden["outputs"]
    if ins != want_in:
        fail(f"inputs differ: got {ins}, subject declares {want_in}")
    if outs != want_out:
        fail(f"outputs differ: got {outs}, subject declares {want_out}")

    # ---- structural checks + topological order
    drivers = {}
    inet = set(ins)
    for gname, pins in gates:
        if gname not in lib:
            fail(f"unknown gate {gname}")
        g = lib[gname]
        want = set(g["pins"]) | {"O"}
        if set(pins) != want:
            fail(f"{gname}: pins {sorted(pins)} != {sorted(want)}")
        if pins["O"] in drivers or pins["O"] in inet:
            fail(f"net {pins['O']} multiply driven")
        drivers[pins["O"]] = (gname, pins)
    for o in outs:
        if o not in drivers and o not in inet:
            fail(f"output {o} is not driven")
    used = set()
    for _g, pins in gates:
        for pin, net in pins.items():
            if pin != "O":
                used.add(net)
    for net in used:
        if net not in drivers and net not in inet:
            fail(f"pin driven by undriven net {net}")
    for o in outs:
        used.add(o)
    for net in drivers:
        if net not in used:
            fail(f"gate output {net} is dangling")

    sys.setrecursionlimit(1_000_000)
    state, order = {}, []           # 1 = on stack, 2 = done
    def visit(n):
        if n in inet:
            return
        st = state.get(n)
        if st == 2:
            return
        if st == 1:
            fail(f"combinational loop through net {n}")
        state[n] = 1
        gname, pins = drivers[n]
        for p in lib[gname]["pins"]:
            visit(pins[p])
        state[n] = 2
        order.append(n)
    for o in outs:
        visit(o)

    # ---- simulate on golden vectors
    def sim(case_hex):
        n_in = len(want_in)
        bits = [(int(case_hex, 16) >> (n_in - 1 - k)) & 1
                for k in range(n_in)]
        env = dict(zip(want_in, bits))
        for net in order:
            gname, pins = drivers[net]
            pen = {p: env[pins[p]] for p in lib[gname]["pins"]}
            env[net] = gate_eval(lib[gname], pen)
        return [env[o] for o in want_out]

    bad = 0
    for cin, cout in golden["cases"]:
        got = sim(cin)
        want = [(int(cout, 16) >> (len(want_out) - 1 - k)) & 1
                for k in range(len(want_out))]
        if got != want:
            bad += 1
            if bad <= 3:
                print(f"  mismatch on input {cin}: "
                      f"got {bits_str(got)} want {bits_str(want)}")
    if bad:
        fail(f"functionality: {bad}/{len(golden['cases'])} vectors differ")

    # ---- area
    area = sum(lib[g]["area"] for g, _ in gates)
    counts = {}
    for g, _ in gates:
        counts[g] = counts.get(g, 0) + 1

    if args.report:
        rep = json.load(open(args.report))
        if abs(rep.get("area", -1) - area) > EPS:
            fail(f"report.json area {rep.get('area')} != "
                 f"netlist area {area:.5f}")
        if rep.get("cells") != len(gates):
            fail("report.json cell count does not match netlist")

    thr = THRESHOLDS.get(subject)
    print(f"{subject}: {len(gates)} cells, area {area:.5f} "
          f"(threshold {thr})")
    for n, c in sorted(counts.items()):
        print(f"  {n:6s} x{c}")
    if thr is None:
        print("note: no threshold recorded for this subject")
    elif area > thr + EPS:
        fail(f"area {area:.5f} exceeds threshold {thr}")
    print("PASS")


def bits_str(bits):
    return "".join(str(b) for b in bits)


if __name__ == "__main__":
    main()
