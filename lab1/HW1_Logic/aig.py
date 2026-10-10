#!/usr/bin/env python3
"""HW1 P3 helper: reader for the subject-graph format (.aag).

The subject graph is an and-inverter graph (AIG) in ASCII AIGER format:

    aag <M> <I> <L> <O> <A>        header (we only ship L = 0)
    <I> input literals             even integers 2, 4, ..., 2*I
    <O> output literals            one per line, possibly odd
    <A> and-gate lines             "lhs a b": lhs is the fresh even literal
                                   of the gate output; a, b are literals
    i<k> <name> / o<k> <name>      symbol table (input/output names)
    c                              trailing comment section

A literal l denotes a signal: variable l >> 1, complemented iff l is odd.
Guaranteed for all shipped fixtures: every AND input and every output
literal is > 1 (no constants appear).

load(path) returns a Subject:

    s.inputs    [(lit, name)]      primary-input literals in port order
    s.outputs   [(lit, name)]      primary-output literals in port order
    s.ands      {var: (l1, l2)}    AND gate children literals, keyed by
                                   the gate's variable (lhs >> 1)
    s.order     [var, ...]         AND variables in file order, which is
                                   topological (children precede parents)

Helpers: lit_var(l), lit_inv(l), lit(var, inv).
"""

from dataclasses import dataclass, field


def lit_var(lit):
    return lit >> 1


def lit_inv(lit):
    return lit & 1


def lit(var, inv):
    return (var << 1) | inv


@dataclass
class Subject:
    inputs: list = field(default_factory=list)    # [(lit, name)]
    outputs: list = field(default_factory=list)   # [(lit, name)]
    ands: dict = field(default_factory=dict)      # var -> (lit, lit)
    order: list = field(default_factory=list)     # topo order of ands
    model: str = ""


def load(path):
    lines = open(path).read().splitlines()
    hdr = lines[0].split()
    assert hdr[0] == "aag", f"{path}: not an ASCII AIGER file"
    m, i, nl, o, a = (int(x) for x in hdr[1:6])
    assert nl == 0, f"{path}: latches are not supported"
    assert m == i + nl + a, f"{path}: bad max-variable index"

    s = Subject()
    pos = 1
    in_lits = [int(lines[pos + k]) for k in range(i)]
    pos += i
    out_lits = [int(lines[pos + k]) for k in range(o)]
    pos += o
    for k in range(a):
        lhs, x, y = (int(t) for t in lines[pos + k].split())
        assert x > 1 and y > 1, f"{path}: constant edge on AND {lhs}"
        v = lit_var(lhs)
        assert not lit_inv(lhs) and v not in s.ands
        s.ands[v] = (x, y)
        s.order.append(v)
    pos += a
    inames, onames = {}, {}
    for line in lines[pos:]:
        if line == "c":
            break
        kind, rest = line[0], line[1:]
        idx, name = rest.split(None, 1)
        (inames if kind == "i" else onames)[int(idx)] = name
    s.inputs = [(l, inames[k]) for k, l in enumerate(in_lits)]
    s.outputs = [(l, onames[k]) for k, l in enumerate(out_lits)]
    return s


def topo_literals(s):
    """Every non-constant literal feeding an AND, as (var, inv) pairs."""
    seen = []
    for v in s.order:
        for ch in s.ands[v]:
            seen.append(ch)
    return seen
