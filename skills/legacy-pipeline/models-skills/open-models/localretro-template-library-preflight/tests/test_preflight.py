from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from preflight import check  # noqa: E402


def test_missing_source_is_blocked(tmp_path):
    result = check(tmp_path, "USPTO_50K", env_check=False)
    assert not result["ok"] and "data/USPTO_50K/raw_train.csv" in result["missing_files"]
    assert result["execution_performed"] is False


def test_file_layout_and_readme_mismatch_warning(tmp_path):
    for relative in ("preprocessing/Extract_from_train_data.py",
                     "LocalTemplate/template_extractor.py",
                     "LocalTemplate/template_extract_utils.py"):
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("# fixture\n")
    data = tmp_path / "data/USPTO_50K"
    data.mkdir(parents=True)
    (data / "raw_train.csv").write_text("reactants>reagents>production\nCCO>>CC=O\n")
    (data / "train_class.csv").write_text("class\n1\n")
    result = check(tmp_path, "USPTO_50K", env_check=False)
    assert result["ok"] and result["warnings"]
    assert result["command"] == "python Extract_from_train_data.py -d USPTO_50K"


def test_wrong_schema_is_blocked(tmp_path):
    data = tmp_path / "data/USPTO_50K"
    data.mkdir(parents=True)
    (data / "raw_train.csv").write_text("reaction_smiles\nCCO>>CC=O\n")
    result = check(tmp_path, "USPTO_50K", env_check=False)
    assert not result["ok"] and "missing" in result["csv_error"]
