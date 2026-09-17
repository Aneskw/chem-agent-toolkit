# 下一批实验推荐报告（EDBO 贝叶斯优化）

- 反应空间：Pd 催化直接芳基化（模拟演示）（5 个描述符）
- 已观测数据：20 条 | 当前最优 yield = 74.20（maximize）
- 模型：Gaussian Process (Matérn-5/2, ARD) + Expected Improvement | 批策略：greedy + Kriging-believer（顺序批 EI）
- 生成时间：2026-09-17 16:53:46（seed=42）

## 推荐条件（按优先级）

| # | 实验条件 | 预测均值 | 预测标准差 | EI | 置信度 |
|---|---------|---------:|-----------:|----:|:------:|
| 1 | temperature=40.05；concentration=0.1813；ligand=L8；base=K3PO4；solvent=DMF | 73.97 | 2.83 | 1.02 | high |
| 2 | temperature=41.3；concentration=0.2304；ligand=L8；base=KOAc；solvent=NMP | 61.45 | 8.02 | 0.19 | medium |
| 3 | temperature=118.2；concentration=0.2092；ligand=L8；base=K3PO4；solvent=DMF | 72.71 | 1.68 | 0.17 | high |
| 4 | temperature=66.37；concentration=0.2811；ligand=L8；base=K3PO4；solvent=dioxane | 74.24 | 0.28 | 0.13 | high |
| 5 | temperature=64.39；concentration=0.207；ligand=L8；base=K3PO4；solvent=NMP | 74.25 | 0.21 | 0.11 | high |

## 解读要点

- 高 EI = 预测均值高与不确定性大的平衡点，是最值得优先尝试的条件。
- 置信度 low 的点位于模型覆盖稀疏区域，探索风险与机会并存；high 的点接近已充分探索区域。
- 推荐整批并行执行，实测产率后并入数据文件，再次调用本 skill 迭代（闭环优化）。

## 安全与操作提示（通用提示，不构成安全审查）

- 推荐值是统计模型预测，不是实验事实；产率测量本身存在噪声。
- 执行前请人工复核：溶剂/试剂的燃爆与毒性、温度压力条件、空气/水分敏感性、后处理与淬灭方案。
- 首次尝试新条件建议小规模验证，并做好失败预案。

## 引用

- Shields et al., Nature 2021, 590, 89–96, DOI: 10.1038/s41586-021-03213-y；Garrido Torres et al., J. Am. Chem. Soc. 2022, 144, 19999–20007, DOI: 10.1021/jacs.2c08592
