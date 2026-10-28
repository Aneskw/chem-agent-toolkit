from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts/filter_compounds.py"


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def test_filters_alerts_similarity_and_invalid_smiles(tmp_path):
    hits, train, output = tmp_path / "hits.csv", tmp_path / "train.csv", tmp_path / "out.txt"
    write_csv(hits, ["SMILES"], [{"SMILES": x} for x in ["CCO", "c1ccccc1", "O=[N+]([O-])c1ccccc1", "not-a-smiles"]])
    write_csv(train, ["SMILES", "ACTIVITY"], [{"SMILES": "CCO", "ACTIVITY": "1"}, {"SMILES": "CCN", "ACTIVITY": "0"}])
    proc = subprocess.run([sys.executable, str(SCRIPT), "--hits", str(hits), "--train", str(train), "--output", str(output)], capture_output=True, text=True)
    summary = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert output.read_text().splitlines() == ["c1ccccc1"]
    assert summary["retained"] == 1
    assert summary["rejected"] == {"invalid_smiles": 1, "structural_alert": 1, "similarity": 1}


def test_similarity_boundary_is_strict(tmp_path):
    hits, train, output = tmp_path / "hits.csv", tmp_path / "train.csv", tmp_path / "out.txt"
    write_csv(hits, ["SMILES"], [{"SMILES": "CCO"}])
    write_csv(train, ["SMILES", "ACTIVITY"], [{"SMILES": "CCO", "ACTIVITY": "1"}])
    proc = subprocess.run([sys.executable, str(SCRIPT), "--hits", str(hits), "--train", str(train), "--output", str(output), "--similarity-threshold", "1.0"], capture_output=True, text=True)
    assert proc.returncode == 0 and output.read_text() == ""


def test_missing_activity_column_fails(tmp_path):
    hits, train, output = tmp_path / "hits.csv", tmp_path / "train.csv", tmp_path / "out.txt"
    write_csv(hits, ["SMILES"], [{"SMILES": "CCO"}]); write_csv(train, ["SMILES"], [{"SMILES": "CCN"}])
    proc = subprocess.run([sys.executable, str(SCRIPT), "--hits", str(hits), "--train", str(train), "--output", str(output)], capture_output=True, text=True)
    assert proc.returncode == 2 and json.loads(proc.stdout)["ok"] is False


def test_benchmark_default_paths(tmp_path):
    write_csv(tmp_path / "hits.csv", ["SMILES"], [{"SMILES": "CCO"}, {"SMILES": "c1ccccc1"}])
    write_csv(tmp_path / "train.csv", ["SMILES", "ACTIVITY"], [{"SMILES": "CCO", "ACTIVITY": "1"}])
    proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0
    assert (tmp_path / "pred_results/compound_filter_results.txt").read_text().splitlines() == ["c1ccccc1"]
