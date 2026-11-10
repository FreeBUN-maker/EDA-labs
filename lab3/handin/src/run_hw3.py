#!/usr/bin/env python3
"""HW3 Problem 3 runner: sequence-pair macro floorplanning in OpenROAD.

Typical use from the extracted bundle:

    python3 run_hw3.py --orfs-root /path/to/OpenROAD-flow-scripts

It performs four steps:
  1. locate (or generate) the chameleon `2_1_floorplan.odb`;
  2. run the student's `hw3.py` inside OpenROAD Python;
  3. source `macro_placement.tcl`, then run
     place_pins -> global_placement -> detailed_placement;
  4. validate legality and the post-placement HPWL against `baseline.json`.

The runner never edits the student's source.  It writes everything to
`--workdir` (default `hw3_run/`) and prints a PASS/FAIL summary.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_STUDENT = ROOT / "hw3.py"
DEFAULT_CHECKER = ROOT / "check.py"
DEFAULT_MACRO_DATA = ROOT / "fixtures" / "chameleon_macro_data.json"
DEFAULT_BASELINE = ROOT / "baseline.json"
DESIGN = "sky130hd/chameleon"
DESIGN_CONFIG = f"designs/{DESIGN}/config.mk"
ODB_DIR = Path("flow") / "results" / "sky130hd" / "chameleon" / "base"
ODB_2_1 = "2_1_floorplan.odb"
ODB_2 = "2_floorplan.odb"


def run(cmd, cwd=None, log_path=None, timeout=None, quiet=False):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    start = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if log_path:
            Path(log_path).write_text(out)
        print(f"timeout after {timeout}s", file=sys.stderr)
        return 124, out
    elapsed = time.time() - start
    out = proc.stdout
    if log_path:
        Path(log_path).write_text(out)
    if not quiet:
        print(out, end="" if out.endswith("\n") else "\n")
    print(f"  -> exit {proc.returncode} in {elapsed:.1f}s", flush=True)
    return proc.returncode, out


def find_openroad(args):
    candidates = []
    if args.openroad:
        candidates.append(Path(args.openroad))
    if args.orfs_root:
        candidates.append(Path(args.orfs_root) / "tools" / "install"
                          / "OpenROAD" / "bin" / "openroad")
    w = shutil.which("openroad")
    if w:
        candidates.append(Path(w))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c.resolve()
    raise SystemExit(
        "cannot find openroad; pass --openroad /path/to/openroad or "
        "--orfs-root /path/to/OpenROAD-flow-scripts")


def ensure_odbs(args, workdir):
    """Return (odb_2_1, odb_2) or exit with a useful message."""
    if not args.orfs_root:
        raise SystemExit("--orfs-root is required to locate the chameleon ODBs")
    base = Path(args.orfs_root) / ODB_DIR
    odb_2_1 = base / ODB_2_1
    odb_2 = base / ODB_2
    if odb_2_1.is_file() and odb_2.is_file():
        return odb_2_1, odb_2
    if args.no_run_flow:
        raise SystemExit(
            f"missing {odb_2_1} or {odb_2}; run the chameleon floorplan first:\n"
            f"  cd {Path(args.orfs_root) / 'flow'}\n"
            f"  make DESIGN_CONFIG={DESIGN_CONFIG} floorplan")
    flow_dir = Path(args.orfs_root) / "flow"
    if not (flow_dir / "Makefile").is_file():
        raise SystemExit(f"{flow_dir} does not look like an ORFS flow directory")
    print(f"missing chameleon floorplan; running `make floorplan` in {flow_dir}")
    rc, log = run(["make", f"DESIGN_CONFIG={DESIGN_CONFIG}", "floorplan"],
                  cwd=flow_dir, log_path=workdir / "orfs_floorplan.log",
                  timeout=args.flow_timeout, quiet=True)
    for line in log.splitlines()[-10:]:
        print("  " + line)
    if rc != 0 or not odb_2_1.is_file():
        raise SystemExit(
            f"chameleon floorplan failed (exit {rc}); see "
            f"{workdir / 'orfs_floorplan.log'}")
    return odb_2_1, odb_2


def parse_hpwl(log_text):
    """Prefer the legalized HPWL printed by detailed_placement."""
    legal = re.findall(r"legalized HPWL\s+([0-9.]+)\s+u", log_text)
    original = re.findall(r"original HPWL\s+([0-9.]+)\s+u", log_text)
    if legal:
        return (float(legal[-1]),
                float(original[-1]) if original else float(legal[-1]))
    if original:
        return float(original[-1]), float(original[-1])
    # global_placement's final table has an HPWL column before detailed
    # placement; accept the last numeric row as a fallback.
    rows = re.findall(r"^\s*\d+\s*\|\s*[\d.]+\s*\|\s*([0-9.]+)", log_text,
                      re.MULTILINE)
    if rows:
        return float(rows[-1]), float(rows[-1])
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orfs-root", default=os.environ.get("ORFS_ROOT"),
                    help="OpenROAD-flow-scripts checkout")
    ap.add_argument("--openroad", default=None,
                    help="explicit path to the openroad binary")
    ap.add_argument("--workdir", default="hw3_run")
    ap.add_argument("--student", default=str(DEFAULT_STUDENT))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=100000)
    ap.add_argument("--no-run-flow", action="store_true",
                    help="do not run `make floorplan` if the ODBs are missing")
    ap.add_argument("--flow-timeout", type=int, default=1800,
                    help="timeout for `make floorplan` (s)")
    ap.add_argument("--place-timeout", type=int, default=1800,
                    help="timeout for the OpenROAD placement flow (s)")
    ap.add_argument("--skip-student", action="store_true",
                    help="reuse an existing macro_placement.json/tcl")
    args = ap.parse_args()
    if args.orfs_root:
        args.orfs_root = str(Path(args.orfs_root).resolve())

    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    openroad = find_openroad(args)
    print(f"openroad: {openroad}")
    version = subprocess.run([str(openroad), "-version"], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             check=False).stdout.strip()
    (workdir / "environment.json").write_text(json.dumps(
        {"openroad_version": version, "runner_python": sys.version,
         "orfs_root": args.orfs_root,
         "orfs_revision": os.environ.get("HW3_ORFS_REVISION"),
         "container_image": os.environ.get("HW3_CONTAINER_IMAGE")}, indent=2) + "\n")

    odb_2_1, odb_2 = ensure_odbs(args, workdir)
    print(f"input:  {odb_2_1}")
    print(f"RTLMP ODB: {odb_2}")

    # 1. Student algorithm (OpenROAD Python, so it can read ODB directly).
    if not args.skip_student:
        student = Path(args.student).resolve()
        if not student.is_file():
            raise SystemExit(f"student script not found: {student}")
        rc, _ = run(
            [str(openroad), "-python", "-no_init", "-exit", str(student),
             "--input", str(odb_2_1), "--out-dir", str(workdir),
             "--seed", str(args.seed), "--iters", str(args.iters)],
            cwd=workdir, log_path=workdir / "student.log", timeout=600)
        if rc != 0:
            raise SystemExit(f"student hw3.py failed (exit {rc}); "
                             f"see {workdir / 'student.log'}")
    for f in ("macro_placement.json", "macro_placement.tcl"):
        if not (workdir / f).is_file():
            raise SystemExit(f"missing {workdir / f}")

    # 2. Macro legality / geometry gate before the expensive placement flow.
    rc, _ = run(
        [sys.executable, str(DEFAULT_CHECKER),
         "--macro-data", str(DEFAULT_MACRO_DATA),
         "--placement", str(workdir / "macro_placement.json")],
        cwd=workdir, log_path=workdir / "check_macro.log")
    if rc != 0:
        raise SystemExit("macro placement failed the legality check; "
                         "not running OpenROAD placement")

    # 3. Apply the placement and run the downstream flow.
    flow_tcl = workdir / "flow.tcl"
    flow_tcl.write_text(
        f"read_db {{{odb_2_1}}}\n"
        f"source {{{workdir / 'macro_placement.tcl'}}}\n"
        "place_pins -hor_layers met3 -ver_layers met2\n"
        "global_placement -density 0.6\n"
        "detailed_placement\n"
        f"write_db {{{workdir / '3_2_place_custom.odb'}}}\n"
        "report_design_area\n")
    t0 = time.time()
    rc, log = run([str(openroad), "-no_init", "-exit", str(flow_tcl)],
                  cwd=workdir, log_path=workdir / "flow.log",
                  timeout=args.place_timeout, quiet=True)
    print("  (full OpenROAD log in flow.log; last lines below)")
    for line in log.splitlines()[-12:]:
        print("  " + line)
    elapsed = time.time() - t0
    legal_hpwl, original_hpwl = parse_hpwl(log)

    baseline = json.loads(DEFAULT_BASELINE.read_text())
    flow_report = {
        "design": DESIGN,
        "openroad": str(openroad),
        "flow_hpwl_um": legal_hpwl,
        "original_hpwl_um": original_hpwl,
        "baseline_hpwl_um": baseline["flow_hpwl_um"],
        "threshold_um": baseline["threshold_um"],
        "ratio_to_baseline": (legal_hpwl / baseline["flow_hpwl_um"]
                              if legal_hpwl is not None else None),
        "runtime_s": round(elapsed, 1),
        "flow_exit": rc,
        "pass": (rc == 0 and legal_hpwl is not None
                 and legal_hpwl <= baseline["threshold_um"]),
    }
    # Include the student's macro HPWL for reporting.
    placement = json.loads((workdir / "macro_placement.json").read_text())
    flow_report["macro_hpwl_um"] = placement.get("macro_hpwl_um")
    (workdir / "flow_report.json").write_text(
        json.dumps(flow_report, indent=1, sort_keys=True) + "\n")
    if rc != 0:
        print(f"OpenROAD placement flow failed (exit {rc}); "
              f"see {workdir / 'flow.log'}")
    if legal_hpwl is None:
        print("could not parse a post-placement HPWL from flow.log")

    # 4. Final checker gate (legality + HPWL threshold).
    rc_check, _ = run(
        [sys.executable, str(DEFAULT_CHECKER),
         "--macro-data", str(DEFAULT_MACRO_DATA),
         "--placement", str(workdir / "macro_placement.json"),
         "--flow-report", str(workdir / "flow_report.json"),
         "--baseline", str(DEFAULT_BASELINE)],
        cwd=workdir, log_path=workdir / "check.log")
    print(f"\nartifacts: {workdir}")
    print(f"  macro_placement.json / .tcl, 3_2_place_custom.odb, "
          f"flow_report.json, flow.log")
    return 0 if rc_check == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
