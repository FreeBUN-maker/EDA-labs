#!/usr/bin/env python3
"""HW3 Problem 3 checker.

Validates a submitted `macro_placement.json` against the frozen chameleon
macro snapshot and, when a `flow_report.json` is present, checks the
post-placement HPWL against the RTLMP baseline threshold.

The checker is plain Python (no OpenROAD import).  The runner
`run_hw3.py` invokes it with the paths it generated:

    python3 check.py \
        --macro-data fixtures/chameleon_macro_data.json \
        --placement macro_placement.json \
        --flow-report flow_report.json \
        --baseline baseline.json

A missing flow report only disables the HPWL threshold check (useful when
a student wants to inspect macro legality before running the flow).
"""

import argparse
import json
import math
import sys
from pathlib import Path

HALO = 35.0          # um, matches chameleon MACRO_PLACE_HALO
TOL = 1.0            # um, place_macro snaps macros to the manufacturing grid
ORIENTS = ("R0", "MX", "MY", "R180")


def transform_pin(px, py, w, h, orient):
    if orient == "R0":
        return px, py
    if orient == "MX":
        return px, h - py
    if orient == "MY":
        return w - px, py
    if orient == "R180":
        return w - px, h - py
    raise ValueError(f"bad orientation {orient}")


def load_json(path):
    return json.loads(Path(path).read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--macro-data",
                    default=str(Path(__file__).with_name("fixtures")
                                / "chameleon_macro_data.json"))
    ap.add_argument("--placement", default="macro_placement.json")
    ap.add_argument("--flow-report", default=None)
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--threshold", type=float, default=None,
                    help="override the flow HPWL threshold in um")
    args = ap.parse_args()

    data = load_json(args.macro_data)
    macros = data["macros"]
    core = data["core"]
    names = set(macros)

    payload = load_json(args.placement)
    placement = payload.get("macros", {})

    errors = []
    missing = sorted(names - set(placement))
    extra = sorted(set(placement) - names)
    if missing:
        errors.append(f"missing macros in placement: {missing}")
    if extra:
        errors.append(f"unknown macros in placement: {extra}")
    if missing or extra:
        for e in errors:
            print("FAIL:", e)
        return 1

    # Geometry: inside the core and pairwise halo-clean.
    rects = {}
    for name in sorted(names):
        p = placement[name]
        m = macros[name]
        try:
            x = float(p["x"])
            y = float(p["y"])
            orient = p["orient"]
        except (KeyError, TypeError, ValueError):
            errors.append(f"{name}: need numeric x, y and a string orient")
            continue
        if orient not in ORIENTS:
            errors.append(f"{name}: orient {orient!r} not in {ORIENTS}")
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            errors.append(f"{name}: x/y must be finite")
            continue
        w, h = float(m["w"]), float(m["h"])
        rects[name] = (x, y, w, h)
        if x < core[0] - TOL or y < core[1] - TOL:
            errors.append(f"{name}: lower-left ({x:.3f},{y:.3f}) outside core")
        if x + w > core[2] + TOL or y + h > core[3] + TOL:
            errors.append(f"{name}: upper-right ({x+w:.3f},{y+h:.3f}) outside core")

    if len(rects) == len(names):
        ordered = sorted(rects)
        for i, a in enumerate(ordered):
            ax, ay, aw, ah = rects[a]
            for b in ordered[i + 1:]:
                bx, by, bw, bh = rects[b]
                separated = (
                    ax + aw + HALO <= bx + TOL or
                    bx + bw + HALO <= ax + TOL or
                    ay + ah + HALO <= by + TOL or
                    by + bh + HALO <= ay + TOL
                )
                if not separated:
                    errors.append(f"{a} and {b}: closer than {HALO} um halo")

    # Macro HPWL from the frozen snapshot.
    hp = None
    if len(rects) == len(names):
        hp = 0.0
        for net in data["nets"]:
            xs, ys = [], []
            for name, pin in net["pins"]:
                m = macros[name]
                x, y, _w, _h = rects[name]
                dx, dy = transform_pin(m["pins"][pin][0], m["pins"][pin][1],
                                       m["w"], m["h"],
                                       placement[name]["orient"])
                xs.append(x + dx)
                ys.append(y + dy)
            hp += (max(xs) - min(xs)) + (max(ys) - min(ys))

    print(f"macros: {len(rects)}/{len(names)}")
    if hp is not None:
        print(f"macro HPWL: {hp:.1f} um")

    # Optional flow HPWL gate.
    flow_hpwl = None
    baseline = None
    threshold = args.threshold
    if args.baseline:
        b = load_json(args.baseline)
        baseline = float(b.get("flow_hpwl_um"))
        if threshold is None:
            threshold = float(b.get("threshold_um", baseline))
    if args.flow_report:
        report = load_json(args.flow_report)
        v = report.get("flow_hpwl_um")
        if report.get("flow_exit", 0) != 0:
            errors.append(f"flow_report.json reports flow_exit={report['flow_exit']}")
        if report.get("pass") is False:
            errors.append("flow_report.json reports pass=false")
        if v is None:
            errors.append("flow_report.json has no flow_hpwl_um (flow failed?)")
        else:
            flow_hpwl = float(v)
    if flow_hpwl is not None and threshold is not None:
        ratio = flow_hpwl / baseline if baseline else float("nan")
        passed = flow_hpwl <= threshold
        print(f"flow HPWL: {flow_hpwl:.1f} um  "
              f"(baseline {baseline:.1f} um, ratio {ratio:.3f}, "
              f"threshold {threshold:.1f} um)  "
              f"{'PASS' if passed else 'FAIL'}")
        if not passed:
            errors.append(f"flow HPWL {flow_hpwl:.1f} > threshold {threshold:.1f}")

    for e in errors:
        print("FAIL:", e)
    print("RESULT:", "PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
