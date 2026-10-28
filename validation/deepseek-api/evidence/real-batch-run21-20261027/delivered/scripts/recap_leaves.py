#!/usr/bin/env python
'''Print terminal or full RECAP fragment SMILES for an input SMILES.

Thin source-grounded wrapper around rdkit.Chem.Recap.RecapDecompose.
'''
import argparse
import sys

from rdkit import Chem
from rdkit.Chem import Recap


def parse_reaction_indices(text):
    if text is None or text.strip() == '':
        return None
    return [int(x) for x in text.split(',') if x.strip() != '']


def main(argv=None):
    parser = argparse.ArgumentParser(description='Decompose an RDKit molecule into RECAP fragments')
    parser.add_argument('--smiles', required=True, help='Input SMILES')
    parser.add_argument('--min-fragment-size', type=int, default=0,
                        help='Minimum non-dummy atoms per fragment (default 0)')
    parser.add_argument('--only-use-reactions', type=parse_reaction_indices,
                        help='Comma-separated zero-based reaction indices to use')
    parser.add_argument('--mode', choices=['leaves', 'all'], default='leaves',
                        help='leaves = terminal GetLeaves(), all = full GetAllChildren()')
    args = parser.parse_args(argv)

    mol = Chem.MolFromSmiles(args.smiles)
    if mol is None:
        print('Invalid SMILES')
        return 1

    root = Recap.RecapDecompose(
        mol,
        minFragmentSize=args.min_fragment_size,
        onlyUseReactions=args.only_use_reactions,
    )
    if args.mode == 'leaves':
        result = root.GetLeaves()
    else:
        result = root.GetAllChildren()

    if not result:
        print('no terminal leaves' if args.mode == 'leaves' else 'no fragments')
        return 0

    for smi in sorted(result.keys()):
        print(smi)
    return 0


if __name__ == '__main__':
    sys.exit(main())
