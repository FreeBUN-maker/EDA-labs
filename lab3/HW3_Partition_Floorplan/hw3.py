#!/usr/bin/env python3
"""HW3 Problem 3 skeleton: sequence-pair macro floorplanning in OpenROAD.

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

Only `pack()` and `macro_hpwl()` are algorithmic stubs.  The ODB reader,
the simulated-annealing driver, and the output writers are provided; you
may replace any of them, but keep the command line and output files..

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
# Algorithmic stubs to implement
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
    raise NotImplementedError("pack(): build the SP constraint DAGs and "
                              "longest-path them; use w+HALO, h+HALO")


def macro_hpwl(design, coords, orient):
    """Return the sum of macro-net bounding-box half-perimeters in um.

    A net contributes only if it has at least two macro pins.  Use
    transform_pin() to place each pin under the chosen orientation.
    """
    raise NotImplementedError("macro_hpwl(): sum net bbox half-perimeters")


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
    # Prefer compact packings when HPWL is close.
    return (hp + penalty + 1.0e-3 * W * H, coords, W, H, hp)


def floorplan(design, seed=0, iters=100000, verbose=True):
    """Search over sequence pairs and orientations; return the best layout."""
    rng = random.Random(seed)
    n = len(design.macros)
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
        if c < cur_cost or rng.random() < math.exp((cur_cost - c) / max(T, 1e-9)):
            P, N, orient, cur_cost = nP, nN, nO, c
            if c < best_cost:
                best_cost = c
                best = (P[:], N[:], orient[:], coords, W, H, hp)
        if verbose and it and it % 20000 == 0:
            print(f"  iter {it:6d}  cost {best_cost:.1f}  "
                  f"T {T:.1f}  {time.time() - t0:.1f}s", flush=True)

    P, N, orient, coords, W, H, hp = best
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
        "macros": placement,
    }
    (out / "macro_placement.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n")
    (out / "macro_placement.tcl").write_text("\n".join(tcl) + "\n")
    print(f"macro_hpwl={hp:.1f} um  packed={W:.1f}x{H:.1f} um  "
          f"wrote {out/'macro_placement.json'} and macro_placement.tcl")
    return payload


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
    print(f"elapsed {elapsed:.1f}s")


if __name__ == "__main__":
    main()
