# HW3：Partition and Floorplan

学号：2300012831。所有命令从本目录（包含 `src/`）执行；运行路径均相对当前目录解析，重命名外层目录不影响程序。

## 目录结构

- `hw3-2300012831.pdf`：实验报告，回答问题 1–3。
- `src/hw3.py`：从 ODB 读取数据、O(n²) 序列对打包、四朝向宏引脚 HPWL、模拟退火及平衡划分穷举。
- `src/run_hw3.py`：题目 runner，完成输入生成、学生程序、下游布局和 checker；补充相对路径解析、超时日志解码及环境记录。
- `src/check.py`、`src/baseline.json`、`src/fixtures/`：原版验收程序和数据。学生算法不读取 fixture。
- `src/solve_theory.py`：问题 1 的精确分数计算和问题 2 的约束图、相对关系与最小布局计算。
- `src/test_hw3.py`：不依赖 OpenROAD 的算法测试。
- `src/run_docker.sh`：固定历史镜像的完整运行入口。
- `src/reference_results/`：此次通过验收的 JSON、日志和理论计算结果，供核对；不作为算法输入。

运行后生成 `hw3_run/`，包含宏布局 JSON/Tcl、最终 ODB、两次 checker 日志、完整 OpenROAD 日志、性能统计、面积平衡分析和环境记录。报告 LaTeX 源码及编译说明不属于提交包。

## 复现理论题和算法检查

需要 Python 3.9 或更新版本，无第三方 Python 依赖：

```sh
python3 src/solve_theory.py --out theory_results.json
python3 -m unittest discover -s src -p 'test_*.py'
```

预期：KL 保留前缀 1，FM 保留前缀 2，最终块 0 均为 `{a,b,c,g}`；BFS 路径为 `a-b-d-h`，瓶颈 `1/3`；问题 2 的 `W=11, H=15, area=165`；7 项测试全部通过。

`theory_results.json` 记录全部边权、每步未锁单元的 D/增益、所选交换或移动、累计增益与割、完整约束边、相对位置和坐标。集合按字典序输出，分数用字符串保存以避免精度损失。

## 本次实际使用的环境与完整运行命令

宿主机为 macOS/Apple Silicon，使用 Docker 的 `linux/amd64` 环境。ORFS 路径为本目录下的 **`../../OpenROAD-flow-scripts`**，源码提交为 `5b87982c613347c3ce03341648654f1e8a8f040e`；容器内实际 ORFS 路径为 `/OpenROAD-flow-scripts`。

镜像为 `openroad/orfs:26Q3-565-gef7fbfb0e`，脚本固定其 amd64 manifest：

```text
sha256:d031d85bcf8992f59a693fd3586d0113a5c2f5f79edc54b46dbadcbe47d98b74
```

使用本仓库布局时，实际运行命令为：

```sh
bash src/run_docker.sh ../../OpenROAD-flow-scripts \
  --seed 0 --iters 100000 --workdir hw3_run
```

单独解压提交包时，把第一个参数替换为已有 ORFS checkout 的路径。脚本挂载该 checkout 的 `flow/`，复用镜像内工具，固定 floorplan 阶段 `NUM_CORES=4`；如果缺少输入 ODB，runner 自动执行 `make floorplan`。第一次运行需要下载镜像。该历史镜像保留作业要求的 `openroad -python` 接口；较新版本已移除此入口。

## 已有原生 OpenROAD 的等价命令

使用支持 `-python` 且启用 Python/ODB 的 OpenROAD 安装，从本目录执行：

```sh
export ORFS_ROOT=../../OpenROAD-flow-scripts
python3 src/run_hw3.py --orfs-root "$ORFS_ROOT" \
  --seed 0 --iters 100000 --workdir hw3_run
```

如二进制不在 `$ORFS_ROOT/tools/install/OpenROAD/bin/openroad`，添加 `--openroad /path/to/openroad`，并确保 ORFS floorplan 所需工具也在 PATH 中。学生入口默认就是 `src/hw3.py`，无需额外指定 `--student`。

runner 的下游命令保持题目要求：

```tcl
place_pins -hor_layers met3 -ver_layers met2
global_placement -density 0.6
detailed_placement
```

仅重跑原版 checker：

```sh
python3 src/check.py \
  --macro-data src/fixtures/chameleon_macro_data.json \
  --placement hw3_run/macro_placement.json \
  --flow-report hw3_run/flow_report.json \
  --baseline src/baseline.json
```

## 实现说明

本次实际 OpenROAD 版本为 **26Q3-1985-gc3e680b01b**。seed=0、100,000 次退火迭代得到：

| 指标 | 实测值 |
|---|---:|
| 宏网络 HPWL | 102,840.185 µm |
| 打包宽度 × 高度（含右/上 halo） | 2,249.690 × 2,994.360 µm |
| 详细布局后全设计 HPWL | 647,866.4 µm |
| 题目 RTLMP 基准 | 738,243.9 µm |
| 与题目基准之比 | 0.877578 |
| 相对题目基准降低 | 12.242% |
| 原版 checker | RESULT: PASS |

运行中读取到 6 个宏、127 条宏网络，核心区域与题目一致。宏几何门限和最终 HPWL 门限均通过。比较分母是题目固定基准，其工具版本标注为 `26Q3-1510-g6cb3f2b704`，所以该比值不是同版本下的独立 RTLMP 对照实验。原版 checker、baseline 和 fixture 未修改。

`pack()` 显式构建水平、垂直 DAG，以 P 为共同拓扑序。边权为源模块宽/高加 35 µm；返回宽高包含最右/最上侧 halo，输出位置整体加核心左下角和 5 µm 边界偏移。允许的四朝向不交换宽高。

`macro_hpwl()` 使用主单元 R0 引脚中心，按 R0/MX/MY/R180 变换后求各宏网络包围盒半周长。退火主代价为宏 HPWL 加越界惩罚，面积仅在主代价相同时破同分。输出还保存最佳 P/N、seed、迭代数和运行时间。

平衡划分要求每块面积在总面积的 45%–55% 内。程序从实际 ODB 的网络与宏面积枚举全部 31 种无序非空二分，3 种满足面积限制，cut 均为 47；结果及网络分组保存在 `partition_analysis.json`。

报告中的相对位置表使用题目原表含义：第 i 行的 Left-of/Below 分别表示“i 在哪些模块的左侧/下方”。
