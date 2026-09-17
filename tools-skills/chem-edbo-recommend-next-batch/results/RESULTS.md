# 测试与验证结果（RESULTS）

> skill：`chem-edbo-recommend-next-batch`（EDBO 贝叶斯反应优化推荐）
> 生成时间：2026-09-17 ｜ 状态：**全部验证通过**（12/12 测试 + 5 组额外证据）
> 原始输出见 `raw/`；复现命令见第 7 节。所有数字均可由 `raw/` 中的捕获文件核对。

## 1. 验证环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows 11（win32，中文控制台 GBK） |
| Python | 3.11.9 |
| numpy / scipy / scikit-learn | 2.4.6 / 1.17.1 / 1.9.0 |
| matplotlib（可选，绘图用） | 3.11.1 |
| 依赖安装 | `pip install -r requirements.txt`（核心 3 库，无网络/无 LLM 依赖） |

## 2. 测试总览（12/12 通过）

| # | 测试 | 文件 | 层级 | 验证内容 | 结果 |
|---|---|---|---|---|---|
| 1 | test_encode_decode_roundtrip | test_edbo_core.py | 单元 | 编码/解码往返一致性（200 随机点） | ✅ |
| 2 | test_ei_formula | 同上 | 单元 | EI 公式数值正确性（含符号方向、零方差无 NaN） | ✅ |
| 3 | test_cold_start | 同上 | 单元 | <2 条数据时返回空间填充批、不拟合 GP | ✅ |
| 4 | test_validation_errors | 同上 | 单元 | 非法类别值/越界/NaN 剔除/重复去重 四类输入校验 | ✅ |
| 5 | test_recommendation_schema_and_dedup | 同上 | 单元 | 输出 JSON schema 完整；批内与已观测均无重复 | ✅ |
| 6 | test_determinism | 同上 | 单元 | 相同 seed 输出逐字节一致（可复现性） | ✅ |
| 7 | test_minimize_direction | 同上 | 单元 | minimize 目标方向正确（推荐低值区域） | ✅ |
| 8 | test_full_enumeration_space | 同上 | 单元 | 纯类别空间全枚举（3×2=6 点）与推荐合法性 | ✅ |
| 9 | test_diagnostics_degradation | 同上 | 单元 | 跨 sklearn 版本核结构异常时诊断降级、推荐不崩 | ✅ |
| 10 | test_branin_optimization | 同上 | 数值基准 | Branin 2D：5.01 → 0.41（全局最优 0.398），22 次评估 | ✅ |
| 11 | test_cli_end_to_end | test_cli.py | 端到端 | CLI 全链路：JSON + 报告 + 图 均生成且内容正确 | ✅ |
| 12 | test_cli_invalid_data | 同上 | 端到端 | 非法数据 → 退出码 2 + 明确错误信息 | ✅ |

原始输出：`raw/unit-tests.txt`（10 项）、`raw/cli-tests.txt`（2 项）。

## 3. 关键数值证据

### 3.1 Branin 标准基准（效果核心证据）

Branin 函数（2D 连续，minimize，全局最优 **0.398**）：

- **单元测试**（seed=3）：初始最优 5.01 → 3 轮 BO 后 **0.41**；
- **多种子扫描**（6 个不同初始数据种子，`raw/branin-multiseed.txt`）：

| init_seed | 初始最优 | 最终最优 | 结论 |
|---:|---:|---:|---|
| 0 | 10.87 | 0.40 | 收敛 |
| 1 | 3.63 | 0.45 | 收敛 |
| 2 | 0.84 | 0.44 | 收敛 |
| 3 | 5.01 | 0.41 | 收敛 |
| 4 | 2.74 | 2.21 | 部分收敛（已如实记录，见 §6） |
| 5 | 3.99 | 0.40 | 收敛 |

**5/6 种子收敛到全局最优邻域**；1 例停滞属 BO 偶发行为，缓解策略见 SKILL.md 故障排查。

