---
name: chem-reaction-atommap-audit
description: >-
  Audit atom-map identity and syntax in mapped reaction SMILES. Invoke for: checking a reactants>>products input before extracting local reaction templates; do not use it to prove reaction feasibility or atom-mapping chemical correctness.
license: MIT
compatibility: Python 3.10+ with RDKit; no model weights or network required
allowed-tools: Bash, Read, Write
---

# Reaction atom-map audit

Check a mapped reaction's structural preconditions for template extraction. Use
this for `reactants>>products` strings and batch files of such strings. Do not
use it as a reaction predictor, an atom mapper, or a chemistry-validity judge.

## Credibility

**High confidence (Enforce strictly)** for the narrow structural checks in
this package: RDKit parsing, nonempty sides, unique positive map numbers on
each side, and product map numbers present in reactants. Valid, unmapped,
duplicate-map, and extra-product-map cases pass the packaged tests. This does
not establish whether mapped atoms correspond to the chemically correct atoms.

## Reference

- Wang et al., *JACS Au* 2021, DOI `10.1021/jacsau.1c00246`: LocalRetro
  derives local templates from atom-mapped reactant/product differences.
- Pinned LocalRetro repository: `kaist-amsg/LocalRetro` commit
  `eba83e72efabeb854fec86c865e8743c295a8a1e`, especially
  `LocalTemplate/template_extractor.py`. The pinned source and SHA-256 values
  are in `creation_pipeline/source_locks/2GFR874J.json` at repository root.
- Read `references/science.md` when deciding whether a map audit is sufficient
  for a downstream template workflow.

## Input & Output

Input: one mapped reaction through `--reaction`, or one reaction per line in
`--input`. Output: JSONL with `ok`, original `reaction`, sorted reactant and
product atom-map lists, `reactant_only_maps`, and `errors`. Exit code 2 means at
least one input failed. Reactant-only maps are expected for leaving groups and
are not treated as an error.

## Procedure Guidance

```bash
python scripts/audit_atom_maps.py \
  --reaction '[CH3:1][CH2:2][OH:3]>>[CH3:1][CH:2]=[O:3]'
python scripts/audit_atom_maps.py --input mapped_reactions.txt --output audit.jsonl
```

Require `ok: true` before passing the reaction to a template extractor. Keep
the original input and error record for rejected rows rather than silently
dropping them.

## Matters & Troubleshooting

- No mapping is generated here; obtain a mapped source separately.
- `reactants>reagents>products` is a different notation and is rejected. Split
  or normalize it explicitly before this check.
- An `ok: true` result says only that map identifiers are structurally usable.
  Stereochemistry, conservation and experimental plausibility need separate
  checks.
