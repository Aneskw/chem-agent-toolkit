"""Terminal fragments using RDKit RecapDecompose/GetLeaves, with JSON I/O.

API/source reference: rdkit/Chem/Recap.py at
237a1d9027c800784afed8788540f38a3aa595f8 (see SKILL.md and references/LICENSE.txt).
Only parsing checks and output/error formatting are added here.
"""
import argparse
import json


def emit_error(kind, message, code):
    print(json.dumps({"error": kind, "message": message}))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("smiles", help="One nonempty molecular SMILES string")
    args = parser.parse_args()
    if not args.smiles.strip():
        return emit_error("invalid_input", "SMILES must not be blank", 2)
    try:
        from rdkit import Chem
        from rdkit.Chem import Recap
    except ImportError as exc:
        return emit_error("runtime_error", str(exc), 1)
    try:
        mol = Chem.MolFromSmiles(args.smiles)
    except Exception as exc:
        return emit_error("invalid_input", str(exc), 2)
    if mol is None:
        return emit_error("invalid_input", "SMILES could not be parsed", 2)
    if mol.GetNumAtoms() == 0:
        return emit_error("invalid_input", "Molecule must contain atoms", 2)
    try:
        root = Recap.RecapDecompose(mol)
        fragments = sorted(root.GetLeaves().keys())
    except Exception as exc:
        return emit_error("runtime_error", str(exc), 1)
    print(json.dumps({"fragments": fragments, "count": len(fragments)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())