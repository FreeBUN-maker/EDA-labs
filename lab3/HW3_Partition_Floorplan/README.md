# HW3: Partition and Floorplan

## What is in this bundle

| File | Purpose |
| --- | --- |
| `HW3_problem.pdf` | Assignment statement (Problems 1–3). |
| `hw3.py` | Problem 3 skeleton. The ODB reader, annealing driver, and output writers are provided; implement `pack()` and `macro_hpwl()`. |
| `run_hw3.py` | Runs `hw3.py` inside OpenROAD Python, applies `macro_placement.tcl`, runs the placement flow, and invokes the checker. |
| `check.py` | Bundled checker: macro legality, halo, orientations, and post-placement HPWL. |
| `baseline.json` | RTLMP baseline HPWL and the acceptance threshold. |
| `fixtures/chameleon_macro_data.json` | Frozen macro/pin/net snapshot used by `check.py`. The student implementation must read the ODB, not this file. |

## Prerequisites

- A native OpenROAD-flow-scripts checkout (the same install as Lab 0).
- The chameleon floorplan stage. The runner generates it if missing:

  ```sh
  cd "$ORFS_ROOT/flow"
  make DESIGN_CONFIG=designs/sky130hd/chameleon/config.mk floorplan
  ```

  This creates
  `flow/results/sky130hd/chameleon/base/2_1_floorplan.odb` and
  `2_floorplan.odb`. The first `make floorplan` can take several minutes.

## Run

From this directory:

```sh
export ORFS_ROOT=/path/to/OpenROAD-flow-scripts
python3 run_hw3.py --orfs-root "$ORFS_ROOT"
```

The default student entry is `hw3.py`. If your implementation lives in
`src/` (the submission layout), pass it explicitly:

```sh
python3 run_hw3.py --orfs-root "$ORFS_ROOT" \
    --student src/hw3.py --workdir hw3_run
```

Outputs are written to `--workdir` (default `hw3_run/`):
`macro_placement.json`, `macro_placement.tcl`,
`3_2_place_custom.odb`, `flow_report.json`, and `flow.log`.

The checker must print `RESULT: PASS`. The post-placement HPWL threshold
is 730,000 µm; the RTLMP baseline is 738,243.9 µm.

## Submission

```
hw3-YOURSTUDENTID.zip
├── README.md          # exact commands and the ORFS path you used
├── src/               # hw3.py and any support files
└── hw3-YOURSTUDENTID.pdf
```
