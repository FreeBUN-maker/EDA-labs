# HW2：STA

## 文件

- `src/sta.py`：拓扑排序、时钟传播、逐起点 AT、基准 RAT、CPPR、端点统计与关键路径回溯。
- `src/run_hw2.py`：作业提供的输入读取与结果输出脚本。
- `src/compare_opensta.py`：独立调用 OpenSTA，以相同周期和 derate 验证三对路径的 credit 与公共时钟引脚。
- `run_gcd/`：运行后生成的完整逐节点时序、全部 pair 明细及 OpenSTA 原生报告。
- `hw2-2300012831.pdf`：实验报告pdf.

## 复现实验结果

从包含 `src` 的目录执行：

```sh
export OPENROAD_ROOT="path/to/OpenROAD"
export STA="path/to/opensta"
python3 src/run_hw2.py --openroad-root "$OPENROAD_ROOT" --sta "$STA" --period 0.28 --out run_gcd
python3 src/compare_opensta.py --openroad-root "$OPENROAD_ROOT" --sta "$STA" --results run_gcd/result.json --out run_gcd/native
```

运行时，将 `OPENROAD_ROOT` 设置为 OpenROAD 源码目录，将 `STA` 设置为独立 OpenSTA 可执行文件的完整路径。

## 实测结果（ns）

| 指标 | CPPR 前 | CPPR 后 |
|---|---:|---:|
| WNS | -0.012235756 | -0.008608215 |
| TNS | -0.056881131 | -0.019221813 |
| 负 slack 端点数 | 9 | 3 |

数据图有 1221 个节点、70 个起点、35 个 FF 端点；时钟树有 46 个节点。全部 1199 个可达起点—端点对见 `run_gcd/result.json` 的 `pairs`，其中包含 AT、修正前后 RAT/slack、CPPR 与公共引脚。全部端点汇总见同一文件的 `endpoints`。10 个端点在 CPPR 后更换最坏起点，报告详述其中一个例子。

全局关键路径前后均为 `dpath.a_reg.out[13]$_DFFE_PP_/QN` 到 `dpath.a_reg.out[7]$_DFFE_PP_/D`；完整引脚序列保存在 `result.json` 的 `before/after.critical_path`。

原生 OpenSTA 对照见 `run_gcd/native/comparison.json`，三对路径的 credit 和最后公共时钟引脚均匹配，最大绝对误差约 `1.67e-9 ns`（断言门限 `2e-8 ns`）。`pair_*_cppr_0/1.txt` 保存 CPPR 关闭/开启时的完整原生时序报告。这里比较的是 CPPR credit，不能把原生 slack 当作本题标量模型的结果：原生 STA 保持 rise/fall 跃迁一致性，而作业 reader 对数据弧逐级取最大，并采用简化 PI/端点约束。

`node_timing.json` 中数据 ID 是排序后的引脚名索引，不是拓扑位置；与 runner 接口一致。节点的不可达 AT/前驱为 `null`；无约束基准 RAT 序列化为 `null`。WNS 定义为 `min(0, minimum_endpoint_slack)`；TNS 对每个 FF 端点只累加一次负 slack。

原始输入带有 Liberty Warning 1212、TAPCELL 物理黑盒和对时钟端口设置 input delay 的警告，保留在 `opensta.log`。它们没有阻止 reader 或独立对照完成。
