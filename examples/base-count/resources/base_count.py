"""Release 1.0: count A, C, G, T in a nonempty uppercase DNA string."""
import argparse
import json
from pathlib import Path


def counts(sequence):
    if not sequence or any(base not in 'ACGT' for base in sequence):
        raise ValueError('expected a nonempty uppercase ACGT sequence')
    return {'length': len(sequence), **{base: sequence.count(base) for base in 'ACGT'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--sequence')
    mode.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.input:
            sequence = args.input.read_text(encoding='utf-8').removesuffix('\n')
        else:
            sequence = args.sequence
        text = json.dumps(counts(sequence), sort_keys=True)
        if args.output:
            args.output.write_text(text + '\n', encoding='utf-8')
        print(text)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
