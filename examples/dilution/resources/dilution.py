"""Version 1.0: ideal dilution calculator; concentrations must use the same unit."""
import argparse
import json
import math
from pathlib import Path


def calculate(stock, target, volume):
    if not all(math.isfinite(x) and x > 0 for x in (stock, target, volume)):
        raise ValueError('values must be finite and positive')
    if target > stock:
        raise ValueError('target exceeds stock')
    aliquot = volume * target / stock
    return {'stock_volume_ml': aliquot, 'diluent_volume_ml': volume - aliquot}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=float)
    parser.add_argument('--target', type=float)
    parser.add_argument('--volume', type=float)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.input:
            if any(x is not None for x in (args.stock, args.target, args.volume)):
                raise ValueError('input and scalar arguments are mutually exclusive')
            rows = json.loads(args.input.read_text(encoding='utf-8'))
            if not isinstance(rows, list) or not rows:
                raise ValueError('input must be a nonempty JSON array')
            result = [calculate(float(r['stock']), float(r['target']), float(r['volume'])) for r in rows]
        else:
            result = calculate(args.stock, args.target, args.volume)
        text = json.dumps(result, allow_nan=False)
        if args.output:
            args.output.write_text(text + '\n', encoding='utf-8')
        print(text)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
