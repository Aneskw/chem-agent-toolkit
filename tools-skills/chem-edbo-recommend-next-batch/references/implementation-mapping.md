# 论文概念 ↔ 本实现逐条映射（含取舍说明）

> 用途：实现核对、调试、以及向用户解释"本 skill 与 EDBO 论文的异同"时的依据。
> 映射对象：Shields et al., *Nature* 2021（EDBO）与 scripts/edbo_core.py。

## 1. 逐条映射表

| # | 论文/EDBO 概念 | 本实现 | 位置 | 取舍与说明 |
|---|---|---|---|---|
| 1 | 迭代闭环：训练→推荐→实验→重训 | `BayesianOptimizer.fit() → recommend()` 反复调用 | edbo_core.py | 一致；每轮重新拟合 GP |
| 2 | 描述符：DFT(>1000维) / Mordred(>1800维) / OHE | 仅类别 one-hot + 连续数值 | `ReactionSpace.encode()` | **主动简化**：不计算分子描述符；用户可将 DFT/Mordred 算好的数值列直接当连续描述符输入 |
| 3 | 预处理：去非数值、one-hot、去相关(r>0.95)、归一化[0,1] | 连续变量线性归一化 [0,1]；类别 one-hot；未做去相关 | `_build_layout()`, `encode()` | 去相关省略（用户变量通常已正交）；若输入强相关列可自行预处理 |
| 4 | 代理模型：Matérn-5/2 核 GP | `ConstantKernel * Matern(nu=2.5)` + ARD 长度尺度，alpha=1e-5 数值抖动 | `_make_gp()` | 核函数一致（论文同款核族） |
| 5 | GP 先验：按描述符集合多目标自优化 | ML-II 边际似然最大化 + n_restarts 多重启（默认 5） | `GaussianProcessRegressor(n_restarts_optimizer=...)` | **工程替代**：等价于标准的经验贝叶斯超参数估计，非论文的 self-optimized priors |
| 6 | 目标值处理 | 手动标准化 y→(0,1)，预测映射回原始量纲；minimize 方向内部取负 | `fit_surrogate()`, `evaluate()` | 论文对目标同样做归一化；实现细节略异，行为一致 |
| 7 | 采集函数：expected improvement | `expected_improvement()`：EI=(μ−best)Φ(z)+σφ(z)，z=(μ−best)/σ | edbo_core.py | 公式逐字遵循 Jones 1998；另有 UCB/GREEDY 备选 |
| 8 | 批推荐：联合 EI 优化 | 贪心 + Kriging-believer 幻想更新（预测均值作为伪观测，重拟合后选下一个），默认叠加**局部惩罚**增强批内多样性（`--batch-strategy diverse`，半径 0.25；`greedy` 关闭） | `recommend()` 批循环 + `local_penalty()` | **近似**：顺序批 EI 非联合 qEI；局部惩罚为 González et al. 2016 的工程简化（A/B 对照实验证实其必要性；增大 candidates 对聚集无效） |
| 9 | 候选集：随机采样/全枚举 | 全类别空间且 ≤n_candidates 时全枚举，否则均匀随机采样 n_candidates 点 | `candidate_pool()` | 与 EDBO 的离散组合枚举思路一致 |
| 10 | 已做实验排除 | 推荐前从候选池剔除已观测点（编码向量 allclose） | `_exclude_observed()` | 一致；防止推荐重复实验 |
| 11 | 冷启动（初始数据） | 观测 <2 条 → 不拟合 GP，返回 maximin 空间填充批 | `_cold_start_batch()` | 论文用随机/网格初筛；maximin 是本实现的稳健化选择 |
| 12 | 置信度/不确定性报告 | 每推荐附 predicted_std、置信度分档（0.5σ/1.5σ 观测标准差）、`boundary_hit` 边界命中标记 | `_make_rec()` + `ReactionSpace.boundary_hits()` | 分档阈值自定义（低可信度项，可调）；boundary_hit 为 A/B 实验新增（GP 外推边界曾致整批贴边） |
| 13 | 结果解释与报告 | 模板化 Markdown 报告 + 控制台摘要 + 图 | recommend_next_batch.py, plot_optimization.py | 论文为软件+在线界面；本 skill 为 Agent 可解析 JSON + 人类可读报告 |
| 14 | LLM 的角色 | 无 LLM 参与核心计算；LLM 仅可解析自然语言输入/解读输出 | SKILL.md「Procedure Guidance」第 7 条 | 按任务要求明确划界 |

## 2. 关键公式核对

**Expected Improvement（maximize 方向）**
```
z  = (μ(x) − f⁺) / σ(x)
EI = σ(x)·[ z·Φ(z) + φ(z) ]      （σ→0 时钳位到 1e-12，EI 非负裁剪）
```
`f⁺` = 当前已观测最优（本实现用翻转后空间的最优值）。**符号核对**：μ 高于 f⁺ 时 z>0、EI 大；
μ 远低于 f⁺ 时 z≪0、EI≈0。测试 `test_ei_formula` 锁定该行为（此前曾发现符号反转 bug，已修复）。

**Kriging-believer 批循环**（每批选 k 个点）：
```
1. 在当前 GP 上对所有候选点算 EI，取 argmax → x*
2. 记录 x* 的预测均值 μ(x*) 为"幻想观测"，加入训练集
3. 重拟合 GP，回到 1（直到批满）
```
注意：`best` 在批内**不随幻想点更新**（仅真实观测更新），与经典 Kriging-believer 一致。

**类别编码**：选项块 one-hot（保留全部 k 列，不 drop 首列）；解码取 argmax。
**连续编码**：x_enc = (x − min)/(max − min) ∈ [0,1]。

## 3. 已知局限（诚实声明）

1. 无多目标（EI 为单目标采集函数；EHVI/qEI 见 EDBO+）；
2. 无安全域约束（除 bounds 告警外不限制搜索，GP 可预测出物理界限外的值——现以 `boundary_hit`
   标记 + 建议字段提示，但不自动纠正）；
3. 高维（编码后 >20 维）时 GP 精度与速度下降；
4. 局部惩罚缓解但未根除批内聚集；低数据首轮仍偏探索（diagnostics.suggestions 会提示换 UCB）；
5. 未实现论文的 DFT/Mordred 描述符流水线与先验自优化；
6. 预测为统计外推，系统性偏差（如反应机理突变）无法被 GP 捕捉——变量范围内若存在相变/机理切换，需人工分段或补充领域约束。

## 4. 输出 schema 版本

- `schema_version: "1.1"`（输出 JSON 中声明）。1.1 相对 1.0：每条推荐新增 `boundary_hit`
  字段；diagnostics 新增 `suggestions`；model.batch_strategy 描述随批策略变化。
  改动推荐结构时须递增并更新 SKILL.md。
