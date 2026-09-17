# -*- coding: utf-8 -*-
"""
benchmark.py —— 环境自检 + 参数敏感性小基准（可选运行，不影响 skill 主功能）。

用法：
    python scripts/benchmark.py           # 完整网格（6 组组合，约 0.5–2 分钟）
    python scripts/benchmark.py --quick   # 快速网格（3 组组合）

内容：
    1) 依赖版本自检（numpy / scipy / scikit-learn；matplotlib 可选）；
    2) Branin 2D 标准函数（全局最优 0.398）上跑 (采集函数 × GP 重启数 × 候选数) 网格，
       每组 10 个初始点 + 3 轮 × 4 批，报告最终最优值与耗时——用于验证本机环境
       并观察各参数对收敛与速度的影响。

参考值（开发机 Python 3.11 / sklearn 1.9）：EI 组合通常收敛到 <2.0、单组耗时数秒；
若全部组合最终最优 >10，或单组耗时 >60s，提示环境异常或性能不足。
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edbo_core import BayesianOptimizer, ReactionSpace, fix_console_encoding  # noqa: E402

fix_console_encoding()

# 组合网格：(采集函数, gp_restarts, n_candidates)
GRID_FULL = [
    ("EI", 5, 10000),
    ("EI", 5, 1000),
    ("EI", 1, 1000),
    ("UCB", 5, 10000),
    ("UCB", 1, 1000),
    ("GREEDY", 1, 1000),
]
GRID_QUICK = GRID_FULL[:3]


def branin(u) -> float:
    """Branin 标准测试函数（minimize，全局最优 0.398）。"""
    x1, x2 = 15 * u[0] - 5, 15 * u[1]
    a, b, c, r, s, t = 1.0, 5.1 / (4 * np.pi**2), 5 / np.pi, 6.0, 10.0, 1 / (8 * np.pi)
    return a * (x2 - b * x1**2 + c * x1 - r) ** 2 + s * (1 - t) * np.cos(x1) + s


def check_env() -> bool:
    print("== 1) 依赖环境自检 ==")
    ok = True
    for name, minver in (("numpy", "1.20"), ("scipy", "1.7"), ("sklearn", "1.0")):
        try:
            mod = importlib.import_module(name)
            v = getattr(mod, "__version__", "?")
            try:
                vt = tuple(int(x) for x in v.split(".")[:2])
                mt = tuple(int(x) for x in minver.split("."))
                flag = "OK" if vt >= mt else f"版本过低（需 ≥{minver}）"
                if vt < mt:
                    ok = False
            except ValueError:
                flag = f"版本格式无法解析: {v}"
                ok = False
            print(f"  {name:12s} {v:12s} {flag}")
        except ImportError:
            print(f"  {name:12s} 缺失        ❌ 请安装: pip install {name}")
            ok = False
    try:
        import matplotlib

        print(f"  {'matplotlib':12s} {matplotlib.__version__:12s} OK（可选，--plot 需要）")
    except ImportError:
        print(f"  {'matplotlib':12s} 未安装     提示：可选，仅 --plot 需要")
    return ok


def run_combo(space: ReactionSpace, acq: str, restarts: int, cands: int,
              n_rounds: int = 3, batch: int = 4):
    """固定初始数据（seed=3，初始最优 5.01）下跑一组参数，返回 (最终最优, 初始最优, 耗时s)。"""
    rng = np.random.default_rng(3)
    obs = [{"u1": float(rng.uniform()), "u2": float(rng.uniform())} for _ in range(10)]
    for r in obs:
        r["f"] = branin([r["u1"], r["u2"]])
    init_best = min(r["f"] for r in obs)

    t0 = time.perf_counter()
    bo = BayesianOptimizer(space, batch_size=batch, acquisition=acq,
                           n_candidates=cands, gp_restarts=restarts, seed=5)
    bo.fit(obs)
    for _ in range(n_rounds):
        for r in bo.recommend():
            c = dict(r["conditions"])
            c["f"] = branin([c["u1"], c["u2"]])
            obs.append(c)
        bo.fit(obs)
    return min(r["f"] for r in obs), init_best, time.perf_counter() - t0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="环境自检 + 参数敏感性小基准（可选运行）")
    ap.add_argument("--quick", action="store_true", help="只跑前 3 组组合（更快）")
    args = ap.parse_args(argv)

    env_ok = check_env()
    print()
    print("== 2) 参数敏感性基准（Branin 2D，初始最优 5.01，全局最优 0.398；22 次评估/组） ==")
    space = ReactionSpace.from_dict(
        {
            "name": "branin-bench",
            "objective": {"name": "f", "direction": "minimize"},
            "descriptors": [
                {"name": "u1", "type": "continuous", "min": 0.0, "max": 1.0},
                {"name": "u2", "type": "continuous", "min": 0.0, "max": 1.0},
            ],
        }
    )
    grid = GRID_QUICK if args.quick else GRID_FULL
    print(f"  {'acquisition':<12s} {'restarts':>8s} {'candidates':>10s} {'最终最优':>10s} "
          f"{'耗时(s)':>8s}  结论")
    n_converged, max_time = 0, 0.0
    for acq, restarts, cands in grid:
        final, init, dt = run_combo(space, acq, restarts, cands)
        max_time = max(max_time, dt)
        verdict = "收敛" if final < 2.0 else ("部分收敛" if final < 10.0 else "未收敛")
        n_converged += 1 if final < 2.0 else 0
        print(f"  {acq:<12s} {restarts:>8d} {cands:>10d} {final:>10.2f} {dt:>8.1f}  {verdict}")

    print()
    print("== 3) 结论 ==")
    if n_converged == len(grid) and max_time <= 60:
        print(f"  环境正常：{n_converged}/{len(grid)} 组组合收敛到全局最优邻域，"
              f"最慢单组 {max_time:.1f}s（开发机参考：EI/restarts=5/cands=10000 ≈ 3–10s）。")
    elif n_converged == 0:
        print("  ⚠ 全部组合未收敛：请检查依赖版本或数据质量；本机环境可能异常。")
        return 1 if not env_ok else 0
    else:
        print(f"  {n_converged}/{len(grid)} 组收敛。提示：restarts=1 或 GREEDY 组合收敛性弱属正常；"
              "实际推荐建议保持默认 EI + restarts≥3。")
        if max_time > 60:
            print(f"  ⚠ 最慢单组 {max_time:.1f}s 超过 60s：建议减小 --candidates 或 batch-size。")
    return 0 if env_ok else 1


if __name__ == "__main__":
    sys.exit(main())
