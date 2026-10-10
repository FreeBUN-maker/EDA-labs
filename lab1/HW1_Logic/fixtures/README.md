# HW1 technology-mapping fixtures

Four subject circuits plus a 19-gate cell library. Each `subj_*` ships as:

| file | content |
|---|---|
| `subj_*.v`    | the design in Verilog (the human-readable spec) |
| `subj_*.aag`  | the subject graph: combinational AIG in ASCII AIGER, with symbol table |
| `subj_*.aig`  | the same AIG in binary AIGER (the `cec` reference for ABC) |
| `subj_*_golden.json` | golden input/output vectors for simulation |

plus `lib.json` (library, student input) and `lib.genlib` (same library in
GENLIB format, for ABC's own `map` and for reading `.gate` BLIFs back).

The subjects are produced by

```sh
yosys -p "read_verilog subj_X.v; synth -top <top> -flatten -noabc; \
          aigmap; opt_clean; abc -g AND; opt_clean; \
          write_aiger -ascii -symbols subj_X.aag; \
          write_aiger -symbols subj_X.aig"
```

`subj_sbox` is the OpenCores AES S-box; `subj_riscv` wraps the riscv32i
adder, barrel shifter, and magnitude comparator into one 32-bit ALU.

## Subject graph (.aag)

ASCII AIGER, restricted to the combinational fragment:

    aag <M> <I> 0 <O> <A>
    <I> input literals       even numbers 2, 4, ..., 2I
    <O> output literals      one per line, possibly odd
    <A> and lines            "lhs a b", lhs even and fresh, in topo order
    i<k> <name> / o<k> <name>  symbol table giving port names in order
    c                          comment section (ends the file)

A literal `l` is variable `l >> 1`, complemented iff `l` is odd. The file
order of AND lines is topological. No constant literals (0/1) appear, and
no output is a constant or a primary input. The shipped `aig.py` parses
this format; you may use it or write your own.

## Library (lib.json)

```json
{"name": "asap7-mini",
 "gates": [{"name": "aoi21", "asap7": "AOI21x1_ASAP7_75t_R",
            "area": 0.11664, "func": "!(a*b+c)",
            "pins": ["a","b","c"], "out_inv": true,
            "pattern": ...}]}
```

`area` is the real ASAP7 cell area in um². `pattern` is the gate's pattern
tree over the AIG base:

- `{"and": [e1, e2]}` — a 2-input AND node; children are unordered;
- each edge `e = {"inv": bool, "node": <node>}` — `inv` is an inverter on
  that edge inside the gate;
- `{"leaf": "<pin>"}` — a leaf, labelled by the gate pin it binds.

`out_inv` is the polarity of the gate's output: a gate matched at AIG node
`v` produces literal `(v, out_inv)`. `inv1` has a leaf-only pattern — it
produces `(v, 1)` from `(v, 0)` or `(v, 0)` from `(v, 1)`, never matches
inside `matches_at`, and is the only way to change a literal's polarity.
`func` is the gate's function in `! * + ^ ( )` notation over the pin
names, for reference.

## Mapped netlist (mapped.blif)

BLIF with `.gate` instances — the same format ABC's `write_blif` emits
for a mapped network:

    .model <name>
    .inputs <subject input port names, in .aag order>
    .outputs <subject output port names, in .aag order>
    .gate <gname> <pin>=<net> ... O=<net>
    .end

Every pin of the gate must be bound exactly once; `O` names the produced
net. Nets driven by gate outputs may have any names, except that a
primary input drives its own name and each primary-output literal is
produced on a net carrying the output's port name.

## Golden vectors (subj_*_golden.json)

```json
{"subject": "subj_X",
 "inputs":  [input port names in .aag order],
 "outputs": [output port names in .aag order],
 "cases":   [[<in>, <out>], ...]}
```

`<in>`/`<out>` are hex strings; their most significant bit is the first
port in the respective list. Cases are exhaustive for `<= 16` inputs, else
a fixed sampled set (all-zero, all-one, walking-1/0, plus 8192 seeded
random vectors).

## Subjects and acceptance

| subject      | in/out | AIG nodes | area bound (um²) |
|---|---|---|---|
| `subj_p2func` | 4/1    |    5 | 0.2704 |
| `subj_alu4`   | 11/5   |   60 | 4.4902 |
| `subj_sbox`   | 8/8    |  695 | 52.3207 |
| `subj_riscv`  | 74/35  | 1735 | 122.5420 |

Run the bundled checker per subject:

```sh
python3 check.py --aag fixtures/subj_alu4.aag --lib fixtures/lib.json \
    --golden fixtures/subj_alu4_golden.json --net mapped.blif \
    --report report.json
```

An independent cross-check: ABC reads your mapped netlist as a mapped
network, reports its area, and verifies it against the reference AIG.
`yosys-abc` ships inside the Lab-0 ORFS install at
`$ORFS_ROOT/tools/install/yosys/bin/yosys-abc`:

```sh
$ORFS_ROOT/tools/install/yosys/bin/yosys-abc -c \
    "read fixtures/lib.genlib; read_blif mapped.blif; \
     cec fixtures/subj_alu4.aig; print_stats"
```
