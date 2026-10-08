---
name: widom-sorbent-screening
description: >-
  Gate porous sorbent rankings on valid and precise infinite-dilution sampling. Invoke for: comparing CO2 uptake proxies at low partial pressure; not for claiming full working capacity from Henry coefficients.
license: MIT
compatibility: Periodic framework structures and an interaction-energy calculator
allowed-tools: Read, Bash
---

# Widom Sorbent Screening

## Applicability

Use for low-pressure adsorption screening with Widom insertion. Do not apply an infinite-dilution ranking directly to high-pressure or cyclic process performance.

## Credibility

**low confidence (Highly flexible).** Based on a benchmark protocol; neither the insertion campaign nor downstream capture performance was verified here.

## Reference

[MOF DAC benchmark task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/mof-dac-screening/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/chemistry/mof-dac-screening/tests/test_outputs.py).

## Input & Output

Input: framework cells, probe geometry, temperature, force field or potential, sampling plan. Output: Henry coefficient, heat of adsorption, uncertainty, overlap fraction, and qualified/unqualified decision per framework.

## Procedure Guidance

Check the cell's minimum interplanar separation before insertion; an inadequate cell blocks a trustworthy ranking. Use identical randomized positions, orientations, overlap rules, energy references, and sampling counts across frameworks. Exclude physically invalid overlaps and pathological energies by a declared rule, then estimate uncertainty from repeated sampling or bootstrap. If relative Henry uncertainty or heat uncertainty exceeds the decision tolerance, sample more or mark the candidate inconclusive; do not promote the largest noisy point estimate. Keep heat sign convention explicit.

## Success Criteria

Each framework has a traceable sampling-quality verdict; the selected framework is the best among those meeting the predefined quality gates.

## Matters & Troubleshooting

Flexible frameworks, water, defects, and finite-loading effects are outside rigid infinite-dilution screening.
