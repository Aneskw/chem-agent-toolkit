from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from evaluate_candidates import evaluate_case  # noqa: E402


def test_component_order_and_forward_roundtrip():
    row = {"target_product": "CCO", "ground_truth_reactants": "CC.O", "predictions": [
        {"reactants": "O.CC", "forward_product": "CCO"},
        {"reactants": "CCN.O", "forward_product": "CCO"}]}
    result = evaluate_case(row, 2)
    assert result["exact_top1"] and result["roundtrip_top1"]
    assert not result["predictions"][1]["exact_match"]
    assert result["predictions"][1]["roundtrip_correct"]


def test_missing_forward_is_unassessed_and_invalid_precursor_fails():
    row = {"target_product": "CCO", "ground_truth_reactants": "CC.O", "predictions": [
        {"reactants": "not-a-smiles"}]}
    result = evaluate_case(row, 1)
    assert not result["exact_top1"] and result["roundtrip_top1"] is None
    assert result["predictions"][0]["error"]


def test_cli_example():
    result = subprocess.run([sys.executable, str(HERE / "scripts/evaluate_candidates.py"),
                             "--input", str(HERE / "examples/predictions.jsonl")],
                            capture_output=True, text=True)
    assert result.returncode == 0 and '"exact_top1": true' in result.stdout
