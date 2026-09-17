---
name: chem-edbo-recommend-next-batch
description: >
    Function: 基于 EDBO 贝叶斯反应优化，给定化学反应空间与已有实验产率数据，推荐下一批最值得做的实验条件。
    Invoke for: "推荐下一批最值得做的实验/反应条件"、"优化反应产率该做哪些实验"、
    "下一批实验设计/实验规划"、"EDBO 贝叶斯优化推荐实验"、"Bayesian reaction optimization
    next batch recommendation"、"给定产率数据建议下一轮筛选条件"...
license: MIT
compatibility: Python ≥ 3.9；依赖 numpy / scipy / scikit-learn
allowed-tools: Bash, Read, Write, Glob, WebFetch, WebSearch
---

# chem-edbo-recommend-next-batch

**做什么**：给定一个化学反应空间（类别/连续描述符）和已有实验产率数据，用 EDBO 风格贝叶斯优化（高斯过程 + Expected Improvement）**推荐下一批最值得做的实验条件**，输出推荐条件、预测均值、预测标准差、EI 值与置信度，以及可选的可视化图与 Markdown 报告。

**适用（positive）**：
- 小数据量实验设计：已有 ≥5 条（≥2 条可冷启动）实测产率/目标值，希望以最少实验数找到高产率条件；
- 同时含类别描述符（配体/碱/溶剂等）与连续描述符（温度/浓度/时间等）的混合反应空间；
- 批量并行实验工作流（一次跑一批，拿到结果后迭代下一轮）——闭环优化；
- 单目标（产率/选择性/ee/成本等，maximize 或 minimize）反应优化。

**不适用（negative）**：
- ❌ 反应预测 / 逆合成 / 分子生成——本 skill 不做化学推断，只做实验条件数值优化；
- ❌ 零数据全自动寻优：观测 <2 条时只返回空间填充初始设计，不做模型推荐；
- ❌ 高维（编码后 > 20 维）或样本量 > 数千的大数据场景：GP 拟合慢且收益有限；
- ❌ 多目标帕累托优化（如同时优化产率+选择性）——需 qEHVI 等方法，见 references 中的 EDBO+；
- ❌ 安全评估与可行性判断：推荐条件必须经实验者人工复核后才能执行。

## Credibility

按可信度分三级（高=严格遵循；中=需验证；低=高度灵活）：

**1. 高可信度（Enforce strictly）—— 文献直接验证、本实现已测试**
- GP + EI 在 EDBO 论文中的系统基准：Pd 催化直接芳基化基准集（12 配体 × 4 碱 × 4 溶剂 × 3 温度 × 3 浓度
  = 1728 组合），贝叶斯优化在平均效率与一致性上**优于 50 位人类化学专家**（第 3 批起超越，且总能达到 >99% 产率）；
- 真实案例：Mitsunobu 反应 40 次实验内 99% 产率（18 万组合空间）；脱氧氟化反应 15 次实验内 35% → 69%；
- 算法核心（Matérn-5/2 核 GP、EI 公式、[0,1] 归一化、one-hot 类别编码、贪心批选择）为
  scripts/edbo_core.py 的标准实现，已通过本 skill 自带 11 项测试：Branin 基准 22 次评估收敛到
  全局最优邻域（5.01 → 0.41，全局最优 0.40）、模拟闭环 2 轮产率 74.2 → 94.2；
- 执行时必须保持：EI 符号公式、类别/连续编码方式、重复条件去重、批内不重复推荐。

**2. 中可信度（Need verification）—— 实现细节与原文有工程取舍，使用前应验证**
- 超参数估计：EDBO 论文对每个描述符集合用多目标自优化确定 GP 先验；本实现改用
  ML-II 边际似然 + 多重启（n_restarts）估计核超参数，效果接近但非原文设置；
- 批选择策略：EDBO 采用联合 EI（含随机采样批优化），本实现用**贪心 + Kriging-believer 幻想更新**
  近似顺序批 EI，批内多样性可能略低（缓解：增大 --candidates 或减小 batch-size）；
- 描述符集合：论文最优为 DFT 描述符（>1000 维）与 Mordred 指纹（>1800 维），本 skill 仅支持
  **类别 one-hot + 连续数值**这一最通用的工程形态；分子描述符可另行计算后作为连续描述符输入；
- 冷启动阈值（<2 条返回空间填充）与置信度分档（0.5σ/1.5σ）为本 skill 自定义经验规则。

**3. 低可信度（Highly flexible）—— 解释与外围，可自由调整**
- 报告措辞、"解读要点"、通用安全提示文案（模板生成，非专业安全审查）；
- 置信度标签语义、控制台输出格式、图的配色与布局；
- 是否用 LLM 解读结果（可选）：Agent 可将 JSON 结果转述为自然语言，但**不得**修改数值推荐。

## Reference

参考材料选择指南（按使用场景取用）：

