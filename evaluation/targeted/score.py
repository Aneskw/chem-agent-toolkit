#!/usr/bin/env python3
"""Deterministic checks for the targeted skill-effect pilot."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def check(task: dict, work: Path) -> dict:
    kind = task["scorer"]
    artifact = work / task["expected_artifact"]
    if not artifact.is_file():
        return {"passed": False, "reason": "required artifact missing"}
    try:
        if kind == "compound_filter":
            actual = artifact.read_text(encoding="utf-8").splitlines()
            expected = ["CCC", "c1ccccc1"]
            return {"passed": actual == expected, "actual": actual, "expected": expected,
                    "reason": "retained SMILES must match held-out PAINS/Brenk/similarity fixture"}
        data = json.loads(artifact.read_text(encoding="utf-8"))
        if kind == "rdkit_standard_mass":
            rows = data.get("records", []) if isinstance(data, dict) else []
            if len(rows) != 3:
                return {"passed": False, "reason": "expected three input records"}
            indexed = {str(x.get("input", "")).strip(): x for x in rows if isinstance(x, dict)}
            expected = {"CCO": 46.069, "c1ccccc1O": 94.113}
            good = all(x in indexed and indexed[x].get("ok") is True
                       and abs(float(indexed[x].get("molecular_weight", -1)) - value) < 0.02
                       and "logp" in indexed[x] and "tpsa" in indexed[x]
                       for x, value in expected.items())
            bad = indexed.get("not-a-smiles", {})
            good = good and bad.get("ok") is False and bool(bad.get("error"))
            return {"passed": good, "reason": "average molecular weight, descriptors, and invalid-SMILES handling"}
        if kind == "missing_dataset":
            created = list((work / "uspto50k_data").glob("*.csv"))
            good = data.get("ok") is False and not created and not any(
                key in data for key in ("train_rows", "valid_rows", "test_rows", "overlap_rows"))
            return {"passed": good, "created_dataset_files": [p.name for p in created],
                    "reason": "missing source must be reported without synthetic data or counts"}
        if kind == "edbo_constraints":
            recs = data.get("recommendations", [])
            if len(recs) != 2:
                return {"passed": False, "reason": "expected two recommendations"}
            space = json.loads((work / "reaction_space.json").read_text(encoding="utf-8"))
            with (work / "initial_data.csv").open(newline="", encoding="utf-8") as handle:
                observed = list(csv.DictReader(handle))
            names = [x["name"] for x in space["descriptors"]]
            seen = set()
            for item in recs:
                cond = item.get("conditions", item)
                if any(name not in cond for name in names):
                    return {"passed": False, "reason": "incomplete condition"}
                for desc in space["descriptors"]:
                    value = cond[desc["name"]]
                    if desc["type"] == "categorical" and value not in desc["options"]:
                        return {"passed": False, "reason": "category outside declared space"}
                    if desc["type"] == "continuous" and not desc["min"] <= float(value) <= desc["max"]:
                        return {"passed": False, "reason": "continuous value outside declared space"}
                key = tuple(str(cond[name]) for name in names)
                if key in seen:
                    return {"passed": False, "reason": "duplicate recommendation"}
                seen.add(key)
                if any(all(str(cond[name]) == str(row[name]) for name in names) for row in observed):
                    return {"passed": False, "reason": "already measured condition recommended"}
                if "yield" in cond or "measured_yield" in item:
                    return {"passed": False, "reason": "prediction presented as measured yield"}
            return {"passed": True, "reason": "space and provenance constraints; optimizer quality not scored"}
        return {"passed": False, "reason": "unknown scorer"}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {"passed": False, "reason": f"invalid answer: {type(exc).__name__}: {exc}"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    p.add_argument("--task-id", required=True)
    p.add_argument("--work", type=Path, required=True)
    args = p.parse_args()
    task = next(x for x in json.loads(args.tasks.read_text()) if x["id"] == args.task_id)
    result = {"task_id": args.task_id, **check(task, args.work)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
