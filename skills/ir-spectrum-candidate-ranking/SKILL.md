---
name: ir-spectrum-candidate-ranking
description: >-
  Rank candidate compounds against an experimental IR spectrum. Invoke for: comparing candidate reference spectra with a measured trace; not for assigning structure from one isolated peak.
license: MIT
compatibility: IR spectra with documented wavenumber axis and candidate reference spectra
allowed-tools: Read, Bash
---

# IR Spectrum Candidate Ranking

## Applicability

Use when a query spectrum and candidate spectra are available. A SMILES list alone is insufficient unless comparable predicted or measured references can be obtained.

## Credibility

**low confidence (Highly flexible).** Informed by a benchmark task; no independent spectral validation or agent-effect study is claimed.

## Reference

[IR matching task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/ir-spectrum-match/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/ir-spectrum-match/tests/test_outputs.py).

## Input & Output

Input: query axis/intensity, candidate IDs and comparable spectra, instrument or simulation provenance. Output: complete ranked candidate IDs and diagnostic matched and unmatched bands.

## Procedure Guidance

Verify axis direction, units, absorbance versus transmittance, and whether spectra are measured or computed. Align and normalize consistently before comparing; allow bounded peak shifts when reference and query conditions differ. Weight diagnostic regions and penalize strong unexplained bands, rather than selecting on one favorable peak. If references are simulated, avoid pretending their intensities or frequencies are exact experimental matches. Rank every candidate once and mark close scores as ambiguous.

## Success Criteria

All supplied candidate IDs appear exactly once in a reproducible ranking, with the top assignment supported by multiple spectral regions.

## Matters & Troubleshooting

Mixtures, solvent bands, baseline errors, phase, and hydrogen bonding can invalidate a neat one-compound match.
