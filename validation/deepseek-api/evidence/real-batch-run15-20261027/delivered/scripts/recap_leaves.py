#!/usr/bin/env python3
'''Return terminal RECAP fragment SMILES for a valid sanitized RDKit Mol.

Grounded on RDKit rdkit/Chem/Recap.py at commit
237a1d9027c800784afed8788540f38a3aa595f8 (BSD 3-Clause). The decomposition,
hierarchy, filtering, and empty-result semantics are upstream; this wrapper adds
SMILES input validation and JSON output only.
'''
import argparse
import json
import sys

from rdkit import Chem
from rdkit.Chem import Recap


def terminal_fragment_smiles(mol, allNodes=None, minFragmentSize=0, onlyUseReactions=None):
    '''Return a dict mapping each terminal leaf SMILES to itself.

    mol must be a valid sanitized RDKit Mol. RecapDecompose immediately calls
    Chem.MolToSmiles(mol, 1), so None or invalid Mol inputs fail inside that
    call.
    '''
    hierarchy = Recap.RecapDecompose(
        mol,
        allNodes=allNodes,
        minFragmentSize=minFragmentSize,
        onlyUseReactions=onlyUseReactions,
    )
    leaves = hierarchy.GetLeaves()
    return {smi: Chem.MolToSmiles(node.mol, 1) for smi, node in leaves.items()}


def _parse_reaction_indices(value):
    if value is None:
        return None
    if value.strip() == '':
        raise argparse.ArgumentTypeError('only-use-reactions cannot be empty')
    result = []
    for part in value.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            raise argparse.ArgumentTypeError(
                'invalid reaction index {!r}'.format(part)
            )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('smiles', help='input SMILES')
    parser.add_argument(
        '--min-fragment-size',
        type=int,
        default=0,
        help='discard fragments with fewer than this many non-dummy atoms',
    )
    parser.add_argument(
        '--only-use-reactions',
        type=_parse_reaction_indices,
        default=None,
        help='comma-separated zero-based reaction indices (see SKILL.md)',
    )
    args = parser.parse_args(argv)

    mol = Chem.MolFromSmiles(args.smiles)
    if mol is None:
        print(
            'error: could not parse SMILES: {!r}'.format(args.smiles),
            file=sys.stderr,
        )
        return 1

    try:
        leaves = terminal_fragment_smiles(
            mol,
            minFragmentSize=args.min_fragment_size,
            onlyUseReactions=args.only_use_reactions,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(
            'error: RECAP decomposition failed: {}'.format(exc),
            file=sys.stderr,
        )
        return 1

    output = {'input_smiles': args.smiles, 'leaves': leaves}
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
