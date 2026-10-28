#!/usr/bin/env python3
'''Return RDKit RECAP terminal leaf fragments for a SMILES string.

This is a thin command-line wrapper around rdkit.Chem.Recap.RecapDecompose and
RecapHierarchyNode.GetLeaves. Input is a single SMILES string. Output is a JSON
object::

    {"leaves": ["*C1CC1", "*c1ccc(OC)cn1", "*c1ccccc1*"]}

A valid empty decomposition is::

    {"leaves": []}

Exit status:
    0 after successful decomposition (including empty leaves)
    2 on invalid input or an RDKit error
'''

import argparse
import json
import sys
from typing import List, Optional

from rdkit import Chem
from rdkit.Chem import Recap


def terminal_leaves(
    smiles: str,
    min_fragment_size: int = 0,
    only_use_reactions: Optional[List[int]] = None,
) -> List[str]:
    '''Return sorted terminal leaf SMILES for *smiles*.'''
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError('invalid SMILES: {!r}'.format(smiles))

    if only_use_reactions is not None:
        only_use_reactions = set(only_use_reactions)

    root = Recap.RecapDecompose(
        mol,
        minFragmentSize=min_fragment_size,
        onlyUseReactions=only_use_reactions,
    )
    return sorted(root.GetLeaves().keys())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Return RDKit RECAP terminal leaf fragments for a SMILES string.'
    )
    parser.add_argument('smiles', help='input SMILES string')
    parser.add_argument(
        '--min-fragment-size',
        type=int,
        default=0,
        help='minimum explicit atom count after removing * dummy atoms (default: 0)',
    )
    parser.add_argument(
        '--only-use-reactions',
        default='',
        help='comma-separated reaction-definition indices to use (default: all)',
    )
    return parser


def main(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    only_use_reactions = None
    if args.only_use_reactions.strip():
        try:
            only_use_reactions = [
                int(x.strip()) for x in args.only_use_reactions.split(',') if x.strip()
            ]
        except ValueError as exc:
            print(
                json.dumps(
                    {'error': 'invalid --only-use-reactions value: {!s}'.format(exc)},
                    sort_keys=True,
                )
            )
            return 2

    try:
        leaves = terminal_leaves(
            args.smiles,
            min_fragment_size=args.min_fragment_size,
            only_use_reactions=only_use_reactions,
        )
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, sort_keys=True))
        return 2

    print(json.dumps({'leaves': leaves}, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
