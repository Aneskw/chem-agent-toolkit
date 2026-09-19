from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from audit_atom_maps import audit  # noqa: E402


def test_valid_and_reactant_only_maps():
    result = audit("[CH3:1][CH2:2][Br:3]>>[CH3:1][CH2:2]")
    assert result["ok"] and result["reactant_only_maps"] == [3]


def test_duplicate_unmapped_and_new_product_maps():
    assert not audit("[CH3:1][CH2:1]>>[CH3:1][CH2:2]")["ok"]
    assert not audit("CCO>>[CH3:1][OH:2]")["ok"]
    assert not audit("[CH3:1]>>[CH3:1][OH:9]")["ok"]


def test_cli_batch_rejects_bad_row():
    proc = subprocess.run([sys.executable, str(HERE / "scripts/audit_atom_maps.py"),
                           "--input", str(HERE / "examples/reactions.txt")],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and len(proc.stdout.splitlines()) == 2
