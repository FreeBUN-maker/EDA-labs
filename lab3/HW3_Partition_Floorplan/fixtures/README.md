# HW3 partition/floorplan fixtures

- `chameleon_macro_data.json` — a frozen snapshot of the six chameleon
  hard macros, their pin centers at `R0`, the 127 macro-to-macro nets, and
  the core box; `check.py` validates placements against it without
  OpenROAD. The student implementation must read
  the ODB at runtime (`hw3.py` does this); the JSON is only the checker's
  view of the same design.
- The input ODBs (`2_1_floorplan.odb`, `2_floorplan.odb`) are produced by
  the OpenROAD-flow-scripts `sky130hd/chameleon` floorplan flow (see the
  Problem 3 statement). `run_hw3.py` generates them from your own ORFS
  checkout when they are missing.
