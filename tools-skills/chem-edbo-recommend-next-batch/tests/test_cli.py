# -*- coding: utf-8 -*-
"""
test_cli.py —— CLI 端到端测试（recommend_next_batch.py + 报告 + 绘图）。

运行方式：
    python tests/test_cli.py        # 独立运行
    pytest tests/test_cli.py        # 也兼容 pytest
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "recommend_next_batch.py"

SPACE = {
    "name": "cli_test_space",
    "objective": {"name": "yield", "direction": "maximize", "bounds": [0, 100]},
    "descriptors": [
        {"name": "solvent", "type": "categorical", "options": ["DMA", "NMP", "DMF"]},
        {"name": "temperature", "type": "continuous", "min": 40.0, "max": 120.0, "unit": "°C"},
        {"name": "concentration", "type": "continuous", "min": 0.05, "max": 0.30, "unit": "M"},
    ],
}

DATA = """solvent,temperature,concentration,yield
DMA,80,0.1,45.2
DMA,100,0.1,61.8
NMP,90,0.2,38.4
DMF,70,0.1,52.1
DMA,110,0.15,66.3
NMP,60,0.25,41.9
DMF,120,0.2,58.7
DMA,90,0.3,55.0
"""


def run_cli(tmp: Path) -> subprocess.CompletedProcess:
    space_p = tmp / "space.json"
    data_p = tmp / "data.csv"
    out_p = tmp / "rec.json"
    report_p = tmp / "report.md"
    plot_p = tmp / "rec.png"
    space_p.write_text(json.dumps(SPACE, ensure_ascii=False), encoding="utf-8")
    data_p.write_text(DATA, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CLI),
         "--space", str(space_p), "--data", str(data_p),
         "--batch-size", "3", "--seed", "42",
         "--output", str(out_p), "--report", str(report_p), "--plot", str(plot_p)],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
    ), space_p, data_p, out_p, report_p, plot_p


def test_cli_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proc, space_p, data_p, out_p, report_p, plot_p = run_cli(tmp)
        assert proc.returncode == 0, f"CLI 退出码 {proc.returncode}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"

        result = json.loads(out_p.read_text(encoding="utf-8"))
        assert result["status"] == "ok"
        assert result["n_observed"] == 8
        assert len(result["recommendations"]) == 3
        for r in result["recommendations"]:
            assert r["conditions"]["solvent"] in ("DMA", "NMP", "DMF")
            assert 40 <= r["conditions"]["temperature"] <= 120
            assert r["predicted_mean"] is not None

        report = report_p.read_text(encoding="utf-8")
        assert "推荐条件" in report and "EI" in report, "报告缺少关键小节"
        assert "Shields" in report, "报告缺少引用"

        assert plot_p.exists() and plot_p.stat().st_size > 1000, "绘图文件缺失或为空"
    print("✓ test_cli_end_to_end")


def test_cli_invalid_data():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        space_p = tmp / "space.json"
        space_p.write_text(json.dumps(SPACE, ensure_ascii=False), encoding="utf-8")
        bad = tmp / "bad.csv"
        bad.write_text("solvent,temperature,concentration,yield\nX,80,0.1,45\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CLI), "--space", str(space_p), "--data", str(bad),
             "--batch-size", "2", "--output", str(tmp / "out.json")],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        assert proc.returncode == 2, "非法类别值应返回退出码 2"
        assert "错误" in proc.stderr
    print("✓ test_cli_invalid_data")


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from edbo_core import fix_console_encoding

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
