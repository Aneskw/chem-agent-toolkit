# -*- coding: utf-8 -*-
"""
closed_loop_demo.py —— 模拟闭环验证：3 轮"推荐 → 模拟实验 → 追加数据"。

验证 skill 的核心效果（effect）：以最少实验数逼近真实最优。
数据为 examples/ 的模拟产率函数（真实最优 ≈88，不在数据文件内），非真实化学。

用法：python results/closed_loop_demo.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "examples"))

from edbo_core import (  # noqa: E402
    BayesianOptimizer,
    ReactionSpace,
    fix_console_encoding,
    load_observations,
)
from make_demo_data import true_yield  # noqa: E402

fix_console_encoding()


def main() -> int:
    space = ReactionSpace.from_json(ROOT / "examples" / "direct_arylation_space.json")
    obs = load_observations(ROOT / "examples" / "initial_data.csv")
    rng = np.random.default_rng(7)  # 模拟实验噪声
    best_hist = [max(r["yield"] for r in obs)]
    print(f"初始: n={len(obs)} 最优产率={best_hist[-1]:.1f}（真实最优≈88，模拟值）")
    for rnd in range(1, 4):
        bo = BayesianOptimizer(space, batch_size=5, seed=42)
        bo.fit(obs)
        recs = bo.recommend_json()["recommendations"]
        for r in recs:
            cond = dict(r["conditions"])
            cond["yield"] = round(true_yield(cond, noise=5.0, rng=rng), 1)
            obs.append(cond)
        best_hist.append(max(x["yield"] for x in obs))
        top = recs[0]
        c = top["conditions"]
        print(f"第{rnd}轮: 推荐首位 {c['ligand']}/{c['base']}/{c['solvent']} "
              f"T={c['temperature']:.0f} C={c['concentration']:.2f} | "
              f"预测 {top['predicted_mean']:.1f}±{top['predicted_std']:.1f} | "
              f"当前最优={best_hist[-1]:.1f}")
    print("最优产率历史:", " -> ".join(f"{b:.1f}" for b in best_hist))
    assert best_hist[-1] > best_hist[0], "闭环未提升产率！"
    print(f"结论: 3 轮闭环产率提升 {best_hist[-1] - best_hist[0]:.1f} 个百分点")
    return 0


if __name__ == "__main__":
    sys.exit(main())
