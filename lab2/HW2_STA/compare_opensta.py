#!/usr/bin/env python3
"""Independently run native OpenSTA with CPPR off/on for selected register pairs.

Preserves the supplied reader and native SDC I/O constraints. Only CPPR credits
are compared: native rise/fall path selection differs from the scalar model.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess


SCRIPT = r'''
try {
    foreach lib [split $::env(HW2_LIBS) \n] { read_liberty $lib }
    read_verilog $::env(HW2_ROOT)/src/rsz/test/gcd_asap7_cts.v
    link_design gcd
    source $::env(HW2_ROOT)/test/flow_helpers.tcl
    read_sdc $::env(HW2_ROOT)/test/gcd_asap7.sdc
    set_cmd_units -time ns
    create_clock -name core_clock -period $::env(HW2_PERIOD) [get_ports clk]
    set_operating_conditions -analysis_type on_chip_variation
    set_propagated_clock [all_clocks]
    set_clock_latency -source 0 [all_clocks]
    set_clock_uncertainty 0 [all_clocks]
    set_timing_derate -early -cell_delay 0.9
    set_timing_derate -late -cell_delay 1.1
    sta::set_crpr_mode same_transition
    set input [open $::env(HW2_PAIRS) r]
    set lines [split [string trim [read $input]] \n]
    close $input
    foreach enabled {0 1} {
        sta::set_crpr_enabled $enabled
        set index 0
        foreach line $lines {
            lassign [split $line \t] launch endpoint
            set clock_pin "[file dirname $launch]/CLK"
            set stem "$::env(HW2_OUT)/pair_${index}_cppr_${enabled}"
            report_checks -from [get_pins $clock_pin] -through [get_pins $launch] \
                -to [get_pins $endpoint] -path_delay max \
                -format full_clock_expanded -digits 9 > ${stem}.txt
            report_checks -from [get_pins $clock_pin] -through [get_pins $launch] \
                -to [get_pins $endpoint] -path_delay max -format json > ${stem}.json
            incr index
        }
    }
} on error {message options} {
    puts stderr $message
    exit 1
}
exit 0
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openroad-root', type=Path, required=True)
    parser.add_argument('--sta', default='sta')
    parser.add_argument('--results', type=Path, default=Path('run_gcd/result.json'))
    parser.add_argument('--out', type=Path, default=Path('run_gcd/native'))
    args = parser.parse_args()
    root, out = args.openroad_root.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    result = json.loads(args.results.read_text())
    # Include the global worst pairs plus both competing launches at one endpoint.
    selected = {(result[m]['launch'], result[m]['worst_endpoint']) for m in ('before', 'after')}
    changed = [e for e in result['endpoints'] if e['before_launch'] != e['after_launch']]
    if not changed:
        raise ValueError('no endpoint changes its worst launch in this run')
    example = min(changed, key=lambda e: e['before_slack'])
    selected.update((example[m + '_launch'], example['endpoint']) for m in ('before', 'after'))
    pairs = [p for p in result['pairs'] if (p['launch'], p['endpoint']) in selected]
    (out / 'pairs.tsv').write_text(''.join(p['launch'] + '\t' + p['endpoint'] + '\n' for p in pairs))
    libraries = []
    for vt, groups in {'RVT': ('AO', 'OA', 'SIMPLE', 'INVBUF'),
                       'SLVT': ('AO', 'OA', 'SIMPLE', 'INVBUF', 'SEQ'),
                       'LVT': ('SIMPLE', 'INVBUF')}.items():
        for group in groups:
            suffix = ('220123.lib' if group == 'SEQ' else
                      '220122.lib.gz' if group == 'INVBUF' else '211120.lib.gz')
            libraries.append(root / 'test/asap7' / f'asap7sc7p5t_{group}_{vt}_FF_nldm_{suffix}')
    env = dict(os.environ, HW2_ROOT=str(root), HW2_LIBS='\n'.join(map(str, libraries)),
               HW2_PERIOD=str(result['period']), HW2_PAIRS=str(out / 'pairs.tsv'), HW2_OUT=str(out))
    (out / 'compare.tcl').write_text(SCRIPT)
    with (out / 'opensta.log').open('w') as log:
        subprocess.run([args.sta, '-no_init', '-exit', str(out / 'compare.tcl')], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    rows = []
    for index, pair in enumerate(pairs):
        native = {}
        for enabled in (0, 1):
            report = (out / f'pair_{index}_cppr_{enabled}.txt').read_text()
            checks = json.loads((out / f'pair_{index}_cppr_{enabled}.json').read_text())['checks']
            if len(checks) != 1 or checks[0]['startpoint'] != pair['launch'] or checks[0]['endpoint'] != pair['endpoint']:
                raise ValueError(f'native report did not select requested pair {index}')
            slack = re.search(r'([-+\d.eE]+)\s+slack \(', report)
            credit = re.search(r'([-+\d.eE]+)\s+([-+\d.eE]+)\s+clock reconvergence pessimism', report)
            if not slack or (enabled and not credit):
                raise ValueError(f'no native setup/CPPR report for pair {index}')
            native[enabled] = dict(slack=float(slack[1]), cppr=float(credit[1]) if credit else 0.0)
        native_common = None
        for launch, capture in zip(checks[0]['source_clock_path'], checks[0]['target_clock_path']):
            if launch['pin'] != capture['pin']:
                break
            native_common = launch['pin']
        row = dict(launch=pair['launch'], endpoint=pair['endpoint'],
                   common_pin=pair['common_pin'], native_common_pin=native_common,
                   scalar_cppr=pair['cppr'],
                   native_cppr=native[1]['cppr'],
                   native_slack_before=native[0]['slack'], native_slack_after=native[1]['slack'])
        row['credit_error'] = row['native_cppr'] - row['scalar_cppr']
        row['passed'] = (row['common_pin'] == native_common
                         and math.isclose(row['scalar_cppr'], row['native_cppr'], rel_tol=0, abs_tol=2e-8))
        rows.append(row)
    comparison = dict(period=result['period'], early_derate=0.9, late_derate=1.1,
                      changed_endpoint=example, pairs=rows)
    (out / 'comparison.json').write_text(json.dumps(comparison, indent=2, allow_nan=False) + '\n')
    for row in rows:
        print(f"{row['launch']} -> {row['endpoint']}: scalar={row['scalar_cppr']:.9f}, "
              f"OpenSTA={row['native_cppr']:.9f} ns, pass={row['passed']}")
    if not all(row['passed'] for row in rows):
        raise SystemExit('CPPR comparison failed; inspect native reports')


if __name__ == '__main__':
    main()