| 场景 | 材料 | 位置/链接 |
|------|------|-----------|
| 本 skill 方法学依据与算法细节 | Shields et al., *Nature* 2021（EDBO 论文） | `skill提取资源/贝叶斯tool.pdf`（密码保护）；摘要见 `skill提取资源/Fwd Prediction.csv` 第 1 条；DOI: 10.1038/s41586-021-03213-y |
| 文献要点、基准数据、可信度分级依据 | `references/edbo-literature.md` | 本 skill |
| 论文概念 ↔ 本实现逐条映射（含取舍说明） | `references/implementation-mapping.md` | 本 skill |
| EDBO 官方软件（GPyTorch 实现，含 priors 配置参考） | github.com/b-shields/edbo | 网络 |
| 多目标/Web 应用扩展（EI、qEI、EHVI） | Garrido Torres et al., *JACS* 2022, 144, 19999–20007；github.com/doyle-lab-ucla/edboplus | DOI: 10.1021/jacs.2c08592 |
| 领域综述（方法论背景） | Taylor et al., *Chem. Rev.* 2023, 123, 3089–3126 | DOI: 10.1021/acs.chemrev.2c00798 |
| 机器臂闭环验证（正交方法参考） | Angello et al., *Science* 2022, 378, 399–405 | DOI: 10.1126/science.adc8743 |
| EI 采集函数原始文献 | Jones et al., *J. Global Optim.* 1998, 13, 455–492 | — |

选用原则：实现与调试看 `references/implementation-mapping.md`；写报告/可信度论证引用 EDBO 论文
与 `references/edbo-literature.md`；涉及多目标需求时指引到 EDBO+，不要强行用本 skill。

## Input & Output

### 输入 1：反应空间 JSON（`--space`，必需）

```json
{
  "name": "Pd 催化直接芳基化",
  "objective": {"name": "yield", "direction": "maximize", "bounds": [0, 100]},
  "descriptors": [
    {"name": "ligand",   "type": "categorical", "options": ["L1", "L2", "L3", "L4"]},
    {"name": "base",     "type": "categorical", "options": ["Cs2CO3", "K2CO3", "K3PO4", "KOAc"]},
    {"name": "temperature", "type": "continuous", "min": 40.0, "max": 120.0, "unit": "°C"},
    {"name": "concentration", "type": "continuous", "min": 0.05, "max": 0.30, "unit": "M"}
  ]
}
```
- `descriptors`：≥1 个；`type` 为 `categorical`（须给 `options` 列表，≥2 项且不重复）或
  `continuous`（须给 `min < max`）；`unit` 可选，仅用于图轴标签；
- `objective.direction`：`maximize`（默认）或 `minimize`；`bounds` 可选，用于越界告警提示；
- 描述符名必须与数据文件的列名完全一致（区分大小写）。

### 输入 2：已有实验数据（`--data`，必需）

CSV（首行表头 = 描述符名 + 目标列名；类别值用字符串；编码自动识别 utf-8/gbk）：

```csv
ligand,base,solvent,temperature,concentration,yield
L1,Cs2CO3,DMA,90,0.1,42.3
...
```
或 JSON：`[{"ligand": "L1", ..., "yield": 42.3}, ...]`（也接受 `{"observations": [...]}` 包裹）。

### 调用方式（Agent 通过 Bash 执行）

```bash
python <skill>/scripts/recommend_next_batch.py \
    --space <空间.json> --data <数据.csv> \
    --batch-size 5 --acquisition EI --seed 42 \
    --output recommendations.json --report report.md --plot rec.png
```
程序化调用（Python）：

```python
from edbo_core import ReactionSpace, BayesianOptimizer, load_observations
space = ReactionSpace.from_json("space.json")
bo = BayesianOptimizer(space, batch_size=5, acquisition="EI", seed=42)
bo.fit(load_observations("data.csv"))
result = bo.recommend_json()   # 见下方输出 schema
```

### 输出 JSON（机器可读，Agent 直接解析）

```json
{
  "skill": "chem-edbo-recommend-next-batch",
  "schema_version": "1.0",
  "status": "ok",                      // ok | low_data | cold_start
  "model": {"surrogate": "...", "acquisition": "Expected Improvement", "batch_strategy": "...", "seed": 42},
  "objective": {"name": "yield", "direction": "maximize"},
  "n_observed": 20,
  "observed_best": 74.2,                // 原始方向上的当前最优
  "recommendations": [
    {
      "rank": 1,
      "conditions": {"ligand": "L8", "base": "K3PO4", "temperature": 63.8, ...},
      "predicted_mean": 73.97,          // GP 预测均值（原始量纲）
      "predicted_std": 2.83,            // 预测标准差（不确定性）
      "expected_improvement": 1.02,     // EI 采集函数值
      "confidence": "high"              // high | medium | low（相对观测值波动）
    }
  ],
  "diagnostics": {"log_marginal_likelihood": -12.3, "kernel_constant": 0.9,
                  "length_scales": {"ligand[L1]": 1.2, ...}, "warnings": []},
  "citation": ["Shields et al., Nature 2021, ...", "Garrido Torres et al., JACS 2022, ..."],
  "note": "推荐值为模型预测而非实验事实；实验前请结合安全性与可操作性人工复核。"
}
```
- 冷启动（观测 <2 条）时 `status=cold_start`，`predicted_mean` 等为 `null`，推荐为空间填充点；
- 同时可输出 Markdown 报告（含解读要点、通用安全提示、引用）与 PNG 图
  （1–2 个连续描述符时绘采集函数曲面，否则绘预测均值 ± 标准差柱状图）。

