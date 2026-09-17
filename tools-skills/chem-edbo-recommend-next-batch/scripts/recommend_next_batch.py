# -*- coding: utf-8 -*-
"""
recommend_next_batch.py —— EDBO 贝叶斯反应优化推荐 CLI。

用法示例：
  python recommend_next_batch.py \
      --space ../examples/direct_arylation_space.json \
      --data  ../examples/initial_data.csv \
      --batch-size 5 --acquisition EI --seed 42 \
      --output recommendations.json --report report.md --plot rec.png

输入：
  --space  反应空间 JSON（描述符 + 目标定义，见 ../SKILL.md）
  --data   已有实验数据 CSV / JSON（列为描述符名 + 目标列名）
输出：
  JSON（机器可读，Agent 直接解析）、可选 Markdown 报告、可选 PNG 图。
核心计算完全在 edbo_core.py 中完成（GP + EI，无 LLM 调用）。
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edbo_core import (  # noqa: E402
    BayesianOptimizer,
    ReactionSpace,
    fix_console_encoding,
    load_observations,
    save_json,
)

fix_console_encoding()


def _fmt(v) -> str:
    """数值显示格式化：保留 4 位有效数字，其余原样输出。"""
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def build_report(result: dict, args) -> str:
    """由推荐结果生成人类可读的 Markdown 报告（模板化文本，非 LLM 生成）。"""
    obj = result["objective"]
    L = []
    L.append("# 下一批实验推荐报告（EDBO 贝叶斯优化）\n")
    L.append(f"- 反应空间：{result['space']['name']}（{result['space']['n_descriptors']} 个描述符）")
    L.append(f"- 已观测数据：{result['n_observed']} 条 | 当前最优 {obj['name']} = "
             f"{result['observed_best']:.2f}（{obj['direction']}）")
    L.append(f"- 模型：{result['model']['surrogate']} + {result['model']['acquisition']}"
             f" | 批策略：{result['model']['batch_strategy']}")
    L.append(f"- 生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
             f"（seed={result['model']['seed']}）\n")

    L.append("## 推荐条件（按优先级）\n")
    L.append("| # | 实验条件 | 预测均值 | 预测标准差 | EI | 置信度 |")
    L.append("|---|---------|---------:|-----------:|----:|:------:|")
    for r in result["recommendations"]:
        cond = "；".join(f"{k}={_fmt(v)}" for k, v in r["conditions"].items())
        if r["predicted_mean"] is None:
            L.append(f"| {r['rank']} | {cond} | — | — | — | {r['confidence']} |")
        else:
            L.append(f"| {r['rank']} | {cond} | {r['predicted_mean']:.2f} | "
                     f"{r['predicted_std']:.2f} | {r['expected_improvement']:.2f} | "
                     f"{r['confidence']} |")
    L.append("")

    L.append("## 解读要点\n")
    L.append("- 高 EI = 预测均值高与不确定性大的平衡点，是最值得优先尝试的条件。")
    L.append("- 置信度 low 的点位于模型覆盖稀疏区域，探索风险与机会并存；high 的点接近已充分探索区域。")
    L.append("- 推荐整批并行执行，实测产率后并入数据文件，再次调用本 skill 迭代（闭环优化）。")
    hits = [(r["rank"], "、".join(r.get("boundary_hit") or []))
            for r in result["recommendations"] if r.get("boundary_hit")]
    if hits:
        L.append("\n### 边界提示\n")
        for rank, names in hits:
            L.append(f"- ⚠ 第 {rank} 条推荐命中变量边界（{names}）：真实最优可能在声明范围之外，"
                     f"建议扩宽该描述符范围或人工复核。")
    if result["diagnostics"].get("suggestions"):
        L.append("\n### 模型建议\n")
        for s in result["diagnostics"]["suggestions"]:
            L.append(f"- 💡 {s}")
    if result["diagnostics"].get("warnings"):
        L.append("\n### 诊断告警\n")
        for w in result["diagnostics"]["warnings"]:
            L.append(f"- ⚠ {w}")
    L.append("")

    L.append("## 安全与操作提示（通用提示，不构成安全审查）\n")
    L.append("- 推荐值是统计模型预测，不是实验事实；产率测量本身存在噪声。")
    L.append("- 执行前请人工复核：溶剂/试剂的燃爆与毒性、温度压力条件、空气/水分敏感性、后处理与淬灭方案。")
    L.append("- 首次尝试新条件建议小规模验证，并做好失败预案。\n")

    L.append("## 引用\n")
    L.append("- " + "；".join(result["citation"]))
    return "\n".join(L) + "\n"


def print_summary(result: dict) -> None:
    obj = result["objective"]
    print(f"[chem-edbo-recommend-next-batch] 已观测 {result['n_observed']} 条 | "
          f"当前最优 {obj['name']} = {result['observed_best']:.2f} | 状态: {result['status']}")
    print(f"Top {len(result['recommendations'])} 推荐（{result['model']['acquisition']}）：")
    for r in result["recommendations"]:
        cond = " ".join(f"{k}={_fmt(v)}" for k, v in r["conditions"].items())
        if r["predicted_mean"] is None:
            print(f"  #{r['rank']:d}  {cond}  |  冷启动空间填充点")
        else:
            print(f"  #{r['rank']:d}  {cond}  |  预测 {r['predicted_mean']:.2f} ± "
                  f"{r['predicted_std']:.2f}  |  EI={r['expected_improvement']:.2f}  |  "
                  f"{r['confidence']}")
    for r in result["recommendations"]:
        if r.get("boundary_hit"):
            print(f"  [边界提示] #{r['rank']} 命中变量边界（{'、'.join(r['boundary_hit'])}）："
                  f"真实最优可能在范围之外", file=sys.stderr)
    for s in result["diagnostics"].get("suggestions", []):
        print(f"  [建议] {s}", file=sys.stderr)
    for w in result["diagnostics"].get("warnings", []):
        print(f"  [警告] {w}", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="recommend_next_batch.py",
        description="EDBO 贝叶斯反应优化：推荐下一批最值得做的实验条件。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--space", required=True, help="反应空间 JSON 文件")
    ap.add_argument("--data", required=True, help="已有实验数据 CSV 或 JSON 文件")
    ap.add_argument("--batch-size", type=int, default=5, help="推荐批次大小")
    ap.add_argument("--acquisition", default="EI", choices=["EI", "UCB", "GREEDY"],
                    help="采集函数：EI=Expected Improvement（默认）")
    ap.add_argument("--candidates", type=int, default=10000, help="候选点数量")
    ap.add_argument("--gp-restarts", type=int, default=5, help="GP 超参数优化重启次数")
    ap.add_argument("--kappa", type=float, default=2.0, help="UCB 的探索系数 κ")
    ap.add_argument("--batch-strategy", default="diverse", choices=["diverse", "greedy"],
                    help="批选择策略：diverse=局部惩罚增强批内多样性（默认）；greedy=纯贪心（旧行为）")
    ap.add_argument("--diversity-radius", type=float, default=0.25,
                    help="局部惩罚半径（仅 batch-strategy=diverse 时生效；0=关闭惩罚）")
    ap.add_argument("--seed", type=int, default=42, help="随机种子（复现性）")
    ap.add_argument("--output", default=None, help="输出 JSON 路径（默认 recommendations_<空间名>.json）")
    ap.add_argument("--report", default=None, help="可选：输出 Markdown 报告路径")
    ap.add_argument("--plot", default=None, help="可选：输出 PNG 图路径（需 matplotlib）")
    args = ap.parse_args(argv)

    try:
        space = ReactionSpace.from_json(args.space)
    except Exception as e:
        print(f"[错误] 反应空间解析失败: {e}", file=sys.stderr)
        return 2
    try:
        observations = load_observations(args.data)
    except Exception as e:
        print(f"[错误] 数据文件读取失败: {e}", file=sys.stderr)
        return 2

    try:
        bo = BayesianOptimizer(
            space,
            batch_size=args.batch_size,
            acquisition=args.acquisition,
            n_candidates=args.candidates,
            gp_restarts=args.gp_restarts,
            kappa=args.kappa,
            seed=args.seed,
            batch_strategy=args.batch_strategy,
            diversity_radius=args.diversity_radius,
        )
        bo.fit(observations)
        result = bo.recommend_json()
    except ValueError as e:
        print(f"[错误] 数据校验失败: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[错误] 优化计算失败: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if args.output:
        out = Path(args.output)
    else:
        import re

        safe_name = re.sub(r"[^\w\-]+", "_", space.name).strip("_") or "reaction_space"
        out = Path(f"recommendations_{safe_name}.json")
    try:
        save_json(result, out)
    except Exception as e:
        print(f"[错误] 结果写入失败: {e}", file=sys.stderr)
        return 2
    print(f"输出 JSON: {out}")

    if args.report:
        Path(args.report).write_text(build_report(result, args), encoding="utf-8")
        print(f"输出报告: {args.report}")

    if args.plot:
        try:
            from plot_optimization import plot_optimization

            plot_optimization(args.space, args.data, str(out), args.plot, seed=args.seed)
            print(f"输出图: {args.plot}")
        except Exception as e:
            print(f"[警告] 绘图失败（不影响推荐结果）: {e}", file=sys.stderr)

    print_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
