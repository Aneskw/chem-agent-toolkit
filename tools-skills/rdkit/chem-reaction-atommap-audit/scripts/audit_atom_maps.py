#!/usr/bin/env python3
"""Audit atom-map identity constraints before reaction-template extraction."""
from __future__ import annotations

import argparse
import json
import sys


def audit(reaction: str) -> dict:
    from rdkit import Chem

    text = reaction.strip()
    errors = []
    if text.count(">>") != 1:
        return {"ok": False, "reaction": text, "errors": ["expected reactants>>products"]}
    left, right = text.split(">>")
    if not left or not right:
        return {"ok": False, "reaction": text, "errors": ["reactants and products must be nonempty"]}
    reactants, products = Chem.MolFromSmiles(left), Chem.MolFromSmiles(right)
    if reactants is None or products is None:
        return {"ok": False, "reaction": text, "errors": ["invalid reactant or product SMILES"]}

    def map_info(mol, side: str):
        values = [atom.GetAtomMapNum() for atom in mol.GetAtoms()]
        missing = sum(value == 0 for value in values)
        mapped = [value for value in values if value > 0]
        if missing:
            errors.append(f"{side}: {missing} atom(s) have no map number")
        if len(mapped) != len(set(mapped)):
            errors.append(f"{side}: duplicate atom-map number")
        return mapped

    reactant_maps = map_info(reactants, "reactants")
    product_maps = map_info(products, "products")
    unexpected = sorted(set(product_maps) - set(reactant_maps))
    if unexpected:
        errors.append("product maps absent from reactants: " + ",".join(map(str, unexpected)))
    return {
        "ok": not errors,
        "reaction": text,
        "reactant_atom_maps": sorted(set(reactant_maps)),
        "product_atom_maps": sorted(set(product_maps)),
        "reactant_only_maps": sorted(set(reactant_maps) - set(product_maps)),
        "errors": errors,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--reaction")
    group.add_argument("--input")
    p.add_argument("--output")
    args = p.parse_args()
    if args.reaction is not None:
        values = [args.reaction]
    else:
        with open(args.input, encoding="utf-8") as handle:
            values = handle.read().splitlines()
    rows = [audit(value) for value in values]
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(body)
    else:
        sys.stdout.write(body)
    return 0 if all(row["ok"] for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