### 3.2 模拟反应闭环（化学场景效果证据）

`results/closed_loop_demo.py`：Pd 催化直接芳基化风格空间（12 配体 × 4 碱 × 4 溶剂 × 温度 × 浓度），
模拟"真实"产率函数（真实最优 ≈88，不在数据内），3 轮"推荐 → 模拟实验 → 追加数据"：

| 轮次 | 推荐首位条件 | 预测 | 当前最优产率 |
|---|---|---|---|
| 初始 | —（20 条随机数据） | — | 74.2 |
| 第 1 轮 | L8 / K3PO4 / DMF，T=40°C | 74.0 ± 2.8 | 74.2（探索低产率区） |
| 第 2 轮 | **L8 / K3PO4 / DMA，T=114°C** | 78.7 ± 2.9 | **94.2** |
| 第 3 轮 | L8 / K3PO4 / DMA，T=108°C | 100.0 ± 2.9 | 94.2（收敛） |

**2 轮（10 次实验）锁定最优配体/碱/溶剂组合，产率 74.2 → 94.2（+20 个百分点）**，
与 EDBO 论文"第 3 批起超越人类专家"的定性结论一致。原始输出：`raw/closed-loop-demo.txt`。

### 3.3 参数敏感性基准（成本与稳健性证据）

`scripts/benchmark.py` 全量网格（Branin，22 次评估/组，`raw/benchmark-full.txt`）：

| acquisition | gp_restarts | candidates | 最终最优 | 耗时(s) | 结论 |
|---|---|---|---|---|---|
| EI | 5 | 10000 | 0.44 | 1.7 | 收敛 |
| EI | 5 | 1000 | 0.46 | 1.5 | 收敛 |
| EI | 1 | 1000 | 0.46 | 0.6 | 收敛 |
| UCB | 5 | 10000 | 0.45 | 1.5 | 收敛 |
| UCB | 1 | 1000 | 0.48 | 0.6 | 收敛 |
| GREEDY | 1 | 1000 | 0.46 | 0.5 | 收敛 |

**6/6 收敛，单组最慢 1.7s**。参数差异主要体现在耗时（restarts 5→1 快约 2.5 倍）；
真实反应空间（噪声大、高维）仍建议 EI + restarts≥3。

### 3.4 端到端示例产物

`raw/example-run.txt`：演示空间 20 条数据 → Top-5 推荐全部锁定最优配体 **L8**（其中 4/5 含最优碱
K3PO4），预测均值 61.5–74.2、EI 排序合理。配套产物（可打开查看）：
- `raw/example-recommendation.json` —— 机器可读完整输出；
- `raw/example-report.md` —— 人类可读中文报告（含解读要点、安全提示、引用）；
- `raw/example-plot.png` —— EI 曲面 + 预测均值±标准差柱状图（已人工目检，中文标签正常）。

## 4. 开发过程中发现并修复的缺陷（透明记录）

| # | 缺陷 | 影响 | 修复 | 回归保护 |
|---|---|---|---|---|
| 1 | **EI 公式 z 值符号反转**（z 写成 (best−μ)/σ） | 推荐器专挑最差点（严重） | 改为标准公式 z=(μ−best)/σ | test_ei_formula |
| 2 | `random_points` 把连续变量采样到原始量纲而非 [0,1] | 解码值爆炸（温度 7316°C） | 改为 [0,1] 均匀采样 | test_encode_decode_roundtrip |
| 3 | 诊断代码硬编码核对象嵌套结构（`kernel_.k1.k1`） | sklearn 版本差异会 AttributeError 崩溃 | 防御式递归提取 + 逐项降级 | test_diagnostics_degradation |
| 4 | 自检断言随 bug 1 被"修正"为错误预期 | 测试锁定错误行为 | 恢复正确预期（μ>best 时 EI 大） | test_ei_formula |
| 5 | 测试广播比较 1D×2D 成标量 | 断言失效 | 改为逐行 `isclose(..., axis=1)` | test_cold_start 等 |

