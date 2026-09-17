# -*- coding: utf-8 -*-
"""
plot_optimization.py —— 推荐结果可视化（可选组件，需 matplotlib）。

能力边界：
  * 空间中恰有 1–2 个连续描述符时：绘制采集函数曲面 + 已观测散点 + 推荐星标；
  * 其他情况（高维 / 纯类别）：仅绘制推荐点"预测均值 ± 标准差"柱状图。
本脚本只做展示；推荐计算在 edbo_core.py 中完成。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edbo_core import (  # noqa: E402
    BayesianOptimizer,
    ReactionSpace,
    fix_console_encoding,
    load_observations,
)

fix_console_encoding()


def _setup_chinese_font(plt) -> None:
    try:
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass


def plot_optimization(space_path, data_path, result_path, out_png, seed: int = 42) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _setup_chinese_font(plt)

    space = ReactionSpace.from_json(space_path)
    observations = load_observations(data_path)
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))

    bo = BayesianOptimizer(space, seed=seed)
    bo.fit(observations)
    cont_names = [n for n, _ in space.cont_blocks.items()]
    can_surface = 0 < len(cont_names) <= 2 and result["status"] != "cold_start"
    if can_surface:
        bo.fit_surrogate()

    recs = result["recommendations"]
    n_panels = 2 if can_surface else 1
    fig, axes = plt.subplots(1, n_panels, figsize=(7.2 * n_panels, 5.6))
    axes = np.atleast_1d(axes)

    # ---------- 面板 1：采集函数曲面（1–2 个连续描述符） ----------
    if can_surface:
        ax = axes[0]
        fixed = dict(recs[0]["conditions"]) if recs else {}
        base = space.encode(fixed)
        if len(cont_names) == 2:
            n1, n2 = cont_names
            g1 = np.linspace(0, 1, 120)
            g2 = np.linspace(0, 1, 120)
            G1, G2 = np.meshgrid(g1, g2)
            X = np.tile(base, (g1.size * g2.size, 1))
            i1, i2 = [i for i, (n, _) in enumerate(space.cont_blocks.items())][:2]
            X[:, i1] = G1.ravel()
            X[:, i2] = G2.ravel()
            _, _, acq = bo.evaluate(X)
            A = acq.reshape(G1.shape)
            lo1, hi1 = space.cont_blocks[n1][1], space.cont_blocks[n1][2]
            lo2, hi2 = space.cont_blocks[n2][1], space.cont_blocks[n2][2]
            cs = ax.contourf(G1 * (hi1 - lo1) + lo1, G2 * (hi2 - lo2) + lo2, A,
                             levels=20, cmap="viridis")
            fig.colorbar(cs, ax=ax, label="采集函数值 (EI)")
            ax.set_xlabel(_unit_label(space, n1))
            ax.set_ylabel(_unit_label(space, n2))
        else:
            n1 = cont_names[0]
            g = np.linspace(0, 1, 800)
            X = np.tile(base, (g.size, 1))
            i1 = next(i for i, (n, _) in enumerate(space.cont_blocks.items()))
            X[:, i1] = g
            mu, sigma, acq = bo.evaluate(X)
            lo1, hi1 = space.cont_blocks[n1][1], space.cont_blocks[n1][2]
            xaxis = g * (hi1 - lo1) + lo1
            ax.plot(xaxis, acq, label="采集函数 (EI)", color="#2c7fb8")
            ax.fill_between(xaxis, 0, acq, alpha=0.15, color="#2c7fb8")
            ax.set_xlabel(_unit_label(space, n1))
            ax.set_ylabel("EI")
            ax.legend()
        # 已观测散点（类别维与固定值一致的行）
        cat_keys = list(space.cat_blocks.keys())
        sign = 1.0 if space.objective.get("direction", "maximize") == "maximize" else -1.0
        obs_pts, obs_vals = [], []
        for xo, yo in zip(bo.X_obs, bo.y_obs):
            d = space.decode(xo)
            if all(_eq(d[k], fixed[k]) for k in cat_keys):
                obs_pts.append(d)
                obs_vals.append(float(yo) * sign)  # 还原为原始目标方向
        if obs_pts:
            xs = [p[cont_names[0]] for p in obs_pts]
            if len(cont_names) == 2:
                ys = [p[cont_names[1]] for p in obs_pts]
                ax.scatter(xs, ys, s=45, color="white", edgecolor="black", linewidth=0.8,
                           zorder=3, label="已观测")
            else:
                ax.scatter(xs, obs_vals, s=45, color="black", zorder=3, label="已观测")
        # 推荐点星标
        for r in recs:
            c = r["conditions"]
            if len(cont_names) == 2:
                ax.scatter(c[cont_names[0]], c[cont_names[1]], marker="*", s=320,
                           color="#d95f0e", edgecolor="black", linewidth=0.6, zorder=4)
            else:
                ax.axvline(c[cont_names[0]], color="#d95f0e", linestyle="--", alpha=0.7)
        fixed_txt = "，".join(f"{k}={fixed[k]}" for k in cat_keys) or "（无类别描述符）"
        ax.set_title(f"采集函数曲面（{space.name}）\n类别条件固定为 rank1: {fixed_txt}")

    # ---------- 面板 2：推荐点预测均值 ± 标准差 ----------
    ax = axes[-1]
    valid = [r for r in recs if r["predicted_mean"] is not None]
    if valid:
        ranks = np.arange(1, len(valid) + 1)
        means = np.array([r["predicted_mean"] for r in valid])
        stds = np.array([r["predicted_std"] for r in valid])
        colors = ["#2c7fb8" if r["confidence"] == "high" else
                  "#7fcdbb" if r["confidence"] == "medium" else "#d95f0e" for r in valid]
        ax.bar(ranks, means, yerr=stds, capsize=4, color=colors, alpha=0.9,
               edgecolor="black", linewidth=0.6)
        ax.set_xticks(ranks)
        ax.set_xticklabels([f"#{r['rank']}" for r in valid])
        ax.set_xlabel("推荐排名")
        ax.set_ylabel(f"预测 {result['objective']['name']}（± 标准差）")
        if result["n_observed"]:
            ax.axhline(result["observed_best"], color="#d95f0e", linestyle="--", linewidth=1.2)
            ax.text(0.99, 0.02, f"—— 当前最优 {result['observed_best']:.2f}",
                    transform=ax.transAxes, ha="right", va="bottom",
                    color="#d95f0e", fontsize=9)
        ax.set_title("推荐点预测均值与不确定性\n（颜色：高/中/低置信度）")
    else:
        ax.text(0.5, 0.5, "冷启动推荐：无模型预测", ha="center", va="center", fontsize=12)
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def _unit_label(space: ReactionSpace, name: str) -> str:
    d = next(d for d in space.descriptors if d["name"] == name)
    unit = d.get("unit")
    return f"{name} ({unit})" if unit else name


def _eq(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="绘制推荐结果图（需 matplotlib）")
    ap.add_argument("--space", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--result", required=True, help="recommend_next_batch.py 输出的 JSON")
    ap.add_argument("--output", required=True, help="PNG 路径")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    plot_optimization(a.space, a.data, a.result, a.output, seed=a.seed)
    print(f"图已保存: {a.output}")
