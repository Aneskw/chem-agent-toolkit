---
name: parent-analog-stereo-audit
description: "Compare analogs after salt removal while preserving stereo distinctions. Invoke for: nearest-analog and duplicate-topology audits; not for assuming fingerprint similarity implies equal biological activity."
license: MIT
---

# Parent Analog and Stereo Audit

## Applicability

Use when a vendor library mixes salts, solvates, and parent structures. Distinguish structural-neighbor ranking from stereochemical equivalence.

## Input & Output

Input: query and library IDs/structures, parent policy, fingerprint settings. Output: salt-form flags, similarity ranking, and pairs sharing achiral topology but differing in assigned stereo.

## Procedure Guidance

Standardize query and library with the same cleanup, fragment-parent, and charge policy before computing fingerprints. Use one fixed fingerprint radius, bit count, chirality setting, and deterministic tie rule. For suspected duplicates, compare canonical identifiers twice: with and without stereochemistry. If achiral identifiers match but stereo-aware identifiers differ, report a stereochemical pair instead of collapsing records. Flag unspecified stereo separately; it is not evidence for a specific enantiomer.

## Success Criteria

All comparisons use standardized parents, and nearest-neighbor and stereo conclusions can be reproduced from declared settings.

## Matters & Troubleshooting

Parent selection can discard an active counterion or change a biologically relevant ionization state; retain provenance.