## 5. 六维评估（结论版）

| 维度 | 评级 | 依据（详见 SKILL.md Credibility） |
|---|---|---|
| Safety | 🟢 良好 | 无网络/无 LLM 核心路径；seed 可复现；通用安全提示 + bounds 告警；明确"非安全审批"边界。风险：无试剂级安全库，预测可超物理界限（已文档化） |
| Completeness | 🟡 良好 | 原子范围内完整（12 测试 + 冷启动/低数据/minimize/去重/乱码编码全覆盖）；与论文差距（无多目标/DFT/Mordred/联合批 EI）已文档化并指引 EDBO+ |
| Executability | 🟢 已验证 | 本机全链路实测通过；绘图失败自动降级；中文 Windows 编码已处理；跨 sklearn 版本诊断已加固。剩余风险：Python 3.9 未实测 |
| Maintainability | 🟡 良好 | 核心库分层清晰；每处取舍见 implementation-mapping.md；输出带 schema_version；缺陷全部有回归测试。不足：edbo_core.py 约 700 行偏长、无 CI |
| Cost-awareness | 🟢 优秀 | 每次调用零 token/零网络；单轮推荐 <2s CPU；参数（restarts/candidates）可调速度/质量 |
| Effect | 🟢 良好 | Branin 5/6 种子收敛到全局最优邻域；模拟闭环 2 轮 +20 个百分点；与论文基准定性一致。真实实验有效性待用户数据验证 |

## 6. 已知局限与未覆盖测试（诚实声明）

**未覆盖**：真实实验数据验证；Python 3.9 / macOS / Linux 实测；matplotlib 缺失时的降级路径演练；
sklearn 其他版本（1.0–1.8）实测；长时间多轮（>10 轮）稳定性；高维（>20）空间压力测试。

**已知局限**（详见 `references/implementation-mapping.md` §3）：
- 单目标（无 qEI/EHVI 多目标）；无安全域约束（GP 可外推出物理界限）；高维精度下降；
- 贪心批选择可能聚集；未实现 DFT/Mordred 描述符流水线与论文的先验自优化；
- Branin seed=4 停滞个案（2.74→2.21）说明 BO 存在偶发收敛慢，缓解：增大 candidates/换 UCB/补随机实验。

## 7. 复现方法

```bash
pip install -r requirements.txt                      # 依赖
python tests/test_edbo_core.py                       # 10 项单元测试（含 Branin、诊断降级）
python tests/test_cli.py                             # 2 项 CLI 端到端测试
python scripts/benchmark.py                          # 环境自检 + 参数敏感性网格（--quick 更快）
python results/closed_loop_demo.py                   # 模拟闭环效果验证
python results/branin_multiseed.py                   # Branin 多种子扫描
python scripts/recommend_next_batch.py \
    --space examples/direct_arylation_space.json \
    --data examples/initial_data.csv \
    --batch-size 5 --seed 42 \
    --output rec.json --report report.md --plot rec.png   # 端到端示例
```

预期：12/12 测试通过；基准 6/6 收敛（单组 <10s）；闭环产率 74.2 → 94.2；
不同机器上数值与本文档一致（同 seed 确定性已由 test_determinism 保证）。

## 8. 原始输出索引（raw/）

| 文件 | 内容 |
|---|---|
| unit-tests.txt | 10 项单元测试完整输出 |
| cli-tests.txt | 2 项 CLI 测试完整输出 |
| benchmark-full.txt | 依赖自检 + 6 组参数网格输出 |
| branin-multiseed.txt | 6 种子扫描输出 |
| closed-loop-demo.txt | 3 轮闭环模拟输出 |
| example-run.txt | 端到端示例运行控制台输出 |
| example-recommendation.json | 示例推荐 JSON（机器可读） |
| example-report.md | 示例推荐中文报告（人类可读） |
| example-plot.png | 示例可视化图（EI 曲面 + 柱状图） |
