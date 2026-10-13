#!/usr/bin/env python3
"""Run all four HW1 P3 mappings, golden checks, and exact ABC CEC checks."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from check import THRESHOLDS, parse_blif


HERE = Path(__file__).resolve().parent
SUBJECTS = ("p2func", "alu4", "sbox", "riscv")


def run(command, log, cwd):
    proc = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    log.write_text("$ " + shlex.join(command) + "\n" + proc.stdout)
    if proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}); see {log}")
    return proc.stdout


def abc_quote(path):
    # ABC parses its own command language, independently of the shell.
    value = str(path)
    if any(c in value for c in '\";\n\r'):
        raise ValueError(f"unsupported character in ABC path: {value!r}")
    return f'"{value}"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abc", type=Path, required=True,
                        help="path to an ABC or yosys-abc executable")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="directory for netlists, reports, and logs")
    args = parser.parse_args()
    abc_path = args.abc.resolve()
    if not abc_path.is_file() or not os.access(abc_path, os.X_OK):
        parser.error(f"ABC executable is missing or not executable: {abc_path}")
    abc = str(abc_path)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave a stale all-passed summary.
    summary_path = out / "summary.json"
    summary_path.unlink(missing_ok=True)
    fixtures = HERE / "fixtures"
    summary = {"abc": abc, "subjects": []}
    print(f"ABC: {abc}", flush=True)

    for subject in SUBJECTS:
        name = f"subj_{subject}"
        net = out / f"mapped_{subject}.blif"
        report = out / f"report_{subject}.json"
        run([sys.executable, str(HERE / "map.py"),
             str(fixtures / f"{name}.aag"), str(fixtures / "lib.json"),
             "-o", str(net), "-r", str(report)],
            out / f"map_{subject}.log", out)
        check_log = out / f"check_{subject}.log"
        checked = run([sys.executable, str(HERE / "check.py"),
                       "--aag", str(fixtures / f"{name}.aag"),
                       "--lib", str(fixtures / "lib.json"),
                       "--golden", str(fixtures / f"{name}_golden.json"),
                       "--net", str(net), "--report", str(report)],
                      check_log, out)
        if "PASS" not in checked.splitlines():
            raise RuntimeError(f"checker did not pass; see {check_log}")
        rep = json.loads(report.read_text())
        _, _, _, instances = parse_blif(net)
        if rep["gates"] != dict(Counter(g for g, _ in instances)):
            raise RuntimeError(f"gate histogram differs from netlist: {report}")

        # -s disables startup scripts; all ABC scratch output stays in out.
        abc_log = out / f"abc_{subject}.log"
        command = (f"read {abc_quote(fixtures / 'lib.genlib')}; "
                   f"read_blif {abc_quote(net)}; "
                   f"cec {abc_quote(fixtures / (name + '.aig'))}; print_stats")
        verified = run([abc, "-s", "-c", command], abc_log, out)
        # ABC may exit zero even when a command fails: require affirmative CEC.
        if not re.search(r"Networks are equivalent\b", verified):
            raise RuntimeError(f"ABC did not prove equivalence; see {abc_log}")
        stats = re.search(r"\barea\s*=\s*([0-9.]+)", verified)
        if stats is None:
            raise RuntimeError(f"ABC did not report mapped area; see {abc_log}")
        abc_area = float(stats[1])
        # print_stats rounds mapped area to two decimal places.
        if abs(abc_area - rep["area"]) > 0.00501:
            raise RuntimeError(f"ABC area disagrees with report; see {abc_log}")
        golden = json.loads((fixtures / f"{name}_golden.json").read_text())
        summary["subjects"].append({
            "subject": name, "area": rep["area"], "cells": rep["cells"],
            "gates": rep["gates"], "area_bound": THRESHOLDS[name],
            "golden_vectors": len(golden["cases"]), "checker": "PASS",
            "abc_cec": "equivalent", "abc_area": abc_area,
        })
        print(f"{name}: {rep['cells']} cells, area {rep['area']:.5f} "
              f"<= {THRESHOLDS[name]:.5f}; check PASS; ABC equivalent",
              flush=True)

    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"All four subjects passed. Results: {out}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(str(exc))
