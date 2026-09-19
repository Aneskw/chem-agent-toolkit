#!/usr/bin/env python3
"""Evaluate top-k precursor predictions with exact and supplied round-trip checks."""
from __future__ import annotations

import argparse
import json
import sys


def canonical_components(text: str, *, stereo: bool) -> tuple[str, ...]:
    from rdkit import Chem

    items = []
    for part in text.split("."):
        mol = Chem.MolFromSmiles(part.strip()) if part.strip() else None
        if mol is None:
            raise ValueError(f"invalid SMILES component: {part!r}")
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(0)
        items.append(Chem.MolToSmiles(mol, canonical=True, isomericSmiles=stereo))
    return tuple(sorted(items))


def has_specified_stereo(text: str) -> bool:
    from rdkit import Chem

    mol = Chem.MolFromSmiles(text)
    if mol is None:
        raise ValueError("invalid ground-truth SMILES")
    return any(atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for atom in mol.GetAtoms()) or any(
        bond.GetStereo() != Chem.BondStereo.STEREONONE for bond in mol.GetBonds())


def evaluate_case(row: dict, top_k: int) -> dict:
    target = row["target_product"]
    gold = row["ground_truth_reactants"]
    stereo = has_specified_stereo(gold)
    gold_key = canonical_components(gold, stereo=stereo)
    target_key = canonical_components(target, stereo=has_specified_stereo(target))
    details = []
    for rank, item in enumerate(row["predictions"][:top_k], 1):
        precursor = item["reactants"]
        try:
            exact = canonical_components(precursor, stereo=stereo) == gold_key
            error = None
        except ValueError as exc:
            exact = False
            error = str(exc)
        forward = item.get("forward_product")
        if forward is None:
            roundtrip = None
        else:
            try:
                forward_correct = canonical_components(forward, stereo=has_specified_stereo(target)) == target_key
                roundtrip = exact or forward_correct
            except ValueError as exc:
                roundtrip = False
                error = str(exc)
        details.append({"rank": rank, "reactants": precursor, "exact_match": exact,
                        "roundtrip_correct": roundtrip, "error": error})
    assessed = [item for item in details if item["roundtrip_correct"] is not None]
    return {"ok": True, "id": row.get("id"), "top_k": top_k,
            "exact_top1": bool(details and details[0]["exact_match"]),
            "exact_topk": any(item["exact_match"] for item in details),
            "roundtrip_top1": details[0]["roundtrip_correct"] if details else None,
            "roundtrip_topk": any(item["roundtrip_correct"] for item in assessed) if len(assessed) == len(details) and details else None,
            "roundtrip_assessed": len(assessed), "predictions": details,
            "stereo_policy": "compare stereochemistry only when ground truth specifies it"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL rows with target_product, ground_truth_reactants, predictions")
    parser.add_argument("--output")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("top-k must be positive")
    with open(args.input, encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    results = []
    for index, record in enumerate(records, 1):
        try:
            results.append(evaluate_case(record, args.top_k))
        except (KeyError, TypeError, ValueError) as exc:
            results.append({"ok": False, "id": record.get("id", index), "error": str(exc)})
    body = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in results)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(body)
    else:
        sys.stdout.write(body)
    return 0 if all(item["ok"] for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
