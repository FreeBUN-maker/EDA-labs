# HW2：STA 与 CPPR（2300012831）

已实现题目规定的七个函数，`run_hw2.py` 保持原始版本。核心算法和测试只需要 Python 3 标准库；读取真实电路及原生对照需要 OpenSTA 和 OpenROAD 源码中的测试输入，不需要编译 OpenROAD。

## 文件

- `sta.py`：拓扑排序、时钟传播、逐起点 AT、基准 RAT、CPPR、端点统计与关键路径回溯。
- `test_sta.py`：14 项测试，其中一项对 100 个固定随机种子的 DAG 穷举路径核验。
- `compare_opensta.py`：独立调用 OpenSTA，以相同周期和 derate 验证三对路径的 credit 与公共时钟引脚。
- `export_report.py`：从实测结果导出全部 pair/endpoint 的 CSV 和报告中的数值表。
- `run_gcd/`：本次运行结果、完整逐节点时序、全部 pair 明细、测试日志及 OpenSTA 原生报告。
- `../report/lab2_report.tex`、`../report/asset/`：报告源码、从原题裁取的图片和自动生成的表格。

## 在当前工作区运行

从仓库根目录执行：

```sh
cd lab2/HW2_STA
export OPENROAD_ROOT="$(cd ../../OpenROAD-flow-scripts/tools/OpenROAD && pwd)"
export STA="/Users/tongbinzhao/Desktop/Tools/opensta-env/bin/sta"
python3 -m unittest -v
python3 run_hw2.py --openroad-root "$OPENROAD_ROOT" --sta "$STA" --period 0.28 --out run_gcd
python3 compare_opensta.py --openroad-root "$OPENROAD_ROOT" --sta "$STA" --results run_gcd/result.json --out run_gcd/native
python3 export_report.py --run run_gcd --assets ../report/asset
```

在其他机器上，将 `OPENROAD_ROOT` 设置为 OpenROAD 源码目录（不是 OpenROAD-flow-scripts 根目录），将 `STA` 设置为独立 OpenSTA 可执行文件的完整路径。若解压提交包，则在 `src/` 下执行上面四条 Python 命令，另行设置这两个环境变量。建议使用下列同一输入版本以复现最后几位小数：

- OpenROAD：`41a28926b92c5c20f41f89e90222a95a820384d2`
- 其 OpenSTA 子模块：`779d47250b65b121ad22c70eb42e242292f9babf`（版本 3.1.0）
- 本次 Python：系统 Python 3；精确版本及系统信息保存在 `run_gcd/environment.json`。

如需从干净源码准备指定输入，先克隆 OpenROAD 官方仓库，检出上述提交，再初始化子模块；依照该版本 `src/sta/README.md` 构建独立 OpenSTA 即可。本次 OpenSTA 的二进制和运行库位于 `/Users/tongbinzhao/Desktop/Tools/opensta-env/`，没有修改上游源码。

## 实测结果（ns）

| 指标 | CPPR 前 | CPPR 后 |
|---|---:|---:|
| WNS | -0.012235756 | -0.008608215 |
| TNS | -0.056881131 | -0.019221813 |
| 负 slack 端点数 | 9 | 3 |

数据图有 1221 个节点、70 个起点、35 个 FF 端点；时钟树有 46 个节点。全部 1199 个可达起点—端点对见 `run_gcd/pairs.csv` 或 `result.json` 的 `pairs`，其中包含 AT、修正前后 RAT/slack、CPPR 与公共引脚。全部端点汇总见 `endpoints.csv`。10 个端点在 CPPR 后更换最坏起点，报告详述其中一个例子。

全局关键路径前后均为 `dpath.a_reg.out[13]$_DFFE_PP_/QN` 到 `dpath.a_reg.out[7]$_DFFE_PP_/D`；完整引脚序列保存在 `result.json` 的 `before/after.critical_path`。

原生 OpenSTA 对照见 `run_gcd/native/comparison.json`，三对路径的 credit 和最后公共时钟引脚均匹配，最大绝对误差约 `1.67e-9 ns`（断言门限 `2e-8 ns`）。`pair_*_cppr_0/1.txt` 保存 CPPR 关闭/开启时的完整原生时序报告。这里比较的是 CPPR credit，不能把原生 slack 当作本题标量模型的结果：原生 STA 保持 rise/fall 跃迁一致性，而作业 reader 对数据弧逐级取最大，并采用简化 PI/端点约束。

`node_timing.json` 中数据 ID 是排序后的引脚名索引，不是拓扑位置；与 runner 接口一致。节点的不可达 AT/前驱为 `null`；无约束基准 RAT 序列化为 `null`。WNS 定义为 `min(0, minimum_endpoint_slack)`；TNS 对每个 FF 端点只累加一次负 slack。

原始输入带有 Liberty Warning 1212、TAPCELL 物理黑盒和对时钟端口设置 input delay 的警告，保留在 `opensta.log`。它们没有阻止 reader 或独立对照完成。

## 编译报告：仅使用最小 XeLaTeX

按要求，在 `/Users/tongbinzhao/Desktop/Tools/TinyTeX/` 安装了 TinyTeX-0 基础设施，按需加入 **XeTeX 引擎**、中文字体和本报告宏包，没有安装 pdfTeX/LuaTeX 引擎或完整 TeX Live。安装时关闭了文档包与源码包；依赖按 XeLaTeX 实际需求选择。

从 `HW2_STA/`（提交包中为 `src/`）执行：

```sh
cd ../report
/Users/tongbinzhao/Desktop/Tools/TinyTeX/bin/universal-darwin/xelatex -interaction=nonstopmode -halt-on-error lab2_report.tex
/Users/tongbinzhao/Desktop/Tools/TinyTeX/bin/universal-darwin/xelatex -interaction=nonstopmode -halt-on-error lab2_report.tex
```

生成 `lab2_report.pdf`。两次编译用于稳定目录书签、图片编号和 PDF 页面标签。其他机器可使用已有 XeLaTeX；若自行准备最小环境，可参考 [TinyTeX 官方发布说明](https://github.com/rstudio/tinytex-releases)，从 TinyTeX-0 开始按需安装，避免安装完整方案。

## 提交包

`../hw2-2300012831.zip` 包含 `hw2-2300012831.pdf`、`src/`、根目录 `README.md`，并额外附带 `report/` 以便复编译。`src/run_gcd/` 包含完整结果及原生 OpenSTA 对照证据。无需将本机工具安装目录或 OpenROAD 源码一并提交。

AI 辅助范围已如实写入报告附录，包括推导、代码、测试、结果整理和排版。
