#!/usr/bin/env python3
"""CPU-only, pinned RDKit descriptors and bundled JSON screening rule; no external resources or runtime network.
Rules are caller-selected operational thresholds, not universal scientific validity criteria.
CCO: source descriptor weight 46.069 <= 50.0, selected true.
c1ccccc1O: source descriptor weight 94.113 > 50.0, selected false.
Invalid or empty SMILES must return ok false, original error and exit 2.
"""
import argparse
import json
from pathlib import Path
from calc_descriptors import calculate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smiles', required=True)
    args = parser.parse_args()
    rules = json.loads((Path(__file__).resolve().parent / "data" / "rules.json").read_text(encoding="utf-8"))
    result = calculate(args.smiles)
    if result['ok']:
        result['selected'] = result['descriptors']['molecular_weight'] <= rules['maximum_molecular_weight']
        result['policy_id'] = rules['policy_id']
        result['maximum_molecular_weight'] = rules['maximum_molecular_weight']
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
