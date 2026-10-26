#!/usr/bin/env python3
"""Export complete CSV tables and reproducible LaTeX tables from actual results."""
import argparse
import csv
import json
from pathlib import Path


def code(value):
    return r'\code{' + str(value) + '}'


def table(headers, rows, widths=None):
    spec = widths or ('l' + 'r' * (len(headers) - 1))
    lines = [r'\begin{center}\small', r'\begin{tabular}{' + spec + '}', r'\toprule',
             ' & '.join(headers) + r' \\', r'\midrule']
    lines += [' & '.join(map(str, row)) + r' \\' for row in rows]
    return '\n'.join(lines + [r'\bottomrule', r'\end{tabular}', r'\end{center}']) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, default=Path('run_gcd'))
    ap.add_argument('--assets', type=Path, default=Path('../report/asset'))
    args = ap.parse_args()
    run, assets = args.run, args.assets
    assets.mkdir(parents=True, exist_ok=True)
    r = json.loads((run / 'result.json').read_text())
    t = json.loads((run / 'node_timing.json').read_text())
    comparison = json.loads((run / 'native/comparison.json').read_text())
    for name in ['pairs', 'endpoints']:
        with (run / f'{name}.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(r[name][0]))
            writer.writeheader()
            writer.writerows(r[name])
    changed = [e for e in r['endpoints'] if e['before_launch'] != e['after_launch']]
    metadata = dict(data_nodes=len(t['order']), clock_nodes=len(t['clock']),
                    launches=len(t['launches']), endpoints=len(r['endpoints']),
                    reachable_pairs=len(r['pairs']), changed_endpoints=len(changed))
    (run / 'summary.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (assets / 'graph_counts.tex').write_text(
        f"实际读入 {metadata['data_nodes']} 个数据节点、{metadata['clock_nodes']} 个时钟节点、"
        f"{metadata['launches']} 个数据起点（包括 FF 输出、PI 与 tie）、"
        f"{metadata['endpoints']} 个 FF 数据端点，共有 {metadata['reachable_pairs']} 个可达起点--端点对。"
        f"CPPR 后共有 {len(changed)} 个端点的最坏起点发生变化。\n")
    rows = []
    for label, key in [('WNS / ns', 'wns'), ('TNS / ns', 'tns'),
                       ('关键路径 AT / ns', 'arrival'), ('关键路径 RAT / ns', 'required')]:
        rows.append([label] + [f"{r[m][key]:.9f}" for m in ('before', 'after')])
    rows.append(['负 slack 端点数'] + [sum(e[m + '_slack'] < 0 for e in r['endpoints'])
                                   for m in ('before', 'after')])
    (assets / 'metrics.tex').write_text(table(['指标', 'CPPR 前', 'CPPR 后'], rows))
    path_text = []
    for mode, title in [('before', 'CPPR 前'), ('after', 'CPPR 后')]:
        path = r[mode]['critical_path']
        path_text += [title + '：' + code(path[0]) + r' $\longrightarrow$ ' + code(path[-1]) + '。\n\n']
    path_text += ['两次全局最坏路径在本例中相同，完整的数据引脚序列如下：\n',
                  r'\begin{lstlisting}[style=script,language={},numbers=none]' + '\n']
    path = r['before']['critical_path']
    path_text += [path[0] + '\n']
    for i in range(1, len(path) - 1, 2):
        path_text.append(' -> ' + path[i] + ' -> ' + path[i + 1] + '\n')
    path_text += [' -> ' + path[-1] + '\n', r'\end{lstlisting}' + '\n']
    (assets / 'critical_path.tex').write_text(''.join(path_text))
    example = comparison['changed_endpoint']
    pairs = [p for p in r['pairs'] if p['endpoint'] == example['endpoint']
             and p['launch'] in [example['before_launch'], example['after_launch']]]
    definitions = ['端点为 ' + code(example['endpoint']) + '，记两个候选起点为：\n',
                   r'\begin{itemize}' + '\n']
    for label, pair in zip(['L1', 'L2'], pairs):
        definitions.append(r'\item ' + label + '：' + code(pair['launch']) + '。\n')
    definitions.append(r'\end{itemize}' + '\n')
    definitions.append(table(['起点', 'AT / ns', 'slack 前 / ns', 'CPPR / ns', 'slack 后 / ns'],
                             [[label] + [f'{p[k]:.9f}' for k in ['arrival', 'slack_before', 'cppr', 'slack_after']]
                              for label, p in zip(['L1', 'L2'], pairs)]))
    definitions += ['L1 的公共时钟引脚为 ' + code(pairs[0]['common_pin']) + '；L2 的公共时钟引脚为 '
                    + code(pairs[1]['common_pin']) + '。\n']
    (assets / 'launch_change.tex').write_text(''.join(definitions))
    native = ['所比较的三对路径为：\n', r'\begin{itemize}' + '\n']
    for i, pair in enumerate(comparison['pairs'], 1):
        native.append(r'\item P' + str(i) + '：' + code(pair['launch']) + r' $\to$ ' + code(pair['endpoint']) + '。\n')
    native.append(r'\end{itemize}' + '\n')
    native.append(table(['路径', '本实现 CPPR / ns', 'OpenSTA CPPR / ns', '绝对误差 / ns'],
                        [[f'P{i}', f"{p['scalar_cppr']:.9f}", f"{p['native_cppr']:.9f}",
                          f"{abs(p['credit_error']):.2e}"] for i, p in enumerate(comparison['pairs'], 1)]))
    (assets / 'native_comparison.tex').write_text(''.join(native))
    print(f"Exported {len(r['pairs'])} pairs, {len(r['endpoints'])} endpoints and report tables.")


if __name__ == '__main__':
    main()
