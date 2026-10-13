# HW1_Logic bundle

- `HW1_problem.pdf` — assignment statement.
- `fixtures/` — subject graphs (`subj_*.v/.aag/.aig`), golden simulation
  vectors (`subj_*_golden.json`), and the `asap7-mini` cell library
  (`lib.json` + `lib.genlib`). `fixtures/README.md` is the format spec.
- `aig.py` — reference reader for the `.aag` subject graph; usable as-is
  or replaceable.
- `map.py` — Problem 3 tree-covering mapper: recursive pattern matching,
  bottom-up dual-polarity area DP, and the supplied netlist emitter.
- `check.py` — submission checker (netlist format, golden-vector
  simulation, area bound).
- `evaluate.py` — runs mapping, `check.py`, and ABC `cec` on all four
  subjects; also cross-checks ABC area and the report's per-gate counts.
- `build_abc.sh` — copies ABC source from a required command-line path and
  builds it in `lab1/tools/abc/`, leaving the supplied source unchanged.

```sh
python3 map.py fixtures/subj_alu4.aag fixtures/lib.json \
    -o mapped.blif -r report.json
python3 check.py --aag fixtures/subj_alu4.aag --lib fixtures/lib.json \
    --golden fixtures/subj_alu4_golden.json --net mapped.blif \
    --report report.json
```

Run the full evaluation from the repository root (Python 3.8+ and an
existing ABC or yosys-abc executable).

```sh
python3 lab1/HW1_Logic/evaluate.py \
    --abc /absolute/path/to/abc \
    --output-dir results
```

Both `--abc` and `--output-dir` are required. Relative paths are resolved
from the current working directory. The output directory is created if
needed. The script checks that the supplied ABC path is an executable
file; it does not search for ABC or use a default output directory.

If ABC is not already installed, build a private copy of the supplied source
(requires make, gcc, g++), then pass the resulting executable:

```sh
bash lab1/HW1_Logic/build_abc.sh path/to/abc/repo
python3 lab1/HW1_Logic/evaluate.py \
    --abc tools/abc/abc \
    --output-dir results
```

`build_abc.sh` requires exactly one argument: the ABC source directory.
Relative source paths are resolved from the current working directory;
the build directory is always `lab1/tools/abc/`. Set `JOBS` to change the
number of parallel build jobs (default: 4), or use `--help` for usage.

In the specified output directory, each subject gets `mapped_<subject>.blif`,
`report_<subject>.json`, and mapping/checker/ABC logs with the exact
commands. `summary.json` is written only after all four pass; any previous
summary is removed before evaluation starts.
ABC must explicitly report equivalence; a zero process exit status alone
does not count as a pass. ABC's printed area has two decimal places and is
compared to the report allowing only that rounding difference.

The matcher preserves library and AAG child order and rejects inconsistent
bindings of repeated pins. The DP sums costs over distinct **literals**,
then compares direct gates with an inverter on the opposite polarity.
The supplied emitter reuses produced literals across fanout and outputs;
the report counts the actual emitted instances.

Verified results (all golden-vector checks and all four ABC equivalence
checks pass):

| Subject | Cells | Area (um²) | Area bound (um²) | ABC CEC |
|---|---:|---:|---:|---|
| p2func | 3 | 0.26244 | 0.2704 | equivalent |
| alu4 | 47 | 4.35942 | 4.4902 | equivalent |
| sbox | 548 | 50.81130 | 52.3207 | equivalent |
| riscv | 1277 | 118.92906 | 122.5420 | equivalent |
