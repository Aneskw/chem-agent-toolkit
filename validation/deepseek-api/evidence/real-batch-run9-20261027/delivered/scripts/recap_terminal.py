"""Default RDKit RECAP terminal leaves; see ../references/source.md.

The CLI is mechanical input/output glue. The fragmentation algorithm is RDKit's.
"""
import argparse
import json
import sys


class InputError(ValueError):
    """An adapter input boundary failure."""


def terminal_leaves(smiles):
    """Return SMILES -> RecapHierarchyNode; access each node's .mol as needed."""
    from rdkit import Chem
    from rdkit.Chem import Recap

    if not isinstance(smiles, str) or not smiles.strip():
        raise InputError("SMILES must be a nonempty string")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise InputError("SMILES must parse to a nonempty RDKit molecule")
    root = Recap.RecapDecompose(mol)
    return root.GetLeaves()


def main():
    parser = argparse.ArgumentParser(description="Unique terminal RDKit RECAP fragments")
    parser.add_argument("--smiles", required=True, help="One input SMILES string")
    args = parser.parse_args()
    try:
        from rdkit import rdBase
        from rdkit import Chem
        from rdkit.Chem import Recap
    except ImportError as exc:
        print(json.dumps({"error": "dependency_unavailable", "message": str(exc)}))
        return 1
    try:
        leaves = terminal_leaves(args.smiles)
    except InputError as exc:
        print(json.dumps({"error": "invalid_input", "message": str(exc)}))
        return 2
    except Exception as exc:
        print(json.dumps({"error": "decomposition_failed", "message": str(exc)}))
        return 1
    print(json.dumps({"fragments": sorted(leaves), "rdkit_version": rdBase.rdkitVersion}))
    return 0


if __name__ == "__main__":
    sys.exit(main())