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
- `test_map.py` — targeted tests for child swaps, internal/leaf inversions,
  repeated pins, distinct literal costs, inverter routes, and tie breaking.
- `evaluate.py` — runs mapping, `check.py`, and ABC `cec` on all four
  subjects; also cross-checks ABC area and the report's per-gate counts.
- `build_abc.sh` — builds a private copy of the supplied ABC in
  `lab1/tools/abc/`; the original ORFS source directory is only read.

```sh
python3 map.py fixtures/subj_alu4.aag fixtures/lib.json \
    -o mapped.blif -r report.json
python3 check.py --aag fixtures/subj_alu4.aag --lib fixtures/lib.json \
    --golden fixtures/subj_alu4_golden.json --net mapped.blif \
    --report report.json
```

Run the full evaluation from the repository root (Python 3.8+):

```sh
# Once, if there is no existing ABC executable; requires make, gcc, g++.
bash lab1/HW1_Logic/build_abc.sh

python3 lab1/HW1_Logic/test_map.py -v
python3 lab1/HW1_Logic/evaluate.py
```

`evaluate.py` first looks for `lab1/tools/abc/abc`, then the ORFS install
and source-tree binaries, then `yosys-abc` / `abc` on `PATH`. To choose an
existing executable explicitly:

```sh
python3 lab1/HW1_Logic/evaluate.py --abc /absolute/path/to/yosys-abc
```

Each subject gets `results/mapped_<subject>.blif`,
`results/report_<subject>.json`, and mapping/checker/ABC logs with the exact
commands. `results/summary.json` is written only after all four pass.
ABC must explicitly report equivalence; a zero process exit status alone
does not count as a pass. ABC's printed area has two decimal places and is
compared to the report allowing only that rounding difference.

The individual commands below, run from `lab1/HW1_Logic/`, reproduce all
four subjects without the evaluation wrapper:

```sh
mkdir -p results
for s in p2func alu4 sbox riscv; do
    python3 map.py "fixtures/subj_${s}.aag" fixtures/lib.json \
        -o "results/mapped_${s}.blif" -r "results/report_${s}.json"
    python3 check.py --aag "fixtures/subj_${s}.aag" --lib fixtures/lib.json \
        --golden "fixtures/subj_${s}_golden.json" \
        --net "results/mapped_${s}.blif" --report "results/report_${s}.json"
    ../tools/abc/abc -s -c "read fixtures/lib.genlib; \
        read_blif results/mapped_${s}.blif; \
        cec fixtures/subj_${s}.aig; print_stats"
done
```

The matcher preserves library and AAG child order and rejects inconsistent
bindings of repeated pins. The DP sums costs over distinct **literals**,
then compares direct gates with an inverter on the opposite polarity.
The supplied emitter reuses produced literals across fanout and outputs;
the report counts the actual emitted instances.

Verified results (all eight unit tests, all golden-vector checks, and all
four ABC equivalence checks pass):

| Subject | Cells | Area (um²) | Area bound (um²) | ABC CEC |
|---|---:|---:|---:|---|
| p2func | 3 | 0.26244 | 0.2704 | equivalent |
| alu4 | 47 | 4.35942 | 4.4902 | equivalent |
| sbox | 548 | 50.81130 | 52.3207 | equivalent |
| riscv | 1277 | 118.92906 | 122.5420 | equivalent |
