#!/usr/bin/env python3
"""HW3 Problem 3: sequence-pair macro floorplanning in OpenROAD.

The graded entry point is the runner:

    python3 run_hw3.py --orfs-root /path/to/OpenROAD-flow-scripts

Internally the runner executes this script under OpenROAD's Python,
because reading the input ODB requires OpenROAD's own `odb` module
(a plain `python3 hw3.py` cannot work):

    openroad -python -no_init -exit hw3.py \
        --input <flow>/results/sky130hd/chameleon/base/2_1_floorplan.odb \
        --out-dir <workdir>

That single command writes `macro_placement.json/.tcl`; the runner then
applies the Tcl, runs OpenROAD placement, and calls the checker.  Run
it by hand to debug the algorithm without the placement flow.

The reader, annealing framework, and writers originate in the assignment.
Packing, HPWL, strict area tie-breaking, and partition analysis are implemented
here. All design data comes from the input ODB, never the checker fixture.

Input ODB: the chameleon floorplan stage with six unplaced BLOCK macros.
Output files:
    macro_placement.json      (macro -> x, y, orient)
    macro_placement.tcl       (place_macro commands sourced by the runner)
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

HALO = 35.0                     # um, chameleon MACRO_PLACE_HALO
ORIENTS = ("R0", "MX", "MY", "R180")
CORE_MARGIN = 5.0               # um, keep macros away from the core boundary


@dataclass
class Macro:
    name: str
    master: str
    w: float
    h: float
    pins: dict = field(default_factory=dict)   # pin name -> (x, y) at R0


@dataclass
class Design:
    name: str
    core: tuple          # (x0, y0, x1, y1) in um
    macros: list         # list[Macro]
    nets: list           # list[list[(macro_index, pin_name)]]


# ---------------------------------------------------------------------------
# Provided ODB reader
# ---------------------------------------------------------------------------

def load_design(odb_path):
    """Read BLOCK macros, their pins, and macro-to-macro nets from an ODB."""
    import odb
    db = odb.dbDatabase.create()
    odb.read_db(db, odb_path)
    block = db.getChip().getBlock()
    dbu = float(block.getDbUnitsPerMicron())
    core = block.getCoreArea()

    macros = []
    index = {}
    for inst in block.getInsts():
        master = inst.getMaster()
        if master.getType() != "BLOCK":
            continue
        name = inst.getName()
        w = master.getWidth() / dbu
        h = master.getHeight() / dbu
        loc = inst.getLocation()
        orient = inst.getOrient()
        pins = {}
        for it in inst.getITerms():
            bb = it.getBBox()
            px = (bb.xMin() + bb.xMax()) / 2.0 / dbu - loc[0] / dbu
            py = (bb.yMin() + bb.yMax()) / 2.0 / dbu - loc[1] / dbu
            # The input ODB is normally unplaced at R0.  Undo other
            # orientations so every pin offset is stored at R0.
            if orient == "MX":
                py = h - py
            elif orient == "MY":
                px = w - px
            elif orient == "R180":
                px, py = w - px, h - py
            elif orient != "R0":
                raise SystemExit(f"{name}: unsupported input orientation {orient}")
            pins[it.getMTerm().getName()] = (px, py)
        index[name] = len(macros)
        macros.append(Macro(name, master.getName(), w, h, pins))

    nets = []
    for net in block.getNets():
        pins = []
        for it in net.getITerms():
            n = it.getInst().getName()
            if n in index:
                pins.append((index[n], it.getMTerm().getName()))
        if len(pins) >= 2:
            nets.append(pins)

    return Design(block.getName(),
                  (core.xMin() / dbu, core.yMin() / dbu,
                   core.xMax() / dbu, core.yMax() / dbu),
                  macros, nets)


def transform_pin(macro, orient, pin_name):
    """Return the R0 pin offset transformed by orientation (integer code)."""
    px, py = macro.pins[pin_name]
    if orient == 0:      # R0
        return px, py
    if orient == 1:      # MX: mirror about the x axis
        return px, macro.h - py
    if orient == 2:      # MY: mirror about the y axis
        return macro.w - px, py
    if orient == 3:      # R180
        return macro.w - px, macro.h - py
    raise ValueError(f"bad orientation code {orient}")


# ---------------------------------------------------------------------------
# Sequence-pair packing and macro HPWL
# ---------------------------------------------------------------------------

def pack(design, P, N, orient):
    """Pack a sequence pair and return (coords, W, H), or None on failure.

    Parameters
    ----------
    design : Design
    P, N   : lists of macro indices 0..n-1, each a permutation
    orient : list of orientation codes (0=R0, 1=MX, 2=MY, 3=R180)

    Return
    ------
    coords : list of (x, y) lower-left corners in um, in macro-index order
    W, H   : packed width and height in um

    Contract
    --------
    For each ordered pair (i, j):
        pos_P[i] < pos_P[j] and pos_N[i] < pos_N[j]  =>  i left of j
        pos_P[i] < pos_P[j] and pos_N[i] > pos_N[j]  =>  i below j
    The intended O(n^2) implementation builds the horizontal/vertical
    constraint DAGs and longest-paths them in topological order.

    Use (w_i + HALO) and (h_i + HALO) as the edge weights, so adjacent
    macros keep a 35 um halo.  Coordinates are for the actual lower-left
    corner; the halo is the extra gap to the next macro.  W and H include
    the halo at the right/top.
    """
    n = len(design.macros)
    expected = set(range(n))
    if (len(P) != n or len(N) != n or set(P) != expected
            or set(N) != expected or len(orient) != n
            or any(o not in range(4) for o in orient)):
        return None
    pos_n = [0] * n
    for k, i in enumerate(N):
        pos_n[i] = k
    horizontal, vertical = [[] for _ in range(n)], [[] for _ in range(n)]
    for k, i in enumerate(P):
        for j in P[k + 1:]:
            graph = horizontal if pos_n[i] < pos_n[j] else vertical
            graph[i].append(j)
    # Every edge points forward in P, so P is a topological order of both DAGs.
    x, y = [0.0] * n, [0.0] * n
    for i in P:
        m = design.macros[i]
        for j in horizontal[i]:
            x[j] = max(x[j], x[i] + m.w + HALO)
        for j in vertical[i]:
            y[j] = max(y[j], y[i] + m.h + HALO)
    W = max((x[i] + m.w + HALO for i, m in enumerate(design.macros)), default=0.0)
    H = max((y[i] + m.h + HALO for i, m in enumerate(design.macros)), default=0.0)
    return list(zip(x, y)), W, H


def macro_hpwl(design, coords, orient):
    """Return the sum of macro-net bounding-box half-perimeters in um.

    A net contributes only if it has at least two macro pins.  Use
    transform_pin() to place each pin under the chosen orientation.
    """
    total = 0.0
    for net in design.nets:
        if len(net) < 2:
            continue
        xs, ys = [], []
        for i, pin in net:
            dx, dy = transform_pin(design.macros[i], orient[i], pin)
            xs.append(coords[i][0] + dx)
            ys.append(coords[i][1] + dy)
        total += max(xs) - min(xs) + max(ys) - min(ys)
    return total


# ---------------------------------------------------------------------------
# Provided simulated-annealing driver
# ---------------------------------------------------------------------------

def _cost(design, P, N, orient):
    """Evaluate one candidate; return (cost, coords, W, H, hp), or None."""
    result = pack(design, P, N, orient)
    if result is None:
        return None
    coords, W, H = result
    hp = macro_hpwl(design, coords, orient)
    core_w = design.core[2] - design.core[0] - 2.0 * CORE_MARGIN
    core_h = design.core[3] - design.core[1] - 2.0 * CORE_MARGIN
    penalty = 0.0
    if W > core_w:
        penalty += (W - core_w) * 1.0e5
    if H > core_h:
        penalty += (H - core_h) * 1.0e5
    # Area must only break a tie, rather than trade against HPWL.
    return (hp + penalty, coords, W, H, hp)


def floorplan(design, seed=0, iters=100000, verbose=True):
    """Search over sequence pairs and orientations; return the best layout."""
    rng = random.Random(seed)
    n = len(design.macros)
    if n < 2 or iters < 0:
        raise ValueError("floorplan requires at least two macros and iters >= 0")
    P = list(range(n))
    N = list(range(n))
    rng.shuffle(P)
    rng.shuffle(N)
    orient = [0] * n

    first = _cost(design, P, N, orient)
    if first is None:
        raise RuntimeError("pack() rejected the initial sequence pair")
    cur_cost, coords, W, H, hp = first
    best = (P[:], N[:], orient[:], coords, W, H, hp)
    best_cost = cur_cost
    best_key = (cur_cost, W * H)
    cur_area = W * H
    t0 = time.time()
    # Slow cooling: the chain starts hot enough to climb out of the
    # initial basin and ends nearly greedy.
    T0, T1 = 5000.0, 20.0
    for it in range(iters):
        nP, nN, nO = P[:], N[:], orient[:]
        r = rng.random()
        if r < 0.35:
            i, j = rng.sample(range(n), 2)
            nP[i], nP[j] = nP[j], nP[i]
        elif r < 0.70:
            i, j = rng.sample(range(n), 2)
            nN[i], nN[j] = nN[j], nN[i]
        else:
            i = rng.randrange(n)
            nO[i] = rng.randrange(4)

        outcome = _cost(design, nP, nN, nO)
        if outcome is None:
            continue
        c, coords, W, H, hp = outcome
        T = T0 * (T1 / T0) ** (it / max(1, iters - 1))
        candidate_key = (c, W * H)
        if (candidate_key < (cur_cost, cur_area)
                or rng.random() < math.exp((cur_cost - c) / max(T, 1e-9))):
            P, N, orient, cur_cost, cur_area = nP, nN, nO, c, W * H
            if candidate_key < best_key:
                best_cost = c
                best_key = candidate_key
                best = (P[:], N[:], orient[:], coords, W, H, hp)
        if verbose and it and it % 20000 == 0:
            print(f"  iter {it:6d}  cost {best_cost:.1f}  "
                  f"T {T:.1f}  {time.time() - t0:.1f}s", flush=True)

    P, N, orient, coords, W, H, hp = best
    if (W > design.core[2] - design.core[0] - 2 * CORE_MARGIN
            or H > design.core[3] - design.core[1] - 2 * CORE_MARGIN):
        raise RuntimeError("search found no feasible best layout; increase --iters or change --seed")
    return (P, N, orient, coords, W, H, hp), time.time() - t0


# ---------------------------------------------------------------------------
# Provided output writers
# ---------------------------------------------------------------------------

def write_outputs(design, result, out_dir):
    P, N, orient, coords, W, H, hp = result
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    x0, y0, _x1, _y1 = design.core
    ox, oy = x0 + CORE_MARGIN, y0 + CORE_MARGIN

    placement = {}
    tcl = ["# Generated by hw3.py -- source from OpenROAD after read_db"]
    for i, m in enumerate(design.macros):
        x = coords[i][0] + ox
        y = coords[i][1] + oy
        o = ORIENTS[orient[i]]
        placement[m.name] = {"x": round(x, 3), "y": round(y, 3), "orient": o}
        tcl.append(f"place_macro -macro_name {{{m.name}}} "
                   f"-location {{{x:.3f} {y:.3f}}} -orientation {o}")

    payload = {
        "design": design.name,
        "core": list(design.core),
        "halo_um": HALO,
        "packed_width_um": round(W, 3),
        "packed_height_um": round(H, 3),
        "macro_hpwl_um": round(hp, 3),
        "positive_sequence": [design.macros[i].name for i in P],
        "negative_sequence": [design.macros[i].name for i in N],
        "macros": placement,
    }
    (out / "macro_placement.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n")
    (out / "macro_placement.tcl").write_text("\n".join(tcl) + "\n")
    print(f"macro_hpwl={hp:.1f} um  packed={W:.1f}x{H:.1f} um  "
          f"wrote {out/'macro_placement.json'} and macro_placement.tcl")
    return payload


def partition_analysis(design):
    """Enumerate unordered bipartitions; both areas must be 45%-55% of total."""
    n = len(design.macros)
    areas = [m.w * m.h for m in design.macros]
    total = sum(areas)
    nets = [set(i for i, _pin in net) for net in design.nets]
    splits = []
    # Fix macro 0 in cluster A to count each split once.
    for mask in range(1, (1 << n) - 1, 2):
        a = {i for i in range(n) if mask & (1 << i)}
        area_a = sum(areas[i] for i in a)
        if not 0.45 * total <= area_a <= 0.55 * total:
            continue
        cut = sum(bool(net & a) and bool(net - a) for net in nets)
        splits.append({"a": [design.macros[i].name for i in sorted(a)],
                       "b": [design.macros[i].name for i in range(n) if i not in a],
                       "area_a_um2": area_a, "area_b_um2": total - area_a,
                       "cut": cut})
    incidence = {}
    for net in nets:
        key = tuple(sorted(net))
        incidence[key] = incidence.get(key, 0) + 1
    return {"total_area_um2": total, "half_area_um2": total / 2,
            "allowed_area_um2": [0.45 * total, 0.55 * total],
            "macros": [{"name": m.name, "master": m.master, "w": m.w,
                        "h": m.h, "area_um2": areas[i]}
                       for i, m in enumerate(design.macros)],
            "net_count": len(nets), "balanced_splits": splits,
            "incidence_groups": [{"macros": [design.macros[i].name for i in key],
                                  "count": count}
                                 for key, count in sorted(incidence.items())]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="2_1_floorplan.odb for sky130hd/chameleon")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=100000)
    args = ap.parse_args()

    design = load_design(args.input)
    print(f"design={design.name} macros={len(design.macros)} "
          f"macro_nets={len(design.nets)} core={design.core}")
    result, elapsed = floorplan(design, args.seed, args.iters)
    write_outputs(design, result, args.out_dir)
    out = Path(args.out_dir)
    (out / "partition_analysis.json").write_text(
        json.dumps(partition_analysis(design), indent=2, sort_keys=True) + "\n")
    (out / "search_config.json").write_text(json.dumps(
        {"seed": args.seed, "iters": args.iters, "elapsed_s": elapsed,
         "halo_um": HALO, "core_margin_um": CORE_MARGIN,
         "objective": "(macro_hpwl + overflow_penalty, packed_area)"}, indent=2) + "\n")
    print(f"elapsed {elapsed:.1f}s")


if __name__ == "__main__":
    main()
