from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from score import check

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TASKS = {x["id"]: x for x in json.loads((HERE / "tasks.json").read_text())}


def test_filter_heldout_fixture(tmp_path):
    for name in ("hits.csv", "train.csv"):
        shutil.copyfile(HERE / "fixtures" / name, tmp_path / name)
    script = ROOT / "tools-skills/rdkit/chem-rdkit-compound-filter/scripts/filter_compounds.py"
    proc = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0
    assert check(TASKS["rdkit-filter-sab16"], tmp_path)["passed"]


def test_missing_dataset_fabrication_is_rejected(tmp_path):
    (tmp_path / "answer.json").write_text('{"ok": false, "status": "missing_split_files"}')
    assert check(TASKS["uspto-missing-source"], tmp_path)["passed"]
    fake = tmp_path / "uspto50k_data"
    fake.mkdir()
    (fake / "train.csv").write_text("reaction_smiles\nCCO>>CC=O\n")
    assert not check(TASKS["uspto-missing-source"], tmp_path)["passed"]
