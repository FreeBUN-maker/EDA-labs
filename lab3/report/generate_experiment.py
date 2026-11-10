#!/usr/bin/env python3
"""Create the measured part of the report; refuses missing or failed runs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent / 'handin' / 'hw3_run'


def read(name):
    return json.loads((RUN / name).read_text())


def main():
    p, f = read('macro_placement.json'), read('flow_report.json')
    a, e, s = read('partition_analysis.json'), read('environment.json'), read('search_config.json')
    assert f['pass'] and f['flow_exit'] == 0
    assert 'RESULT: PASS' in (RUN / 'check.log').read_text()
    names = sorted(p['macros'])
    ids = {name: i + 1 for i, name in enumerate(names)}
    module = lambda name: f'M_{{{ids[name]}}}'
    group = lambda members: r'\{' + ','.join(module(n) for n in members) + r'\}'
    rows = []
    for name in names:
        m = p['macros'][name]
        display = name.replace('\\', '')
        rows.append(f"${module(name)}$ & \\code{{{display}}} & {m['x']:.3f} & {m['y']:.3f} & {m['orient']} \\\\")
    coords = '\n'.join(rows)
    split_rows = '\n'.join(
        f"${group(split['a'])}$ & ${group(split['b'])}$ & "
        f"{split['area_a_um2']:,.3f} & {split['area_b_um2']:,.3f} & {split['cut']} \\\\"
        for split in a['balanced_splits'])
    incidence = '\n'.join(
        f"${group(g['macros'])}$ & {g['count']} \\\\"
        for g in a['incidence_groups'])
    P = ','.join(module(n) for n in p['positive_sequence'])
    N = ','.join(module(n) for n in p['negative_sequence'])
    reduction = 100 * (1 - f['ratio_to_baseline'])
    lo = f"{a['allowed_area_um2'][0]:,.4f}".replace(',', r'\,')
    hi = f"{a['allowed_area_um2'][1]:,.4f}".replace(',', r'\,')
    result = rf'''
\subsection{{实测环境与布局结果}}
本次使用 Docker 的 Linux/amd64 环境；OpenROAD 版本为
\code{{{e['openroad_version']}}}，Python 版本为 {e['runner_python'].split()[0]}。
ORFS 源码版本为 \code{{{e['orfs_revision'][:12]}}}。
容器固定到 \code{{openroad/orfs:26Q3-565-gef7fbfb0e}} 对应的镜像摘要，
完整摘要及命令见提交 README 和 \code{{environment.json}}。
实际读取到 {len(names)} 个宏、{a['net_count']} 条宏网络，核心区域为
$({p['core'][0]:.3f},{p['core'][1]:.3f})$ 至 $({p['core'][2]:.3f},{p['core'][3]:.3f})\,\mu$m。
退火参数为 seed={s['seed']}、{s['iters']:,} 次迭代，搜索耗时 {s['elapsed_s']:.1f} s。

\begin{{table}}[H]\centering
\caption{{实际运行指标。全设计 HPWL 来自 detailed\_placement 的 legalized HPWL。}}
\begin{{tabular}}{{lr}}
\toprule 指标 & 实测值 \\\midrule
宏网络 HPWL & {p['macro_hpwl_um']:,.3f} $\mu$m \\
打包宽度 $W$ / 高度 $H$（含外侧 halo） & {p['packed_width_um']:,.3f} / {p['packed_height_um']:,.3f} $\mu$m \\
详细布局后全设计 HPWL & {f['flow_hpwl_um']:,.1f} $\mu$m \\
题目提供的 RTLMP 基准 & {f['baseline_hpwl_um']:,.1f} $\mu$m \\
与题目基准之比 / 降低比例 & {f['ratio_to_baseline']:.6f} / {reduction:.3f}\% \\
验收门限 / checker 结果 & {f['threshold_um']:,.0f} $\mu$m / \textbf{{PASS}} \\\bottomrule
\end{{tabular}}
\end{{table}}
下游严格执行题目给定的 \code{{place_pins}}、密度 0.6 的 \code{{global_placement}}
及 \code{{detailed_placement}}。宏几何检查和最终检查均输出 \code{{RESULT: PASS}}。
这里的比值以题目固定的 738,243.9 $\mu$m 为分母；其标注的 OpenROAD 版本为
\code{{26Q3-1510-g6cb3f2b704}}，与本次工具版本存在差异，因此不将这一比值解释为严格同版本的算法对比。

\begin{{figure}}[H]\centering
\includegraphics[height=9.2cm]{{asset/macro_floorplan.pdf}}
\caption{{输出的宏布局。外框为核心区，矩形为实际宏边界；编号和坐标见下页。}}
\end{{figure}}
最优序列为 $P=({P})$，$N=({N})$。

\clearpage
\subsection{{宏坐标与面积平衡划分}}
\begin{{table}}[H]\centering\small
\caption{{写入 JSON/Tcl 的位置与朝向，单位为 $\mu$m。实际 ODB 名称中的方括号转义由程序保留。}}
\begin{{tabular}}{{clrrc}}
\toprule 编号 & 实例（此处省略反斜杠转义） & $x$ & $y$ & 朝向 \\\midrule
{coords}
\bottomrule
\end{{tabular}}
\end{{table}}
每个 RAM 的面积为 $1,514,187.0492\,\mu\mathrm{{m}}^2$；
Cache、APB、Ibex 的面积依次为 $238,566$、$313,663$、$480,000\,\mu\mathrm{{m}}^2$。
总面积 $A={a['total_area_um2']:,.4f}\,\mu\mathrm{{m}}^2$。
“在一半面积的 $\pm10\%$ 内”对应每块面积落在 $[0.45A,0.55A]$，即
\[
[{lo},\ {hi}]\,\mu\mathrm{{m}}^2.
\]
固定一个宏在块 A 中可消除互补重复；穷举 $2^{{6-1}}-1=31$ 个非空无序划分，
恰有下表 3 种满足平衡约束。每条跨块宏网络只计一次。
\begin{{table}}[H]\centering\small
\caption{{全部合法无序二分；交换块 A/B 不形成新划分。}}
\begin{{tabular}}{{ccrrc}}
\toprule 块 A & 块 B & A 面积 & B 面积 & cut \\\midrule
{split_rows}
\bottomrule
\end{{tabular}}
\end{{table}}
证明其完备性：无 RAM 的三个小宏总面积只有 $1,032,229$，不足下界；
三个 RAM 同块则超过上界。两个 RAM 的面积为 $3,028,374.0984$，
即使再加最小的 Cache 也会超过上界。因此一块必须恰含两个 RAM，另一块包含剩余 RAM 和全部小宏，
只有选择哪一个 RAM 单独与小宏同块这 3 种可能。两块相对半总面积的偏差均约为 $8.65\%$。

对真实 ODB 中的网络按其涉及的宏集合分组，得到：
\begin{{center}}
\begin{{tabular}}{{lc}}
\toprule 宏集合 & 网络数 \\\midrule
{incidence}
\bottomrule
\end{{tabular}}
\end{{center}}
三种平衡划分都分开三个 RAM，因此 46 条 RAM 共用网络全部跨块；
连接全部宏的 1 条网络也跨块；其余 $25+55=80$ 条网络只涉及三个小宏，它们始终同块。
故每个平衡划分的 cut 都等于 $46+1=47$，此平衡约束下无法进一步降低。

\clearpage
\subsection{{代价函数的一个具体局限}}
宏 HPWL 只统计至少含两个宏引脚的网络，会遗漏宏到标准单元或外部端点的连线；
对全部宏作相同平移，宏间 HPWL 不变，但这些被遗漏的线长可能明显变化。
下面用一个完全可计算的小例子说明：两个 $10\times10$ 宏只有一个中心引脚，
核心区为 $[0,200]\times[0,100]$，两宏左下角原为 $(5,5)$、$(50,5)$，间距恰为 $35$。
网络 $e_1$ 连接两个宏引脚，网络 $e_2$ 连接第一个宏引脚与固定端点 $(150,10)$。
将两个宏整体右移 80 后仍合法，得到：
\begin{{center}}
\begin{{tabular}}{{lccc}}
\toprule 布局 & $e_1$（宏代价） & $e_2$（被忽略） & 全部网络之和 \\\midrule
左下角 $(5,5),(50,5)$ & 45 & 140 & 185 \\
左下角 $(85,5),(130,5)$ & 45 & 60 & 105 \\\bottomrule
\end{{tabular}}
\end{{center}}
两者宏 HPWL 同为 45，宏集合的外包宽高也相同，但总 HPWL 相差 80。
当前最长路径打包固定在左下角，输出仅加固定 $5\,\mu$m 边界偏移，
因此既没有代价信息，也没有整体平移扰动来选择后者。
这里的固定端点是用于证明局限的简化外部引脚，并非将该数值当作 chameleon 的实测性能。

一种改进是从 ODB 纳入宏到标准单元/端口的网络，结合外部引脚的当前位置估计线长，
并加入合法的整体平移或局部松弛；不过标准单元还会在后续布局中移动，
因此最终仍须以详细布局后的全设计 HPWL 为验收依据。
本次采用题目要求的宏 HPWL 目标，并用完整下游流程验证所得解。

\subsection{{运行产物}}
\code{{hw3_run/}} 保存 \code{{macro_placement.json/.tcl}}、
\code{{flow_report.json}}、\code{{student.log}}、\code{{flow.log}}、
两份 checker 日志、\code{{partition_analysis.json}}、\code{{search_config.json}} 以及环境记录。
\code{{3_2_place_custom.odb}} 可由同一命令重新生成。
所有表格由这些文件自动提取；原始数据副本保存在报告的 \code{{asset/}} 目录。
'''
    (ROOT / 'asset' / 'experiment.tex').write_text(result)
    for name in ['macro_placement.json', 'flow_report.json', 'partition_analysis.json',
                 'search_config.json', 'environment.json']:
        (ROOT / 'asset' / name).write_text((RUN / name).read_text())


if __name__ == '__main__':
    main()
