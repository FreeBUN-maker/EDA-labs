# HW1_Logic bundle

- `HW1_problem.pdf` — assignment statement.
- `fixtures/` — subject graphs (`subj_*.v/.aag/.aig`), golden simulation
  vectors (`subj_*_golden.json`), and the `asap7-mini` cell library
  (`lib.json` + `lib.genlib`). `fixtures/README.md` is the format spec.
- `aig.py` — reference reader for the `.aag` subject graph; usable as-is
  or replaceable.
- `map.py` — runnable skeleton for Problem 3: the pipeline is wired, the
  pattern matcher / cover / emitter are stubs with contracts.
- `check.py` — submission checker (netlist format, golden-vector
  simulation, area bound). Exact equivalence is verified at grading time
  with ABC `cec`.

```sh
python3 map.py fixtures/subj_alu4.aag fixtures/lib.json \
    -o mapped.blif -r report.json
python3 check.py --aag fixtures/subj_alu4.aag --lib fixtures/lib.json \
    --golden fixtures/subj_alu4_golden.json --net mapped.blif \
    --report report.json
```
