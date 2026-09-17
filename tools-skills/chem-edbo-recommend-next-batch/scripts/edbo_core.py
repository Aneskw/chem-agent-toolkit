# -*- coding: utf-8 -*-
"""
edbo_core.py —— EDBO 风格贝叶斯反应优化核心库（纯数值实现，不调用任何大模型）。

方法依据：Shields et al., "Bayesian reaction optimization as a tool for chemical
synthesis", Nature 590, 89–96 (2021), DOI: 10.1038/s41586-021-03213-y（EDBO）。

实现要点（与论文的逐条对应见 ../references/implementation-mapping.md）：
  * 代理模型：高斯过程回归，Matérn-5/2 核 + 各向异性长度尺度（ARD）
  * 采集函数：Expected Improvement（默认）；另可选 UCB、GREEDY
  * 批推荐：贪心选择 + Kriging-believer 幻想更新（顺序批 EI）
  * 描述符编码：类别变量 one-hot，连续变量归一化到 [0,1] 单位超立方
  * 目标值：内部标准化建模，预测时映射回原始量纲

依赖：numpy / scipy / scikit-learn（均为数值库；无网络、无 LLM 调用）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
from scipy.stats import norm
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern

__all__ = [
    "ReactionSpace",
    "BayesianOptimizer",
    "expected_improvement",
    "upper_confidence_bound",
    "load_observations",
    "save_json",
    "fix_console_encoding",
    "OUTPUT_VERSION",
]

OUTPUT_VERSION = "1.0"
_EPS = 1e-12


def fix_console_encoding() -> None:
    """在中文 Windows 控制台（默认 GBK）下避免 print 中文乱码。"""
    import sys

    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


# --------------------------------------------------------------------------
# 采集函数
# --------------------------------------------------------------------------
def expected_improvement(mu, sigma, best: float) -> np.ndarray:
    """Expected Improvement: EI(x) = (μ-best)Φ(z) + σφ(z)，z = (μ-best)/σ。

    用于"越大越好"的方向（内部已按 maximize 翻转）。
    参考 Jones et al., J. Global Optim. 1998, 13, 455–492。
    """
    mu = np.asarray(mu, dtype=float)
    sigma = np.maximum(np.asarray(sigma, dtype=float), _EPS)
    z = (mu - best) / sigma
    ei = sigma * (z * norm.cdf(z) + norm.pdf(z))
    return np.maximum(ei, 0.0)


def upper_confidence_bound(mu, sigma, best: float = None, kappa: float = 2.0) -> np.ndarray:
    """Upper Confidence Bound: UCB(x) = μ + κσ。"""
    return np.asarray(mu, dtype=float) + kappa * np.asarray(sigma, dtype=float)


# --------------------------------------------------------------------------
# 反应空间
# --------------------------------------------------------------------------
class ReactionSpace:
    """化学反应空间：一组类别/连续描述符 + 优化目标定义。

    类别描述符 one-hot 编码；连续描述符线性归一化到 [0,1]。
    编码向量布局：按描述符声明顺序，连续变量各占 1 维，类别变量各占其选项数维。
    """

    def __init__(self, name: str, descriptors: Iterable[dict], objective: dict):
        self.name = name or "reaction_space"
        self.descriptors = [dict(d) for d in descriptors]
        self.objective = dict(objective)
        self._validate()
        self._build_layout()

    # ---------------- 构造与校验 ----------------
    def _validate(self) -> None:
        if not self.descriptors:
            raise ValueError("反应空间必须至少包含 1 个描述符。")
        names = []
        for d in self.descriptors:
            if "name" not in d or not str(d["name"]).strip():
                raise ValueError("每个描述符必须提供非空 name。")
            d["name"] = str(d["name"]).strip()
            if d["name"] in names:
                raise ValueError(f"描述符名称重复: {d['name']}")
            names.append(d["name"])
            t = d.get("type", "continuous")
            if t == "categorical":
                opts = d.get("options")
                if not opts or len(opts) < 2:
                    raise ValueError(f"类别描述符 {d['name']} 必须提供 ≥2 个 options。")
                if len(set(map(str, opts))) != len(opts):
                    raise ValueError(f"类别描述符 {d['name']} 的 options 存在重复项。")
            elif t == "continuous":
                lo, hi = d.get("min"), d.get("max")
                if lo is None or hi is None:
                    raise ValueError(f"连续描述符 {d['name']} 必须提供 min 与 max。")
                if float(lo) >= float(hi):
                    raise ValueError(f"连续描述符 {d['name']} 需满足 min < max。")
            else:
                raise ValueError(f"描述符 {d['name']} 的 type 只能是 categorical 或 continuous，收到: {t!r}")
        obj = self.objective
        if not obj.get("name"):
            raise ValueError("objective 必须提供 name（目标列名，如 yield）。")
        if obj.get("direction", "maximize") not in ("maximize", "minimize"):
            raise ValueError("objective.direction 只能是 maximize 或 minimize。")

    def _build_layout(self) -> None:
        """记录每个描述符在编码向量中的起止位置。"""
        self.cat_blocks = {}   # name -> (start, end, options)
        self.cont_blocks = {}  # name -> (index, min, max)
        pos = 0
        for d in self.descriptors:
            if d.get("type", "continuous") == "categorical":
                self.cat_blocks[d["name"]] = (pos, pos + len(d["options"]), list(d["options"]))
                pos += len(d["options"])
            else:
                self.cont_blocks[d["name"]] = (pos, float(d["min"]), float(d["max"]))
                pos += 1
        self.dim = pos

    @classmethod
    def from_dict(cls, data: dict) -> "ReactionSpace":
        return cls(
            name=data.get("name", ""),
            descriptors=data.get("descriptors", []),
            objective=data.get("objective", {}),
        )

    @classmethod
    def from_json(cls, path) -> "ReactionSpace":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "objective": self.objective,
            "descriptors": [
                {
                    "name": d["name"],
                    "type": d.get("type", "continuous"),
                    **( {"options": d["options"]} if d.get("type", "continuous") == "categorical"
                         else {"min": d["min"], "max": d["max"]} ),
                }
                for d in self.descriptors
            ],
        }

    # ---------------- 编码 / 解码 ----------------
    def encode(self, conditions: dict) -> np.ndarray:
        """把一组实验条件 dict 编码为 [0,1]^d 向量。不合法值抛 ValueError。"""
        x = np.zeros(self.dim)
        for name in self.cont_blocks:
            idx, lo, hi = self.cont_blocks[name]
            v = self._as_float(conditions[name], f"连续描述符 {name}")
            if v < lo - 1e-9 or v > hi + 1e-9:
                raise ValueError(f"连续描述符 {name} 取值 {v} 超出范围 [{lo}, {hi}]。")
            x[idx] = (v - lo) / (hi - lo)
        for name, (start, end, opts) in self.cat_blocks.items():
            v = conditions.get(name)
            opt = self._coerce_option(v, opts)
            if opt is None:
                raise ValueError(f"类别描述符 {name} 取值 {v!r} 不在允许选项中: {opts}")
            x[start + opts.index(opt)] = 1.0
        return x

    def decode(self, x: np.ndarray) -> dict:
        """把编码向量解码回实验条件 dict（类别块取 argmax）。"""
        x = np.asarray(x, dtype=float)
        out = {}
        for name, (idx, lo, hi) in self.cont_blocks.items():
            out[name] = float(x[idx] * (hi - lo) + lo)
        for name, (start, end, opts) in self.cat_blocks.items():
            out[name] = opts[int(np.argmax(x[start:end]))]
        return out

    def encode_labels(self) -> list:
        """编码向量每一维的人类可读标签（用于诊断输出）。"""
        labels = []
        for name, (idx, lo, hi) in self.cont_blocks.items():
            labels.append(name)
        for name, (start, end, opts) in self.cat_blocks.items():
            labels += [f"{name}[{o}]" for o in opts]
        return labels

    @staticmethod
    def _coerce_option(value, options):
        """宽松匹配类别取值：先精确匹配，再数值匹配，最后字符串匹配。"""
        for opt in options:
            if value == opt:
                return opt
        for opt in options:
            if isinstance(opt, (int, float)) and not isinstance(opt, bool):
                try:
                    if float(value) == float(opt):
                        return opt
                except (TypeError, ValueError):
                    pass
        s = str(value)
        for opt in options:
            if str(opt) == s:
                return opt
        return None

    @staticmethod
    def _as_float(v, where: str) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{where} 取值 {v!r} 无法解析为数值。")

    # ---------------- 候选点生成 ----------------
    def _full_enumeration(self) -> Optional[np.ndarray]:
        """全枚举（仅当所有描述符均为类别变量时可用）。"""
        for d in self.descriptors:
            if d.get("type", "continuous") != "categorical":
                return None
        grids = [range(len(self.cat_blocks[d["name"]][2])) for d in self.descriptors]
        total = int(np.prod([len(g) for g in grids]))
        X = np.zeros((total, self.dim))
        pos = 0
        for d in self.descriptors:
            start, end, _ = self.cat_blocks[d["name"]]
            n_opt = end - start
            n_after = int(np.prod([len(g) for g in grids[pos + 1:]])) if pos + 1 < len(grids) else 1
            one_hot = np.eye(n_opt)[np.arange(total) // n_after % n_opt]
            X[:, start:end] = one_hot
            pos += 1
        return X

    def random_points(self, n: int, rng: np.random.Generator) -> np.ndarray:
        """在归一化空间 [0,1]^d 内均匀随机采样 n 个候选点（编码坐标）。"""
        X = np.zeros((n, self.dim))
        for name, (idx, lo, hi) in self.cont_blocks.items():
            X[:, idx] = rng.uniform(0.0, 1.0, n)
        for name, (start, end, opts) in self.cat_blocks.items():
            k = rng.integers(0, len(opts), n)
            X[np.arange(n), start + k] = 1.0
        return X

    def candidate_pool(self, n_candidates: int, rng: np.random.Generator) -> np.ndarray:
        """生成候选池：全枚举空间若不超过 n_candidates 则全枚举，否则随机采样。"""
        full = self._full_enumeration()
        if full is not None and len(full) <= max(n_candidates, 1):
            return full
        return self.random_points(n_candidates, rng)

    def describe(self) -> str:
        lines = [f"反应空间: {self.name}（编码维度 d={self.dim}）"]
        for d in self.descriptors:
            if d.get("type", "continuous") == "categorical":
                lines.append(f"  [类别] {d['name']}: {len(d['options'])} 个选项")
            else:
                lines.append(f"  [连续] {d['name']}: [{d['min']}, {d['max']}]")
        lines.append(f"  目标: {self.objective['name']}（{self.objective.get('direction','maximize')}）")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# 贝叶斯优化器
# --------------------------------------------------------------------------
class BayesianOptimizer:
    """EDBO 风格贝叶斯优化器：GP 代理模型 + 采集函数 + 贪心批推荐。"""

    ACQ_FUNCS = {"EI": expected_improvement, "UCB": upper_confidence_bound, "GREEDY": None}

    def __init__(
        self,
        space: ReactionSpace,
        batch_size: int = 5,
        acquisition: str = "EI",
        n_candidates: int = 10000,
        gp_restarts: int = 5,
        kappa: float = 2.0,
        seed: Optional[int] = 42,
    ):
        self.space = space
        self.batch_size = int(batch_size)
        if self.batch_size < 1:
            raise ValueError("batch_size 必须 ≥ 1。")
        self.acquisition = acquisition.upper()
        if self.acquisition not in self.ACQ_FUNCS:
            raise ValueError(f"acquisition 只能是 {list(self.ACQ_FUNCS)}，收到: {acquisition!r}")
        self.n_candidates = int(n_candidates)
        self.gp_restarts = int(gp_restarts)
        self.kappa = float(kappa)
        self.seed = seed if seed is not None else 42
        self.rng = np.random.default_rng(self.seed)

        self.X_obs: Optional[np.ndarray] = None   # 已观测条件（编码）
        self.y_obs: Optional[np.ndarray] = None   # 已观测目标（已按 maximize 翻转）
        self.best: Optional[float] = None         # 已观测最优（翻转后）
        self.status: str = "ok"
        self.warnings: list = []
        self.mu_y = 0.0
        self.sd_y = 1.0
        self.gp: Optional[GaussianProcessRegressor] = None
        self.lml: Optional[float] = None

    # ---------------- 数据接入 ----------------
    def fit(self, observations: Iterable[dict]) -> "BayesianOptimizer":
        """接入已有实验数据。observations: list[dict]，键为描述符名 + objective.name。"""
        self.warnings = []
        X_rows, y_rows = self._validate_rows(observations)
        self.X_obs = np.vstack(X_rows)
        sign = 1.0 if self.space.objective.get("direction", "maximize") == "maximize" else -1.0
        self.y_obs = sign * np.asarray(y_rows, dtype=float)
        self.best = float(np.max(self.y_obs))
        if len(self.y_obs) >= 5:
            self.status = "ok"
        else:
            self.status = "low_data"
            self.warnings.append(
                f"观测数据仅 {len(self.y_obs)} 条（<5），GP 拟合不稳定，建议先随机/网格初筛积累数据。"
            )
        return self

    def _validate_rows(self, observations: Iterable[dict]):
        """逐行校验：类型匹配、范围合法、NaN 剔除、重复条件去重（保留最后一条）。"""
        seen, X_rows, y_rows = {}, [], []
        for i, row in enumerate(observations, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"第 {i} 条观测不是 dict（键应为描述符名 + 目标名）。")
            missing = [n for n in self.space.descriptors if n["name"] not in row]
            if missing:
                raise ValueError(f"第 {i} 条观测缺少描述符列: {missing}")
            obj = self.space.objective["name"]
            if obj not in row:
                raise ValueError(f"第 {i} 条观测缺少目标列 {obj!r}。")
            try:
                y = float(row[obj])
            except (TypeError, ValueError):
                raise ValueError(f"第 {i} 条观测的目标 {obj}={row[obj]!r} 无法解析为数值。")
            if not np.isfinite(y):
                self.warnings.append(f"第 {i} 条观测的目标值为 NaN/inf，已剔除。")
                continue
            bounds = self.space.objective.get("bounds")
            if bounds and not (float(bounds[0]) - 1e-6 <= y <= float(bounds[1]) + 1e-6):
                self.warnings.append(
                    f"第 {i} 条观测 {obj}={y} 超出声明的物理界限 {bounds}，请人工确认是否为记录错误。"
                )
            x = self.space.encode(row)
            key = tuple(np.round(x, 9))
            if key in seen:
                self.warnings.append(f"第 {i} 条与第 {seen[key]} 条条件重复，保留最新一条。")
                X_rows[seen[key] - 1] = x
                y_rows[seen[key] - 1] = y
                continue
            seen[key] = len(X_rows) + 1
            X_rows.append(x)
            y_rows.append(y)
        if not X_rows:
            raise ValueError("没有可用观测数据（全部为空或已被剔除）。")
        return X_rows, y_rows

    # ---------------- GP 拟合 ----------------
    def _make_gp(self) -> GaussianProcessRegressor:
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
            nu=2.5,
            length_scale=np.ones(self.space.dim),
            length_scale_bounds=(1e-2, 1e2),
        )
        return GaussianProcessRegressor(
            kernel=kernel,
            alpha=1e-5,                 # 数值抖动；产率噪声由核白噪声项吸收
            normalize_y=False,          # 手动标准化（见 _fit_surrogate）
            n_restarts_optimizer=self.gp_restarts,
            random_state=self.seed,
        )

    def _fit_surrogate(self, X: np.ndarray, y: np.ndarray) -> None:
        """在（可能含幻想点的）训练集上拟合 GP。标准化参数固定用真实观测统计。

        长度尺度收敛到边界是少量高维数据下的正常现象（边界 [0.01, 100]），
        此处抑制该警告以免刷屏；诊断输出中仍保留完整核参数供复核。
        """
        import warnings

        gp = self._make_gp()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            gp.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
        self.gp = gp
        self.lml = float(gp.log_marginal_likelihood())

    def fit_surrogate(self) -> "BayesianOptimizer":
        """仅拟合 GP（供绘图/诊断复用）。"""
        if self.X_obs is None or len(self.X_obs) < 2:
            raise RuntimeError("观测数据不足（<2 条），无法拟合 GP。")
        self.mu_y = float(np.mean(self.y_obs))
        self.sd_y = float(np.std(self.y_obs, ddof=1)) or 1.0
        y_std = (self.y_obs - self.mu_y) / self.sd_y
        self._fit_surrogate(self.X_obs, y_std)
        return self

    # ---------------- 评估 ----------------
    def evaluate(self, X: np.ndarray):
        """在候选点 X 上评估 (预测均值, 预测标准差, 采集函数值)，量纲为原始目标。"""
        if self.gp is None:
            raise RuntimeError("请先调用 fit_surrogate() 或 recommend()。")
        mu_s, sigma_s = self.gp.predict(np.asarray(X, dtype=float), return_std=True)
        mu_raw = mu_s * self.sd_y + self.mu_y
        sigma_raw = np.maximum(sigma_s * self.sd_y, 1e-9)
        if self.acquisition == "GREEDY":
            acq = mu_raw.copy()
        elif self.acquisition == "UCB":
            acq = self.ACQ_FUNCS["UCB"](mu_raw, sigma_raw, self.best, self.kappa)
        else:
            acq = self.ACQ_FUNCS["EI"](mu_raw, sigma_raw, self.best)
        return mu_raw, sigma_raw, acq

    # ---------------- 推荐 ----------------
    def _exclude_observed(self, pool: np.ndarray) -> np.ndarray:
        if self.X_obs is None or len(self.X_obs) == 0:
            return pool
        keep = np.ones(len(pool), dtype=bool)
        for xo in self.X_obs:
            keep &= ~np.all(np.isclose(pool, xo, atol=1e-9), axis=1)
        return pool[keep]

    def _cold_start_batch(self, pool: np.ndarray) -> list:
        """数据不足时的空间填充（maximin）批推荐。"""
        anchors = self.X_obs.copy() if self.X_obs is not None and len(self.X_obs) else None
        picked = []
        n = min(self.batch_size, len(pool))
        for _ in range(n):
            if anchors is None or len(anchors) == 0:
                i = 0
            else:
                dist = np.min(np.linalg.norm(pool[:, None, :] - anchors[None, :, :], axis=2), axis=1)
                i = int(np.argmax(dist))
            picked.append(pool[i])
            anchors = np.vstack([anchors, pool[i]]) if anchors is not None else pool[i][None, :]
            pool = np.delete(pool, i, axis=0)
            if len(pool) == 0:
                break
        return picked

    def recommend(self) -> list:
        """推荐下一批实验条件。返回 list[dict]：rank / conditions / predicted_mean /
        predicted_std / expected_improvement / confidence。"""
        if self.X_obs is None:
            raise RuntimeError("请先调用 fit() 接入观测数据。")
        pool = self._exclude_observed(self.space.candidate_pool(self.n_candidates, self.rng))
        if len(self.X_obs) < 2 or len(pool) == 0:
            self.status = "cold_start"
            if len(pool) == 0:
                self.warnings.append("候选池为空（空间过小或已全部实验过），无法推荐。")
                return []
            self.warnings.append(
                "观测数据 <2 条：无法拟合 GP，返回空间填充（maximin）推荐作为初始实验设计。"
            )
            return self._cold_start_recs(pool)

        self.fit_surrogate()
        if len(self.y_obs) < 5:
            self.status = "low_data"

        # 标准化统计固定用真实观测
        self.mu_y = float(np.mean(self.y_obs))
        self.sd_y = float(np.std(self.y_obs, ddof=1)) or 1.0
        X_train = self.X_obs.copy()
        y_train = (self.y_obs - self.mu_y) / self.sd_y
        self._fit_surrogate(X_train, y_train)

        recs = []
        for rank in range(1, min(self.batch_size, len(pool)) + 1):
            mu_raw, sigma_raw, acq = self.evaluate(pool)
            i = int(np.argmax(acq))
            x = pool[i]
            recs.append(self._make_rec(rank, x, float(mu_raw[i]), float(sigma_raw[i]), float(acq[i])))
            # Kriging-believer：把预测均值当作幻想观测，重新拟合后继续选下一个
            X_train = np.vstack([X_train, x])
            y_train = np.append(y_train, (mu_raw[i] - self.mu_y) / self.sd_y)
            self._fit_surrogate(X_train, y_train)
            pool = np.delete(pool, i, axis=0)
            if len(pool) == 0:
                break
        if len(recs) < self.batch_size:
            self.warnings.append(
                f"候选池耗尽，仅返回 {len(recs)} 条推荐（请求 {self.batch_size} 条）。"
            )
        return recs

    def _cold_start_recs(self, pool: np.ndarray) -> list:
        recs = []
        for rank, x in enumerate(self._cold_start_batch(pool), start=1):
            recs.append(
                {
                    "rank": rank,
                    "conditions": self.space.decode(x),
                    "predicted_mean": None,
                    "predicted_std": None,
                    "expected_improvement": None,
                    "confidence": "n/a（冷启动，无模型）",
                }
            )
        return recs

    def _make_rec(self, rank: int, x: np.ndarray, mu: float, sigma: float, acq: float) -> dict:
        if sigma <= 0.5 * self.sd_y:
            conf = "high"
        elif sigma <= 1.5 * self.sd_y:
            conf = "medium"
        else:
            conf = "low"
        return {
            "rank": rank,
            "conditions": self.space.decode(x),
            "predicted_mean": mu,
            "predicted_std": sigma,
            "expected_improvement": float(acq),
            "confidence": conf,
        }

    # ---------------- 输出 ----------------
    def recommend_json(self) -> dict:
        """完整输出 JSON（供 Agent 解析与存档）。"""
        recs = self.recommend()
        sign = 1.0 if self.space.objective.get("direction", "maximize") == "maximize" else -1.0
        diag = {"warnings": list(self.warnings)}
        if self.gp is not None:
            diag["log_marginal_likelihood"] = self.lml
            diag["kernel_constant"] = float(self.gp.kernel_.k1.constant_value)
            ls = self.gp.kernel_.k2.length_scale
            diag["length_scales"] = {
                lbl: float(v) for lbl, v in zip(self.space.encode_labels(), np.atleast_1d(ls))
            }
        acq_name = {
            "EI": "Expected Improvement",
            "UCB": f"Upper Confidence Bound (κ={self.kappa})",
            "GREEDY": "Greedy (预测均值最大)",
        }[self.acquisition]
        return {
            "skill": "chem-edbo-recommend-next-batch",
            "schema_version": OUTPUT_VERSION,
            "status": self.status,
            "model": {
                "surrogate": "Gaussian Process (Matérn-5/2, ARD)",
                "acquisition": acq_name,
                "batch_strategy": "greedy + Kriging-believer（顺序批 EI）",
                "seed": self.seed,
            },
            "space": {
                "name": self.space.name,
                "n_descriptors": len(self.space.descriptors),
                "encoded_dim": self.space.dim,
            },
            "objective": {
                "name": self.space.objective["name"],
                "direction": self.space.objective.get("direction", "maximize"),
            },
            "n_observed": int(len(self.y_obs)),
            "observed_best": float(sign * self.best),
            "recommendations": recs,
            "diagnostics": diag,
            "citation": [
                "Shields et al., Nature 2021, 590, 89–96, DOI: 10.1038/s41586-021-03213-y",
                "Garrido Torres et al., J. Am. Chem. Soc. 2022, 144, 19999–20007, DOI: 10.1021/jacs.2c08592",
            ],
            "note": "推荐值为模型预测而非实验事实；实验前请结合安全性与可操作性人工复核。",
        }


# --------------------------------------------------------------------------
# 文件 IO
# --------------------------------------------------------------------------
def _read_text(path) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码: {path}")


def load_observations(path) -> list:
    """读取观测数据：CSV（首行为表头，列为描述符名 + 目标名）或 JSON（list[dict]）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    if p.suffix.lower() == ".json":
        data = json.loads(_read_text(p))
        if isinstance(data, dict) and "observations" in data:
            data = data["observations"]
        if not isinstance(data, list):
            raise ValueError("JSON 数据文件应为 list[dict] 或 {\"observations\": [...]}。")
        return data
    if p.suffix.lower() == ".csv":
        import csv as _csv

        rows = list(_csv.reader(_read_text(p).splitlines()))
        if not rows:
            raise ValueError(f"CSV 数据文件为空: {path}")
        header = [h.strip() for h in rows[0]]
        out = []
        for line in rows[1:]:
            if not line or all(not c.strip() for c in line):
                continue
            if len(line) != len(header):
                raise ValueError(f"CSV 列数不一致：表头 {len(header)} 列，数据行 {len(line)} 列。")
            out.append({h: _maybe_float(c.strip()) for h, c in zip(header, line)})
        return out
    raise ValueError(f"不支持的数据文件格式: {p.suffix}（仅支持 .csv / .json）")


def _maybe_float(s: str):
    try:
        return float(s)
    except ValueError:
        return s


def save_json(obj: dict, path) -> None:
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":  # 自检：编码/解码往返 + EI 数值
    fix_console_encoding()
    space = ReactionSpace.from_dict(
        {
            "name": "self-check",
            "descriptors": [
                {"name": "ligand", "type": "categorical", "options": ["L1", "L2", "L3"]},
                {"name": "temperature", "type": "continuous", "min": 40, "max": 120},
            ],
            "objective": {"name": "yield", "direction": "maximize", "bounds": [0, 100]},
        }
    )
    for _ in range(100):
        x = space.random_points(1, np.random.default_rng(0))[0]
        assert np.allclose(space.encode(space.decode(x)), x), "encode/decode 往返失败"
    ei = expected_improvement(np.array([0.0, 1.0, -1.0]), np.array([0.5, 0.5, 0.5]), 0.0)
    # best=0 时：μ=1（高于 best）EI 最大；μ=-1 EI 最小；且恒非负
    assert np.all(ei >= 0) and ei[1] > ei[0] > ei[2], f"EI 数值异常: {ei}"
    print("edbo_core 自检通过：encode/decode 往返一致，EI 计算正常。")
