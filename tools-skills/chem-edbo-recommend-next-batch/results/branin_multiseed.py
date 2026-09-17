# -*- coding: utf-8 -*-
"""
branin_multiseed.py —— Branin 多种子扫描：验证收敛不依赖特定初始点。

对 6 个不同初始随机种子（各 10 个初始点）跑相同 BO 流程（3 轮 × 批 4），
报告初始最优 → 最终最优。全局最优 0.398。

用法：python results/branin_multiseed.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from edbo_core import BayesianOptimizer, ReactionSpace, fix_console_encoding  # noqa: E402

fix_console_encoding()


def branin(u) -> float:
    x1, x2 = 15 * u[0] - 5, 15 * u[1]
    a, b, c, r, s, t = 1.0, 5.1 / (4 * np.pi**2), 5 / np.pi, 6.0, 10.0, 1 / (8 * np.pi)
    return a * (x2 - b * x1**2 + c * x1 - r) ** 2 + s * (1 - t) * np.cos(x1) + s


def main() -> int:
    space = ReactionSpace.from_dict(
        {
            "name": "branin",
            "objective": {"name": "f", "direction": "minimize"},
            "descriptors": [
                {"name": "u1", "type": "continuous", "min": 0.0, "max": 1.0},
                {"name": "u2", "type": "continuous", "min": 0.0, "max": 1.0},
            ],
        }
    )
    print("Branin 多种子扫描（全局最优 0.398；每种子 10 初始点 + 3 轮 × 批 4 = 22 次评估）")
    print(f"{'init_seed':>10s} {'初始最优':>10s} {'最终最优':>10s}  结论")
    n_conv = 0
    for init_seed in range(6):
        rng = np.random.default_rng(init_seed)
        obs = [{"u1": float(rng.uniform()), "u2": float(rng.uniform())} for _ in range(10)]
        for r in obs:
            r["f"] = branin([r["u1"], r["u2"]])
        init_best = min(r["f"] for r in obs)
        bo = BayesianOptimizer(space, batch_size=4, n_candidates=3000, gp_restarts=3, seed=5)
        bo.fit(obs)
        for _ in range(3):
            for r in bo.recommend():
                c = dict(r["conditions"])
                c["f"] = branin([c["u1"], c["u2"]])
                obs.append(c)
            bo.fit(obs)
        final = min(r["f"] for r in obs)
        verdict = "收敛" if final < 2.0 else "部分收敛" if final < 10.0 else "未收敛"
        n_conv += 1 if final < 2.0 else 0
        print(f"{init_seed:>10d} {init_best:>10.2f} {final:>10.2f}  {verdict}")
    print(f"结论: {n_conv}/6 个初始种子收敛到全局最优邻域")
    return 0


if __name__ == "__main__":
    sys.exit(main())
