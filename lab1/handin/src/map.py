#!/usr/bin/env python3
"""HW1 P3: technology mapping by tree covering.

    python3 map.py <subject.aag> <lib.json> -o mapped.blif -r report.json

The pipeline is already wired in main():

    load subject graph (aig.py, shipped)
      -> load library (lib.json)
      -> enumerate pattern-tree matches at every AIG node
      -> dual-polarity dynamic-programming cover
      -> emit the mapped netlist

Contractual artifacts:

    mapped.blif   .gate netlist: ".model/.inputs/.outputs" lines carry the
                  subject's port names verbatim; every gate instance is a
                  line  ".gate <gname> <pin>=<net> ... O=<net>"  binding
                  each library pin to a net; the output pin is named O.
    report.json   {"area": <float>, "cells": <int>,
                   "gates": {<gname>: <count>, ...}}

The functions below document the matching, covering, and output contracts.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aig import load, lit_var, lit_inv, lit   # shipped .aag reader


# ---------------------------------------------------------------- library

def load_lib(path):
    """Return the gate list from lib.json.  Each gate record:

        name      gate type, also the .gate keyword in mapped.blif
        area      gate cost (total mapped area = sum over instances)
        pins      pin names in lib order, e.g. ["a", "b", "c"]
        out_inv   True iff the gate output is the *complement* of its
                  pattern's root AND subtree (nand2, aoi21, xor2, ...)
        pattern   pattern tree: {"and": [edge, edge]} for a 2-input AND
                  node or {"leaf": <pin>} for a leaf; each edge is
                  {"inv": bool, "node": <pattern node>}
    """
    return json.loads(open(path).read())["gates"]


# ------------------------------------------------------------- matching

def matches_at(gate, var, subj):
    """Enumerate every match of `gate`'s pattern tree rooted at the AIG
    node `var` (which is a key of subj.ands).

    A match aligns the pattern's root AND node with `var`; for every
    pattern edge {"inv": e, "node": c} against a subject child literal
    (u, s) = (l >> 1, l & 1):

      * if c is an internal AND node: the edge polarity must be exact,
        i.e. s == e, and u must itself be an AND node; matching continues
        recursively inside u;
      * if c is a leaf labelled pin p: the pin binds the subject literal
        *before* the pattern's internal inverter, i.e. literal
        (u, s ^ e); every occurrence of pin p must bind the same literal.

    Patterns nest several AND levels and may repeat a pin on several
    leaves under differently inverted edges (e.g. xor2 is
    ~((a~b)(~ab))).  Each AND node's two children are unordered: try
    both assignments.

    Yield one dict per distinct match: {pin_name: subject_literal}.
    Gates whose pattern is a bare {"leaf": ...} (inv1) match any node and
    are handled in cover(), not here.
    """
    if "leaf" in gate["pattern"]:
        return

    def match_edge(edge, subject_lit, binds):
        node = edge["node"]
        if "leaf" in node:
            pin = node["leaf"]
            # Undo the inverter inside the pattern to obtain the pin's net.
            bound = subject_lit ^ int(edge["inv"])
            if pin in binds:
                if binds[pin] == bound:
                    yield binds
            else:
                yield {**binds, pin: bound}
        elif lit_inv(subject_lit) == int(edge["inv"]):
            yield from match_node(node, lit_var(subject_lit), binds)

    def match_node(node, subject_var, binds):
        if subject_var not in subj.ands:
            return
        left, right = node["and"]
        a, b = subj.ands[subject_var]
        # Keep the AAG child order first for deterministic tie breaking.
        for first, second in ((a, b), (b, a)):
            for partial in match_edge(left, first, binds):
                yield from match_edge(right, second, partial)

    seen = set()
    for binds in match_node(gate["pattern"], var, {}):
        key = tuple(binds[pin] for pin in gate["pins"])
        if key not in seen:
            seen.add(key)
            yield binds


# ------------------------------------------------------------- covering

def cover(subj, gates):
    """Dual-polarity minimum-area cover.

    For every AIG variable v compute cost[v] = [C0, C1] where C_p is the
    minimum total area of a cover producing literal (v, p) -- v when
    p == 0, its complement when p == 1:

        C_p(v) = min over gates g and matches m of g at v with
                     g.out_inv == p of
                     area(g) + sum over the *distinct* leaf literals l
                                  bound by m of C_{l&1}(l >> 1)
                 and, additionally, the inverter route
                     C_p(v) <= area(inv1) + C_{1-p}(v).

    Primary inputs: C_0(pi) = 0, C_1(pi) = area(inv1).
    Ties are broken deterministically: gates in lib order, children in
    aag order, keep the first minimum.

    Return (cost, choice) where choice[v][p] describes the selected way
    to produce literal (v, p), as consumed by the shipped emit() below:

        ("inv",)                     -- produce it with an inv1 whose
                                      input is the net of (v, 1-p)
        ("gate", binds, lits, gate)  -- a gate instance: `binds` is the
                                      pin -> subject-literal map of the
                                      winning match, `lits` the list of
                                      distinct leaf literals it
                                      requires, `gate` the gate record.
    """
    inv_area = next(g["area"] for g in gates if g["name"] == "inv1")
    pattern_gates = [g for g in gates if "and" in g["pattern"]]
    cost, choice = {}, {}
    for input_lit, _ in subj.inputs:
        v = lit_var(input_lit)
        cost[v] = [0.0, inv_area]
        choice[v] = [None, ("inv",)]

    for v in subj.order:
        direct = [float("inf"), float("inf")]
        selected = [None, None]
        for gate in pattern_gates:
            p = int(gate["out_inv"])
            for binds in matches_at(gate, v, subj):
                # Different pins can consume the same literal; pay only once.
                # Dict insertion order preserves the match's leaf order.
                lits = list(dict.fromkeys(binds.values()))
                area = gate["area"] + sum(
                    cost[lit_var(l)][lit_inv(l)] for l in lits)
                if area < direct[p]:
                    direct[p] = area
                    selected[p] = ("gate", binds, lits, gate)

        cost[v] = direct.copy()
        choice[v] = selected
        # Both routes use the original direct costs, not a just-relaxed cost.
        # With positive inverter area this cannot create an inverter cycle.
        for p in (0, 1):
            inverted = inv_area + direct[1 - p]
            if inverted < cost[v][p]:
                cost[v][p] = inverted
                choice[v][p] = ("inv",)
        if all(ch is None for ch in choice[v]):
            raise ValueError(f"no library cover for AIG node {v}")

    return cost, choice


# ------------------------------------------------------------------ emit

def emit(subj, gates, choice, out_path, report_path):
    """Emit the chosen cover as mapped.blif and report.json.

    Walks the required output literals (subj.outputs) depth-first,
    producing each required literal once: one net, one driving gate
    instance.  If the complementary net already exists when a literal is
    required, a single inv1 on it is cheaper than a fresh cover, so the
    inverter is emitted instead.

    Net naming (deterministic): a positive literal (v, 0) whose v is a
    primary input carries the input's port name; a primary-output
    literal carries the output's port name; other nets are "n<v>"
    (positive) / "nb<v>" (complemented).  Intermediate nets may carry
    any name not colliding with these.

    report.json: {"area": total gate area, "cells": gate count,
                  "gates": {name: count}}.
    """
    by_name = {g["name"]: g for g in gates}
    pinames = {lit_var(l): n for l, n in subj.inputs}
    poname = {l: n for l, n in subj.outputs}

    netname, produced = {}, set()
    lines, counts, total = [], {}, 0.0

    def require(litl):
        """Produce a net for literal `litl`, emitting its gate once."""
        v, p = lit_var(litl), lit_inv(litl)
        if p == 0 and v in pinames:
            netname[litl] = pinames[v]
            return netname[litl]
        if litl in netname:
            return netname[litl]
        name = poname.get(litl, f"n{v}" if p == 0 else f"nb{v}")
        netname[litl] = name
        ch = choice[v][p]
        if lit(v, 1 - p) in produced and (ch is None or ch[0] != "gate"
                or by_name["inv1"]["area"] < ch[3]["area"]):
            ch = ("inv",)
        assert ch, f"uncoverable literal {litl}"
        if ch[0] == "inv":
            g = by_name["inv1"]
            lines.append(f".gate inv1 a={require(lit(v, 1 - p))} "
                         f"O={name}")
        else:
            _k, binds, lits, g = ch
            for l in lits:
                require(l)
            args = " ".join(f"{pin}={netname[binds[pin]]}"
                            for pin in sorted(g["pins"]))
            lines.append(f".gate {g['name']} {args} O={name}")
        nonlocal total
        counts[g["name"]] = counts.get(g["name"], 0) + 1
        total += g["area"]
        produced.add(litl)
        return name

    for l, _ in subj.outputs:
        require(l)

    model = subj.model or Path(out_path).stem
    with open(out_path, "w") as f:
        f.write(f".model {model}\n")
        f.write(".inputs " + " ".join(n for _, n in subj.inputs) + "\n")
        f.write(".outputs " + " ".join(n for _, n in subj.outputs) + "\n")
        f.writelines(l + "\n" for l in lines)
        f.write(".end\n")
    rep = {"subject": subj.model, "area": round(total, 5),
           "cells": sum(counts.values()), "gates": counts}
    with open(report_path, "w") as f:
        json.dump(rep, f, indent=1, sort_keys=True)
        f.write("\n")
    return rep


def main():
    sys.setrecursionlimit(1_000_000)
    ap = argparse.ArgumentParser()
    ap.add_argument("subject", help="subject graph (.aag)")
    ap.add_argument("library", help="cell library (lib.json)")
    ap.add_argument("-o", "--output", default="mapped.blif")
    ap.add_argument("-r", "--report", default="report.json")
    args = ap.parse_args()

    subj = load(args.subject)
    gates = load_lib(args.library)
    _cost, choice = cover(subj, gates)
    emit(subj, gates, choice, args.output, args.report)


if __name__ == "__main__":
    main()
