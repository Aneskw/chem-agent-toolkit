"""Terminal RECAP fragments; see ../references/sources.md for upstream attribution.

Invocation glue only: RDKit supplies parsing and the fragmentation algorithm.
"""
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Return unique terminal RECAP fragment SMILES.")
    parser.add_argument("--smiles", required=True, help="One nonempty molecular SMILES")
    args = parser.parse_args()
    smiles = args.smiles.strip()
    if not smiles:
        print(json.dumps({"error": "invalid_input", "message": "SMILES must be nonempty."}))
        return 2

    try:
        from rdkit import Chem
        from rdkit.Chem import Recap
    except ImportError as exc:
        print(json.dumps({"error": "runtime_error", "message": str(exc)}))
        return 1

    try:
        mol = Chem.MolFromSmiles(smiles)
    except Exception:
        mol = None
    if mol is None or mol.GetNumAtoms() == 0:
        print(json.dumps({"error": "invalid_input", "message": "SMILES did not produce a nonempty RDKit molecule."}))
        return 2

    try:
        root = Recap.RecapDecompose(mol)
        fragments = sorted(root.GetLeaves().keys())
    except Exception as exc:
        print(json.dumps({"error": "runtime_error", "message": str(exc)}))
        return 1
    print(json.dumps({"fragments": fragments}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