## Procedure Guidance

### 标准闭环流程（一次调用一轮）

1. **定义反应空间**：选择描述符并确定取值范围。原则：只放可独立调变且有意义的变量
   （配体/碱/溶剂/温度/浓度/时间/当量…）；连续变量给足范围；把已知固定条件移出空间。
2. **收集已有数据**：整理成 CSV（列名与空间 JSON 一致）。数据不足 2 条也没关系——本 skill 会
   返回空间填充初始设计；建议先用随机/网格实验积累 ≥5 条。
3. **执行推荐**（Bash 运行上述 CLI）：
   - 默认 `--acquisition EI`（探索-利用平衡最好，文献主推）；
   - `--batch-size` = 实验室一轮能并行执行的实验数；
   - 固定 `--seed` 保证可复现；`--candidates` 一般保持默认 10000。
4. **解读结果**：优先看 EI 排序；`predicted_std` 大（置信度 low/medium）的点 = 探索型推荐，
   小（high）的点 = 利用型推荐。注意预测值可略超物理界限（如 >100%），属 GP 正常外推。
5. **执行实验**：按推荐条件开展实验，记录真实目标值。
6. **迭代**：把新实验结果**追加**进数据 CSV，再次运行本 skill → 直到产率收敛或满足目标。
   每轮均重新拟合 GP，历史数据始终参与建模。
7. **（可选）LLM 的使用边界**：核心推荐永远来自 scripts 的数值计算；LLM 只可：
   ①把非结构化实验记录解析成 CSV；②把 JSON 结果改写成自然语言解释；③补充反应安全知识提示。
   **禁止**让 LLM 修改或替代数值推荐结果。

### 常见任务示例

- *"优化我的 Suzuki 反应产率"* → 从 examples/ 复制空间模板，替换描述符与数据 → 跑 CLI → 迭代。
- *"只有 3 条数据怎么办"* → 直接运行，返回空间填充批（status=low_data/cold_start），先做完这批。
- *"想同时优化产率和选择性"* → 本 skill 不适用，指引 EDBO+（qEI/EHVI，见 Reference 表）。
- *"只想快速看当前模型预测"* → `python -c "from edbo_core import ..."` 用 `fit_surrogate() + evaluate()`。

## Matters & Troubleshooting

**数据与空间**
- 类别值写错（如 `K3P04` vs `K3PO4`）→ 报错并列出合法选项：以报错信息为准修改 CSV；
- 连续值越界 / 目标列缺失 / CSV 列数不一致 → 退出码 2 并给出具体行号信息；
- 产率超出 `bounds`（如 0–100）→ 仅告警不报错，请确认是否为记录错误；
- 重复条件 → 自动保留最后一条并告警；NaN 产率 → 自动剔除并告警；
- 中文列名/中文 Excel 导出乱码 → 支持 utf-8 / gbk 自动识别；另存 CSV 时选 UTF-8 最稳。

**算法行为**
- 推荐批内点聚集（多样性低）→ Kriging-believer 贪心的已知局限：增大 `--candidates`、
  减小 `--batch-size`，或分多轮单点推荐；也可改用 `--acquisition UCB` 增加探索；
- 预测均值超过物理界限（如 103%）→ GP 无界外推的正常现象，不裁剪以保持模型诚实，人工按 100% 理解；
- 收敛停滞（EI 连续多轮极小）→ 可能已达局部最优：扩大空间范围、加入新描述符，或补充随机实验重启探索；
- 数据噪声大 → 产率测量尽量用内标/GC 定量；GP 对噪声稳健但收敛变慢；
- 高维空间（>20 编码维）→ GP 拟合慢、效果差：减少变量或改用分子描述符降维后再输入本 skill。

**环境与依赖**
- `ModuleNotFoundError: sklearn` → `pip install numpy scipy scikit-learn`（matplotlib 仅 --plot 需要）；
- 绘图报错不影响推荐结果（CLI 会警告并继续）；服务器无显示器时脚本自动用 Agg 后端；
- 中文 Windows 控制台乱码 → 脚本已自动切换 UTF-8 输出；若仍乱码用 `python -X utf8 ...`；
- 运行耗时：编码维度 ~25、候选 1 万、批 5 时典型 <1 分钟；增大 `--candidates`/`--gp-restarts` 可换更稳的结果。

**安全边界（重要）**
- 本 skill 输出的是统计推荐，**不是**安全或可行性审批：新溶剂/试剂组合、高温高压条件、放大实验前必须由实验人员完成风险评估；涉及危险试剂（如 NaN₃、HF、强氧化剂）时不建议直接上模型推荐条件。
