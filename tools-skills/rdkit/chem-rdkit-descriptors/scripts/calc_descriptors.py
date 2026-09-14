#!/usr/bin/env python3
import argparse
import json
import sys


def calculate(text):
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
    mol = Chem.MolFromSmiles(text.strip()) if text.strip() else None
    if mol is None:
        return {"ok": False, "input": text, "error": "Invalid or empty SMILES"}
    return {
        "ok": True,
        "input": text,
        "canonical_smiles": Chem.MolToSmiles(mol),
        "descriptors": {
            "molecular_weight": round(Descriptors.MolWt(mol), 6),
            "logp": round(Crippen.MolLogP(mol), 6),
            "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 6),
            "h_bond_donors": Lipinski.NumHDonors(mol),
            "h_bond_acceptors": Lipinski.NumHAcceptors(mol),
            "rotatable_bonds": Lipinski.NumRotatableBonds(mol),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--smiles")
    source.add_argument("--input")
    parser.add_argument("--output")
    args = parser.parse_args()
    values = [args.smiles] if args.smiles is not None else open(args.input, encoding="utf-8")
    records = [calculate(v.rstrip("\n")) for v in values]
    if args.input:
        values.close()
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    return 0 if all(r["ok"] for r in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
