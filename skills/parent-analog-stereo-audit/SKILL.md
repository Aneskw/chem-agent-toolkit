---
name: parent-analog-stereo-audit
description: >-
  Compare analogs after salt removal while preserving stereo distinctions. Invoke for: nearest-analog and duplicate-topology audits; not for assuming fingerprint similarity implies equal biological activity.
license: MIT
compatibility: RDKit standardization and chirality-aware fingerprints
allowed-tools: Read, Bash
---

# Parent Analog and Stereo Audit

## Applicability

Use when a vendor library mixes salts, solvates, and parent structures. Distinguish structural-neighbor ranking from stereochemical equivalence.

## Credibility

**low confidence (Highly flexible).** Informed by a benchmark task; no downstream assay prediction was tested.

## Reference

[Analog diversity task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/ecfp-analog-diversity/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/ecfp-analog-diversity/tests/test_outputs.py).

## Input & Output

Input: query and library IDs/structures, parent policy, fingerprint settings. Output: salt-form flags, similarity ranking, and pairs sharing achiral topology but differing in assigned stereo.

## Procedure Guidance

Standardize query and library with the same cleanup, fragment-parent, and charge policy before computing fingerprints. Use one fixed fingerprint radius, bit count, chirality setting, and deterministic tie rule. For suspected duplicates, compare canonical identifiers twice: with and without stereochemistry. If achiral identifiers match but stereo-aware identifiers differ, report a stereochemical pair instead of collapsing records. Flag unspecified stereo separately; it is not evidence for a specific enantiomer.

## Success Criteria

All comparisons use standardized parents, and nearest-neighbor and stereo conclusions can be reproduced from declared settings.

## Matters & Troubleshooting

Parent selection can discard an active counterion or change a biologically relevant ionization state; retain provenance.
