"""Default RDKit RECAP leaves; provenance: ../references/source.md.

Validation and JSON serialization are wrapper behavior. Fragmentation delegates
unchanged to RDKit RecapDecompose and GetLeaves.
"""
import argparse
import json

from rdkit import Chem
from rdkit.Chem import Recap


class InvalidSmiles(ValueError):
    """Input rejected before decomposition."""


def terminal_leaves(smiles):
    """Return SMILES-keyed terminal nodes; an empty dictionary is successful."""
    if not isinstance(smiles, str) or not smiles.strip():
        raise InvalidSmiles("SMILES must be a nonempty string")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise InvalidSmiles("SMILES did not produce a nonempty RDKit molecule")
    root = Recap.RecapDecompose(mol)
    return root.GetLeaves()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("smiles", help="one nonempty SMILES string")
    args = parser.parse_args()
    try:
        leaves = terminal_leaves(args.smiles)
    except InvalidSmiles as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps({"fragments": sorted(leaves)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
