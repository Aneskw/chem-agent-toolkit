#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def truthy_activity(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "active", "positive", "pos"}:
        return True
    if text in {"false", "no", "n", "inactive", "negative", "neg", ""}:
        return False
    try:
        return float(text) > 0
    except ValueError as exc:
        raise ValueError(f"Unrecognized activity label: {value!r}") from exc


def load_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hits", default="hits.csv")
    parser.add_argument("--train", default="train.csv")
    parser.add_argument("--output", default="pred_results/compound_filter_results.txt")
    parser.add_argument("--smiles-column", default="SMILES")
    parser.add_argument("--activity-column", default="ACTIVITY")
    parser.add_argument("--all-train-active", action="store_true")
    parser.add_argument("--similarity-threshold", type=float, default=0.5)
    parser.add_argument("--radius", type=int, default=2)
    parser.add_argument("--fp-size", type=int, default=2048)
    args = parser.parse_args()

    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import rdFingerprintGenerator
        from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

        if not 0 < args.similarity_threshold <= 1:
            raise ValueError("similarity threshold must be in (0, 1]")
        if args.radius < 1 or args.fp_size < 64:
            raise ValueError("radius must be >= 1 and fp-size must be >= 64")

        hit_rows, hit_fields = load_rows(Path(args.hits))
        train_rows, train_fields = load_rows(Path(args.train))
        if args.smiles_column not in hit_fields:
            raise ValueError(f"hits CSV is missing column {args.smiles_column!r}")
        if args.smiles_column not in train_fields:
            raise ValueError(f"train CSV is missing column {args.smiles_column!r}")
        if not args.all_train_active and args.activity_column not in train_fields:
            raise ValueError(f"train CSV is missing activity column {args.activity_column!r}")

        active_rows = train_rows if args.all_train_active else [r for r in train_rows if truthy_activity(r[args.activity_column])]
        generator = rdFingerprintGenerator.GetMorganGenerator(radius=args.radius, fpSize=args.fp_size)
        active_fps = []
        invalid_active = 0
        for row in active_rows:
            mol = Chem.MolFromSmiles((row.get(args.smiles_column) or "").strip())
            if mol is None:
                invalid_active += 1
            else:
                active_fps.append(generator.GetFingerprint(mol))
        if not active_fps:
            raise ValueError("no valid active reference molecules were found")

        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
        catalog = FilterCatalog(params)

        retained = []
        rejected = {"invalid_smiles": 0, "structural_alert": 0, "similarity": 0}
        for row in hit_rows:
            smiles = (row.get(args.smiles_column) or "").strip()
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                rejected["invalid_smiles"] += 1
                continue
            if catalog.HasMatch(mol):
                rejected["structural_alert"] += 1
                continue
            fp = generator.GetFingerprint(mol)
            max_similarity = max(DataStructs.BulkTanimotoSimilarity(fp, active_fps))
            if max_similarity >= args.similarity_threshold:
                rejected["similarity"] += 1
                continue
            retained.append(smiles)

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(x + "\n" for x in retained), encoding="utf-8")
        summary = {
            "ok": True, "hits": len(hit_rows), "active_references": len(active_fps),
            "invalid_active_references": invalid_active, "retained": len(retained),
            "rejected": rejected, "similarity_threshold": args.similarity_threshold,
            "radius": args.radius, "fp_size": args.fp_size, "output": str(output),
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
