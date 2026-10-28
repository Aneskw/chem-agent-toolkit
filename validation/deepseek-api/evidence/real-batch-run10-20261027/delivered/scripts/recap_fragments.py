"""Terminal RECAP fragments using RDKit's existing algorithm.

Source: rdkit/Chem/Recap.py at 237a1d9027c800784afed8788540f38a3aa595f8.
Parsing, JSON serialization and error labels are adapter behavior.
"""
import argparse
import json

from rdkit import Chem
from rdkit.Chem import Recap


def terminal_fragments(mol):
    """Return sorted unique leaf SMILES for a valid, nonempty RDKit molecule.

    Caller-provided molecules must already be sanitized. No normalization,
    reaction customization or shared decomposition cache is applied.
    """
    if not isinstance(mol, Chem.Mol) or mol.GetNumAtoms() == 0:
        raise ValueError("expected a nonempty RDKit molecule")
    root = Recap.RecapDecompose(mol)
    return sorted(root.GetLeaves().keys())


def main():
    parser = argparse.ArgumentParser(description="Extract terminal RECAP fragment SMILES")
    parser.add_argument("smiles", help="one nonempty SMILES string")
    args = parser.parse_args()
    text = args.smiles.strip()
    if not text:
        print(json.dumps({"error": "empty_input"}))
        return 2
    try:
        mol = Chem.MolFromSmiles(text)
    except Exception:
        print(json.dumps({"error": "invalid_smiles"}))
        return 2
    if mol is None:
        print(json.dumps({"error": "invalid_smiles"}))
        return 2
    if mol.GetNumAtoms() == 0:
        print(json.dumps({"error": "empty_molecule"}))
        return 2
    print(json.dumps({"fragments": terminal_fragments(mol)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
