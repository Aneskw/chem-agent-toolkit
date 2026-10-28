#!/usr/bin/env python3
"""Command-line wrapper for RDKit RECAP terminal leaf fragments.

This script is source-grounded in rdkit/Chem/Recap.py from the RDKit snapshot:
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py

It decomposes each input SMILES with RecapDecompose and prints only
GetLeaves() results. RDKit is BSD-3-Clause; see references/LICENSE.txt.
"""

import argparse
import json
import sys

from rdkit import Chem
from rdkit.Chem import Recap


def parse_reaction_indices(value):
    if value is None:
        return None
    if value.strip() == "":
        return []
    try:
        return [int(part) for part in value.split(",") if part.strip() != ""]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "only-use-reactions must be a comma-separated list of integers"
        ) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print RECAP terminal leaf fragments for one or more SMILES."
    )
    parser.add_argument("smiles", nargs="+", help="SMILES string(s) to decompose")
    parser.add_argument(
        "--min-fragment-size",
        type=int,
        default=0,
        help="Minimum non-dummy atom count for fragments; defaults to 0.",
    )
    parser.add_argument(
        "--only-use-reactions",
        default=None,
        help="Comma-separated 0-based reactionDefs indices to use (default: all).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON object keyed by canonical input SMILES.",
    )
    args = parser.parse_args(argv)
    only_use = parse_reaction_indices(args.only_use_reactions)

    results = {}
    for smi in args.smiles:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            raise SystemExit("invalid SMILES: {!r}".format(smi))
        canonical = Chem.MolToSmiles(mol, 1)
        root = Recap.RecapDecompose(
            mol,
            minFragmentSize=args.min_fragment_size,
            onlyUseReactions=only_use,
        )
        leaves = root.GetLeaves()
        results[canonical] = sorted(leaves.keys())

    if args.json:
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for canonical, leaf_smiles in results.items():
            print("{}\t{}\t{}".format(canonical, len(leaf_smiles), ",".join(leaf_smiles)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
