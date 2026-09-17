# -*- coding: utf-8 -*-
"""
make_demo_data.py —— 生成演示用反应空间 JSON + 模拟初始产率数据 CSV。

⚠ 数据为合成模拟值（有已知"真实"最优），仅用于演示/测试 skill 的闭环优化流程，
不代表任何真实化学反应。

反应空间风格参照 EDBO 论文基准（Shields et al., Nature 2021, 590, 89–96）：
Pd 催化 C–H 直接芳基化 —— 配体/碱/溶剂为类别变量，温度/浓度为连续变量。

真实最优（yield ≈ 86）：
  ligand=L8, base=K3PO4, solvent=DMA, temperature≈105 °C, concentration≈0.10 M

用法：
  python make_demo_data.py            # 在本目录生成 direct_arylation_space.json 与 initial_data.csv
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from edbo_core import fix_console_encoding  # noqa: E402

fix_console_encoding()

HERE = Path(__file__).resolve().parent

LIGANDS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10", "L11", "L12"]
BASES = ["Cs2CO3", "K2CO3", "K3PO4", "KOAc"]
SOLVENTS = ["DMA", "NMP", "DMF", "dioxane"]

LIGAND_EFFECT = {  # 相对基线（%）
    "L1": 1, "L2": 8, "L3": -3, "L4": -6, "L5": 0, "L6": -2,
    "L7": 4, "L8": 14, "L9": -5, "L10": -1, "L11": 5, "L12": -1,
}
BASE_EFFECT = {"Cs2CO3": 4, "K2CO3": 0, "K3PO4": 10, "KOAc": -3}
SOLVENT_EFFECT = {"DMA": 8, "NMP": 1, "DMF": -1, "dioxane": -4}

TRUE_OPTIMUM = {
    "ligand": "L8", "base": "K3PO4", "solvent": "DMA",
    "temperature": 105.0, "concentration": 0.10,
}


def true_yield(cond: dict, noise: float = 0.0, rng=None) -> float:
    """模拟"真实"产率函数：主效应 + 高斯峰 + 交互 + 噪声，截断到 [3, 97]。

    真实最优 ≈ 88（远低于截断上限，保证演示有可优化空间）。"""
    y = 24.0
    y += LIGAND_EFFECT[cond["ligand"]]
    y += BASE_EFFECT[cond["base"]]
    y += SOLVENT_EFFECT[cond["solvent"]]
    T, C = cond["temperature"], cond["concentration"]
    y += 16.0 * np.exp(-((T - 105.0) ** 2) / (2 * 22.0**2))
    y += 10.0 * np.exp(-((C - 0.10) ** 2) / (2 * 0.12**2))
    if cond["ligand"] == "L8" and cond["base"] == "K3PO4":
        y += 3.0
    if cond["solvent"] == "DMA" and T > 90:
        y += 3.0
    if noise and rng is not None:
        y += rng.normal(0.0, noise)
    return float(np.clip(y, 3.0, 97.0))


SPACE = {
    "name": "Pd 催化直接芳基化（模拟演示）",
    "objective": {"name": "yield", "direction": "maximize", "bounds": [0, 100]},
    "descriptors": [
        {"name": "ligand", "type": "categorical", "options": LIGANDS},
        {"name": "base", "type": "categorical", "options": BASES},
        {"name": "solvent", "type": "categorical", "options": SOLVENTS},
        {"name": "temperature", "type": "continuous", "min": 40.0, "max": 120.0, "unit": "°C"},
        {"name": "concentration", "type": "continuous", "min": 0.05, "max": 0.30, "unit": "M"},
    ],
}


def main() -> None:
    space_path = HERE / "direct_arylation_space.json"
    data_path = HERE / "initial_data.csv"
    space_path.write_text(json.dumps(SPACE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rng = np.random.default_rng(42)
    n_init = 20
    rows = []
    for _ in range(n_init):
        cond = {
            "ligand": str(rng.choice(LIGANDS)),
            "base": str(rng.choice(BASES)),
            "solvent": str(rng.choice(SOLVENTS)),
            "temperature": round(float(rng.uniform(40, 120)), 1),
            "concentration": round(float(rng.uniform(0.05, 0.30)), 3),
        }
        cond["yield"] = round(true_yield(cond, noise=5.5, rng=rng), 1)
        rows.append(cond)

    header = ["ligand", "base", "solvent", "temperature", "concentration", "yield"]
    with open(data_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"已生成: {space_path.name} 与 {data_path.name}（{n_init} 条模拟观测, seed=42）")
    print(f"真实最优参考: {TRUE_OPTIMUM} → yield ≈ {true_yield(TRUE_OPTIMUM):.1f}（模拟值，不在数据文件中）")
    print(f"初始数据中的最优产率: {max(r['yield'] for r in rows):.1f}")


if __name__ == "__main__":
    main()
