# 示例：Pd 催化直接芳基化（模拟演示）

本目录提供一个自包含的演示案例，风格参照 EDBO 论文基准
（Shields et al., *Nature* 2021, 590, 89–96）：12 配体 × 4 碱 × 4 溶剂（类别）+
温度/浓度（连续）的反应空间，配 20 条**模拟**产率数据。

⚠ **数据为合成模拟值**（`make_demo_data.py` 中定义了已知"真实"产率函数，最优 ≈88，
不在数据文件内），仅用于演示闭环优化流程，不代表任何真实化学反应。

## 文件

| 文件 | 说明 |
|------|------|
| `direct_arylation_space.json` | 反应空间（5 个描述符 + yield 目标） |
| `initial_data.csv` | 20 条模拟初始观测（seed=42） |
| `make_demo_data.py` | 重新生成上述两个文件（`python make_demo_data.py`） |

## 快速开始

```bash
# 1. 推荐下一批 5 个实验
python ../scripts/recommend_next_batch.py \
    --space direct_arylation_space.json \
    --data initial_data.csv \
    --batch-size 5 --seed 42 \
    --output rec.json --report report.md --plot rec.png

# 2. 查看推荐（JSON 为机器可读；report.md 为人类可读；rec.png 为可视化）

# 3.（模拟闭环）把推荐条件代入"真实"产率函数，追加进数据，再迭代一轮：
python -c "
import sys; sys.path.insert(0, '../scripts')
from edbo_core import BayesianOptimizer, ReactionSpace, load_observations
from make_demo_data import true_yield
import numpy as np
space = ReactionSpace.from_json('direct_arylation_space.json')
obs = load_observations('initial_data.csv')
bo = BayesianOptimizer(space, batch_size=5, seed=42); bo.fit(obs)
rng = np.random.default_rng(7)
for r in bo.recommend():
    cond = dict(r['conditions'])
    print('执行:', cond, '→ 模拟产率', round(true_yield(cond, noise=5.0, rng=rng), 1))
"
```

预期：首轮推荐即锁定最优配体 L8 / 碱 K3PO4 组合；约 2 轮闭环后最优产率从 ~74 提升到 ~94。
