# -*- coding: utf-8 -*-
"""
test_edbo_core.py —— 核心库单元测试。

运行方式（无需 pytest，纯标准库断言）：
    python tests/test_edbo_core.py
也兼容：
    pytest tests/test_edbo_core.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from edbo_core import (  # noqa: E402
    BayesianOptimizer,
    ReactionSpace,
    expected_improvement,
    fix_console_encoding,
)


def make_space() -> ReactionSpace:
    return ReactionSpace.from_dict(
        {
            "name": "测试空间",
            "objective": {"name": "yield", "direction": "maximize", "bounds": [0, 100]},
            "descriptors": [
                {"name": "ligand", "type": "categorical", "options": ["L1", "L2", "L3", "L4"]},
                {"name": "base", "type": "categorical", "options": ["A", "B"]},
                {"name": "temperature", "type": "continuous", "min": 40.0, "max": 120.0},
                {"name": "concentration", "type": "continuous", "min": 0.05, "max": 0.30},
            ],
        }
    )


def make_observations(n: int = 12, seed: int = 0) -> list:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        out.append(
            {
                "ligand": str(rng.choice(["L1", "L2", "L3", "L4"])),
                "base": str(rng.choice(["A", "B"])),
                "temperature": round(float(rng.uniform(40, 120)), 2),
                "concentration": round(float(rng.uniform(0.05, 0.30)), 3),
                "yield": round(float(rng.uniform(10, 90)), 1),
            }
        )
    return out


def test_encode_decode_roundtrip():
    space = make_space()
    rng = np.random.default_rng(1)
    for _ in range(200):
        x = space.random_points(1, rng)[0]
        assert np.allclose(space.encode(space.decode(x)), x), "编码/解码往返不一致"
    print("✓ test_encode_decode_roundtrip")


def test_ei_formula():
    # best=0 时：μ 高于 best 的 EI 大，μ 远低于 best 的 EI≈0，恒非负
    ei = expected_improvement(np.array([0.0, 1.0, -1.0]), np.array([0.5, 0.5, 0.5]), 0.0)
    assert np.all(ei >= 0)
    assert ei[1] > ei[0] > ei[2]
    # 零方差时无 NaN
    ei0 = expected_improvement(np.array([0.0]), np.array([0.0]), 0.0)
    assert np.isfinite(ei0[0])
    print("✓ test_ei_formula")


def test_cold_start():
    space = make_space()
    bo = BayesianOptimizer(space, batch_size=4, seed=42)
    bo.fit([make_observations(1, seed=0)[0]])
    result = bo.recommend_json()
    assert result["status"] == "cold_start"
    assert len(result["recommendations"]) == 4
    for r in result["recommendations"]:
        assert r["predicted_mean"] is None
        # 冷启动点必须落在空间内且不与已观测重复
        x = space.encode(r["conditions"])
        assert not np.all(np.isclose(bo.X_obs, x, atol=1e-9), axis=1).any()
    print("✓ test_cold_start")


def test_validation_errors():
    space = make_space()
    obs = make_observations(5, seed=1)

    bad_cat = [dict(obs[0], ligand="L99")]
    try:
        BayesianOptimizer(space, seed=0).fit(bad_cat)
        raise AssertionError("非法类别值未报错")
    except ValueError as e:
        assert "L99" in str(e)

    bad_cont = [dict(obs[0], temperature=999.0)]
    try:
        BayesianOptimizer(space, seed=0).fit(bad_cont)
        raise AssertionError("越界连续值未报错")
    except ValueError:
        pass

    nan_row = {**obs[0], "yield": float("nan")}
    bo = BayesianOptimizer(space, seed=0)
    bo.fit([nan_row] + obs)
    assert len(bo.y_obs) == len(obs), "NaN 行应被剔除"
    assert any("剔除" in w for w in bo.warnings)

    dup = [{**obs[0], "yield": 50.0}, {**obs[0], "yield": 80.0}]
    bo = BayesianOptimizer(space, seed=0)
    bo.fit(dup)
    assert len(bo.y_obs) == 1 and bo.y_obs[0] == 80.0, "重复条件应保留最后一条"
    assert any("重复" in w for w in bo.warnings)
    print("✓ test_validation_errors")


def test_recommendation_schema_and_dedup():
    space = make_space()
    bo = BayesianOptimizer(space, batch_size=5, seed=42)
    bo.fit(make_observations(15, seed=2))
    result = bo.recommend_json()
    for key in ("skill", "status", "model", "objective", "n_observed",
                "observed_best", "recommendations", "diagnostics", "citation"):
        assert key in result, f"输出缺少键: {key}"
    assert result["skill"] == "chem-edbo-recommend-next-batch"
    assert result["status"] == "ok"
    recs = result["recommendations"]
    assert len(recs) == 5
    seen = set()
    for r in recs:
        for k in ("rank", "conditions", "predicted_mean", "predicted_std",
                  "expected_improvement", "confidence"):
            assert k in r
        assert r["predicted_std"] >= 0 and r["expected_improvement"] >= 0
        # 推荐点必须落在空间内
        x = space.encode(r["conditions"])
        assert np.all((x >= 0) & (x <= 1))
        # 批次内与已观测均不重复
        key = tuple(np.round(x, 9))
        assert key not in seen, "批次内出现重复推荐"
        seen.add(key)
        assert not np.all(np.isclose(bo.X_obs, x, atol=1e-9), axis=1).any(), "推荐与已观测重复"
    assert "log_marginal_likelihood" in result["diagnostics"]
    print("✓ test_recommendation_schema_and_dedup")


def test_determinism():
    space = make_space()
    obs = make_observations(15, seed=3)
    r1 = BayesianOptimizer(space, batch_size=5, seed=7).fit(obs).recommend_json()
    r2 = BayesianOptimizer(space, batch_size=5, seed=7).fit(obs).recommend_json()
    assert r1["recommendations"] == r2["recommendations"], "相同 seed 结果不一致"
    print("✓ test_determinism")


def test_minimize_direction():
    space = ReactionSpace.from_dict(
        {
            "name": "minimize",
            "objective": {"name": "cost", "direction": "minimize"},
            "descriptors": [
                {"name": "x", "type": "continuous", "min": 0.0, "max": 1.0},
            ],
        }
    )
    obs = [{"x": 0.0 + 0.2 * i, "cost": 10.0 - i} for i in range(5)]  # 越小越好：x 越大 cost 越低
    bo = BayesianOptimizer(space, batch_size=2, seed=0)
    bo.fit(obs)
    result = bo.recommend_json()
    assert result["observed_best"] == 6.0, "minimize 方向应取最小 cost 为最优"
    assert result["recommendations"][0]["conditions"]["x"] > 0.8, "应推荐 cost 更低的 x"
    print("✓ test_minimize_direction")


def test_full_enumeration_space():
    space = ReactionSpace.from_dict(
        {
            "name": "grid",
            "objective": {"name": "yield", "direction": "maximize"},
            "descriptors": [
                {"name": "A", "type": "categorical", "options": ["a1", "a2", "a3"]},
                {"name": "B", "type": "categorical", "options": ["b1", "b2"]},
            ],
        }
    )
    assert space._full_enumeration().shape == (6, 5), "全枚举点数应为 3×2=6"
    bo = BayesianOptimizer(space, batch_size=2, n_candidates=10, seed=0)
    bo.fit([{"A": "a1", "B": "b1", "yield": 10.0}])
    recs = bo.recommend_json()["recommendations"]
    assert len(recs) == 2
    assert all(r["conditions"]["A"] in ("a1", "a2", "a3") for r in recs)
    print("✓ test_full_enumeration_space")


def test_branin_optimization():
    """Branin 函数（2D 连续，minimize，全局最优 0.3979）：BO 应显著优于随机初始。"""

    def branin(u):
        x1, x2 = 15 * u[0] - 5, 15 * u[1]
        a, b, c, r, s, t = 1.0, 5.1 / (4 * np.pi**2), 5 / np.pi, 6.0, 10.0, 1 / (8 * np.pi)
        return a * (x2 - b * x1**2 + c * x1 - r) ** 2 + s * (1 - t) * np.cos(x1) + s

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
    rng = np.random.default_rng(3)  # 该种子下初始最优 5.01，BO 收敛至 ≈0.41
    obs = [{"u1": float(rng.uniform()), "u2": float(rng.uniform())} for _ in range(10)]
    for r in obs:
        r["f"] = branin([r["u1"], r["u2"]])
    init_best = min(r["f"] for r in obs)

    bo = BayesianOptimizer(space, batch_size=4, n_candidates=3000, gp_restarts=3, seed=5)
    bo.fit(obs)
    for _ in range(3):
        recs = bo.recommend()
        for r in recs:
            cond = dict(r["conditions"])
            cond["f"] = branin([cond["u1"], cond["u2"]])
            obs.append(cond)
        bo.fit(obs)
    final_best = min(r["f"] for r in obs)
    print(f"    Branin: 初始最优 {init_best:.2f} → 3 轮 BO 后 {final_best:.2f}（全局最优 0.40）")
    assert final_best < init_best, "BO 未优于随机初始"
    assert final_best < 2.0, f"BO 未收敛到 Branin 全局最优邻域: {final_best:.2f}"
    print("✓ test_branin_optimization")


def main() -> int:
    fix_console_encoding()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception:
            failed += 1
            print(f"✗ {t.__name__}")
            traceback.print_exc()
    print(f"\n{'全部通过' if failed == 0 else f'{failed} 个失败'}（共 {len(tests)} 个测试）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
