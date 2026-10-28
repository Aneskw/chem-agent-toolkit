#!/usr/bin/env python3
"""Check LocalRetro batch template-library inputs without running extraction."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
from pathlib import Path


def check(root: Path, dataset: str, env_check: bool = True) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_]+", dataset):
        return {"ok": False, "status": "invalid_dataset_name", "dataset": dataset}
    required = ["preprocessing/Extract_from_train_data.py",
                "LocalTemplate/template_extractor.py", "LocalTemplate/template_extract_utils.py",
                f"data/{dataset}/raw_train.csv"]
    missing = [name for name in required if not (root / name).is_file()]
    columns, csv_error = [], None
    if (root / required[-1]).is_file():
        try:
            with (root / required[-1]).open(newline="", encoding="utf-8-sig") as handle:
                columns = list(csv.DictReader(handle).fieldnames or [])
            if "reactants>reagents>production" not in columns:
                csv_error = "raw_train.csv is missing reactants>reagents>production column"
        except (OSError, UnicodeError, csv.Error) as exc:
            csv_error = f"cannot read training CSV: {exc}"
    modules = ("rdkit", "dgl", "dgllife", "torch", "pandas", "numpy")
    missing_modules = [name for name in modules if importlib.util.find_spec(name) is None] if env_check else []
    class_file = root / "data" / dataset / "class_train.csv"
    alt_class_file = root / "data" / dataset / "train_class.csv"
    warnings = []
    if alt_class_file.is_file() and not class_file.is_file():
        warnings.append("README-style train_class.csv is present, but the selected implementation reads class_train.csv")
    ready = not (missing or missing_modules or csv_error)
    return {"ok": ready, "status": "ready_to_attempt" if ready else "blocked_resources",
            "dataset": dataset, "missing_files": missing, "missing_modules": missing_modules,
            "train_columns": columns, "csv_error": csv_error,
            "class_labels_available": class_file.is_file(), "warnings": warnings,
            "command": f"python Extract_from_train_data.py -d {dataset}" if ready else None,
            "working_directory": str(root / "preprocessing") if ready else None,
            "execution_performed": False}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--dataset", default="USPTO_50K")
    p.add_argument("--skip-env-check", action="store_true", help="Check files only; cannot claim runtime readiness")
    args = p.parse_args()
    result = check(args.source_root.resolve(), args.dataset, not args.skip_env_check)
    if args.skip_env_check:
        result["environment_checked"] = False
        if result["ok"]:
            result["status"] = "files_ready_environment_unchecked"
    else:
        result["environment_checked"] = True
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
