"""Terminal RECAP SMILES using RDKit's existing implementation.

Source: rdkit/Chem/Recap.py at 237a1d9027c800784afed8788540f38a3aa595f8.
Parsing checks and JSON serialization are wrapper glue. See ../LICENSES.txt.
"""
import argparse
import json

from rdkit import Chem
from rdkit.Chem import Recap


class InputError(ValueError):
    """Invalid wrapper input, distinct from decomposition failures."""


def terminal_fragments(smiles):
    """Return sorted unique terminal SMILES; raise ValueError for invalid input."""
    if not isinstance(smiles, str) or not smiles.strip():
        raise InputError("SMILES must be a nonempty string")
    try:
        mol = Chem.MolFromSmiles(smiles)
    except Exception as exc:
        raise InputError("SMILES could not be parsed") from exc
    if mol is None:
        raise InputError("SMILES could not be parsed")
    if mol.GetNumAtoms() == 0:
        raise InputError("SMILES must contain at least one atom")
    root = Recap.RecapDecompose(mol)
    return sorted(root.GetLeaves().keys())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("smiles", help="One quoted SMILES string")
    args = parser.parse_args()
    # Restrict input-error handling to validation. Decomposition errors propagate.
    if not args.smiles.strip():
        parser.error("SMILES must be a nonempty string")
    try:
        result = terminal_fragments(args.smiles)
    except InputError as exc:
        parser.error(str(exc))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())