#!/usr/bin/env python3
"""Read OpenROAD's post-CTS gcd with unmodified OpenSTA, run sta.py, save student results.
Defaults: T=0.28 ns, early/late cell-delay derates=0.9/1.1; zero wire delay,
clock latency and uncertainty. Full-cycle rising-edge setup only.
Native I/O constraints and transition selection differ from this scalar model;
compare CPPR credit, not absolute WNS. The runner contains only input/output code.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

# Embedded Tcl only reads the original case and nominal arc delays.
OPENSTA_SCRIPT = r'''
try {
    foreach lib [split $::env(HW2_LIBS) \n] { read_liberty $lib }
    read_verilog $::env(HW2_ROOT)/src/rsz/test/gcd_asap7_cts.v
    link_design gcd
    source $::env(HW2_ROOT)/test/flow_helpers.tcl
    read_sdc $::env(HW2_ROOT)/test/gcd_asap7.sdc
    set_operating_conditions -analysis_type on_chip_variation
    set_propagated_clock [all_clocks]
    sta::find_delays
    set out [open $::env(HW2_GRAPH) w]
    set vertices [sta::vertex_iterator]
    while {[$vertices has_next]} {
        set v [$vertices next]; set p [$v pin]
        set dir [sta::pin_direction $p]
        if {$dir eq "internal"} { continue }
        puts $out [join [list pin [get_full_name $p] $dir [$p is_top_level_port]] \t]
        set edges [$v out_edge_iterator]
        while {[$edges has_next]} {
            set e [$edges next]; set role [$e role]
            if {$role ni {wire combinational "Reg Clk to Q" setup}} { continue }
            if {[sta::pin_direction [[$e to] pin]] eq "internal"} { continue }
            set prefix [list arc [get_full_name [[$e from] pin]] [get_full_name [[$e to] pin]] $role]
            if {$role eq "wire"} {
                puts $out [join [concat $prefix [list ^ ^ 0 0]] \t]
            } else {
                foreach arc [$e timing_arcs] {
                    # Nominal seconds -> ns; only cell delays receive derates.
                    lassign [$e arc_delays $arc] mn mx
                    set mn [expr {$mn * 1e9}]; set mx [expr {$mx * 1e9}]
                    if {$role ne "setup"} {
                        set mn [expr {$mn * 0.9}]; set mx [expr {$mx * 1.1}]
                    }
                    puts $out [join [concat $prefix [list [$arc from_edge] [$arc to_edge] $mn $mx]] \t]
                }
            }
        }
        $edges finish
    }
    $vertices finish
    close $out
} on error {message options} {
    puts stderr $message
    exit 1
}
exit 0
'''


def build_graph(path):
    """Separate the known case into a data DAG and a noninverting clock tree."""
    pins, edges, source, setup, launch, capture = {}, {}, {}, {}, {}, {}
    for line in path.read_text().splitlines():
        kind, *row = line.split('\t')
        if kind == 'pin':
            pins[row[0]] = (row[1], row[2] == '1')
        else:
            s, t, role, rf, rt, mn, mx = row
            mn, mx = float(mn), float(mx)
            if role == 'Reg Clk to Q':
                if rf != '^':
                    raise ValueError('only rising-edge FFs are supported')
                source[t] = max(source.get(t, -math.inf), mx); launch[t] = s
            elif role == 'setup':
                setup[t] = max(setup.get(t, -math.inf), mx); capture[t] = s
            else:
                # Collapse data transitions; keep rising-to-rising clock arcs.
                old = edges.get((s, t), (0, math.inf, -math.inf))
                edges[s, t] = (max(old[0], mx),
                    min(old[1], mn) if rf == rt == '^' else old[1],
                    max(old[2], mx) if rf == rt == '^' else old[2])
    root = 'clk'  # This fixed upstream case has one physical clock root.
    incoming = {n: [] for n in pins}
    for s, t in edges:
        incoming[t].append(s)
    clocks = {root} | set(launch.values()) | set(capture.values())
    stack = list(clocks)
    while stack:
        for p in incoming[stack.pop()]:
            if p not in clocks:
                clocks.add(p); stack.append(p)
    cnames = sorted(clocks); cids = {n: i for i, n in enumerate(cnames)}
    parent, early, late = [None]*len(cnames), [0.0]*len(cnames), [0.0]*len(cnames)
    for n in clocks - {root}:
        if len(incoming[n]) != 1:
            raise ValueError('case requires a rooted clock tree')
        p = incoming[n][0]; arc = edges[p, n]
        parent[cids[n]], early[cids[n]], late[cids[n]] = cids[p], arc[1], arc[2]
    clock = SimpleNamespace(nodes=cnames, root=cids[root], parent=parent, early=early, late=late)
    for n, (direction, top) in pins.items():
        if (top and direction == 'input') or (not top and direction == 'output' and not incoming[n]):
            source.setdefault(n, 0.0); launch.setdefault(n, None)
    active = (set(setup) | {n for n, (d, top) in pins.items() if top and d == 'output'}) - clocks
    stack = list(active)
    while stack:
        for p in incoming[stack.pop()]:
            if p not in clocks and p not in active:
                active.add(p); stack.append(p)
    names = sorted(active); ids = {n: i for i, n in enumerate(names)}
    inc, out = [[] for _ in names], [[] for _ in names]
    for (s, t), (delay, _, _) in sorted(edges.items()):
        if s in active and t in active:
            inc[ids[t]].append((ids[s], delay)); out[ids[s]].append((ids[t], delay))
    return SimpleNamespace(nodes=names, incoming=inc, outgoing=out, clock=clock,
        source_at={ids[n]: d for n, d in source.items() if n in active},
        endpoint_setup={ids[n]: d for n, d in setup.items()},
        launch_clock={ids[n]: cids[c] if c is not None else None for n, c in launch.items() if n in active},
        capture_clock={ids[n]: cids[c] for n, c in capture.items()})


def load_case(sta, out, openroad_root):
    root = Path(openroad_root).resolve(); out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    groups = {'RVT': ('AO', 'OA', 'SIMPLE', 'INVBUF'),
              'SLVT': ('AO', 'OA', 'SIMPLE', 'INVBUF', 'SEQ'), 'LVT': ('SIMPLE', 'INVBUF')}
    libs = []
    for vt, names in groups.items():
        for g in names:
            suffix = '220123.lib' if g == 'SEQ' else '220122.lib.gz' if g == 'INVBUF' else '211120.lib.gz'
            libs.append(root/'test/asap7'/f'asap7sc7p5t_{g}_{vt}_FF_nldm_{suffix}')
    inputs = libs + [root/'src/rsz/test/gcd_asap7_cts.v', root/'test/gcd_asap7.sdc', root/'test/flow_helpers.tcl']
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(f'missing OpenROAD input: {path}')
    # A system temporary script also works when the source/output path has spaces.
    with tempfile.TemporaryDirectory(prefix='hw2-') as tmp:
        script, graph = Path(tmp)/'read.tcl', Path(tmp)/'graph.txt'
        script.write_text(OPENSTA_SCRIPT)
        env = dict(os.environ, HW2_ROOT=str(root), HW2_GRAPH=str(graph), HW2_LIBS='\n'.join(map(str, libs)))
        with (out/'opensta.log').open('w') as log:
            subprocess.run([sta, '-no_init', '-exit', str(script)], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        return build_graph(graph)


def execute_kernel(graph, period, kernel, out):
    order = kernel.topological_order(graph)
    early, late = kernel.propagate_clock(graph.clock)
    arrival, predecessor = kernel.propagate_arrival(graph, order, late)
    required = kernel.propagate_required(graph, order, early, period)
    result = kernel.summarize_endpoints(graph, arrival, early, period)
    result['period'] = period
    ids = {name: n for n, name in enumerate(graph.nodes)}
    for mode in ('before', 'after'):
        stats = result[mode]
        pair = next(p for p in result['pairs'] if p['endpoint'] == stats['worst_endpoint'] and p['launch'] == stats['launch'])
        path = kernel.trace_critical_path(graph, predecessor[ids[pair['launch']]], ids[pair['endpoint']])
        stats.update(arrival=pair['arrival'], required=pair['required_'+mode],
                     cppr=pair['cppr'] if mode == 'after' else 0,
                     common_pin=pair['common_pin'] if mode == 'after' else None,
                     critical_path=[graph.nodes[n] for n in path])
    timing = dict(period=period, order=order,
        clock=[dict(name=n, early=early[i], late=late[i]) for i, n in enumerate(graph.clock.nodes)],
        pre_required=[None if x == math.inf else x for x in required],
        launches=[dict(source=graph.nodes[s], nodes=[dict(arrival=arrival[s][n], predecessor=predecessor[s][n])
                    for n in range(len(graph.nodes))]) for s in sorted(graph.source_at)])
    for name, data in [('result.json', result), ('node_timing.json', timing)]:
        (out/name).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    print(f"WNS: {result['before']['wns']:+.6f} -> {result['after']['wns']:+.6f} ns")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--openroad-root', default=os.environ.get('OPENROAD_ROOT'), required=not os.environ.get('OPENROAD_ROOT'))
    ap.add_argument('--sta', default='sta', help='OpenSTA executable')
    ap.add_argument('--period', type=float, default=0.28, help='period in ns')
    ap.add_argument('--out', type=Path, default=Path('run_gcd'))
    args = ap.parse_args()
    if not math.isfinite(args.period) or args.period <= 0:
        ap.error('--period must be positive and finite')
    try:
        import sta
        graph = load_case(args.sta, args.out, args.openroad_root)
        execute_kernel(graph, args.period, sta, args.out)
    except (OSError, ValueError, NotImplementedError, subprocess.CalledProcessError) as e:
        ap.exit(1, f'{e}; see {args.out}/opensta.log for OpenSTA errors\n')


if __name__ == '__main__':
    main()
