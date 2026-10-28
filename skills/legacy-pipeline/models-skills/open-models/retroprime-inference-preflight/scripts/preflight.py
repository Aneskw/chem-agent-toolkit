#!/usr/bin/env python3
"""Inspect RetroPrime inference resources without loading or executing models."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


WEIGHTS = {
    "p2s": "retroprime/transformer_model/experiments/checkpoints/USPTO-50K_pos_pred/USPTO-50K_pos_pred_model_step_90000.pt",
    "s2r": "retroprime/transformer_model/experiments/checkpoints/USPTO-50K_S2R/USPTO-50K_S2R_model_step_100000.pt",
}
SCRIPTS = (
    "run_example.sh",
    "retroprime/transformer_model/script/smi_tokenizer.py",
    "retroprime/transformer_model/script/evaluate.py",
    "retroprime/transformer_model/script/mix_c2c_top3_after_rerank.py",
    "retroprime/transformer_model/translate.py",
)


def inspect(root: Path, input_file: Path | None = None, check_environment: bool = True) -> dict:
    missing_scripts = [path for path in SCRIPTS if not (root / path).is_file()]
    missing_weights = [key for key, path in WEIGHTS.items() if not (root / path).is_file()]
    missing_modules = [name for name in ("rdkit", "torch", "pandas")
                       if importlib.util.find_spec(name) is None] if check_environment else []
    input_errors: list[str] = []
    product_count = None
    if input_file is not None:
        if not input_file.is_file():
            input_errors.append("input file is missing")
        else:
            try:
                products = [x.strip() for x in input_file.read_text(encoding="utf-8").splitlines()]
                product_count = len(products)
                if not products or any(not x for x in products):
                    input_errors.append("input must contain one nonempty product SMILES per line")
            except (OSError, UnicodeError) as exc:
                input_errors.append(f"cannot read input file: {exc}")
    warnings = []
    run_script = root / "run_example.sh"
    if run_script.is_file():
        content = run_script.read_text(encoding="utf-8", errors="replace")
        for key, path in WEIGHTS.items():
            expected = Path(path).name
            if expected not in content:
                warnings.append(f"{key} pinned weight filename differs from run_example.sh; inspect your checkout")
    readme = root / "README.md"
    if readme.is_file():
        content = readme.read_text(encoding="utf-8", errors="replace")
        if "_model.pt" in content and any("_model_step_" in p for p in WEIGHTS.values()):
            warnings.append("README example uses generic weight names while pinned run_example.sh uses step-numbered names")
    ready = not (missing_scripts or missing_weights or missing_modules or input_errors)
    return {
        "ok": ready,
        "status": "ready_to_attempt" if ready and check_environment else
                  "files_ready_environment_unchecked" if ready else "blocked_resources",
        "missing_scripts": missing_scripts,
        "missing_weights": missing_weights,
        "missing_modules": missing_modules,
        "input_errors": input_errors,
        "product_count": product_count,
        "warnings": warnings,
        "expected_weight_paths": WEIGHTS,
        "environment_checked": check_environment,
        "execution_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--skip-env-check", action="store_true")
    args = parser.parse_args()
    result = inspect(args.source_root.resolve(), args.input, not args.skip_env_check)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
