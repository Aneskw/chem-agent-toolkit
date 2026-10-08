---
name: xrd-mixture-phase-quantification
description: >-
  Separate phase identification from quantitative mixture fitting. Invoke for: powder-XRD analysis of multiphase samples; not for treating peak-height ratios as weight fractions.
license: MIT
compatibility: Powder pattern with radiation metadata and candidate crystal structures
allowed-tools: Read, Bash
---

# XRD Mixture Phase Quantification

## Applicability

Use when a measured pattern may contain multiple crystalline phases. Account for amorphous material or preferred orientation before calling fractions absolute.

## Credibility

**low confidence (Highly flexible).** Motivated by a benchmark task; neither phase identification nor quantitative refinement was executed here.

## Reference

[XRD mixture task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/xrd-mixture-phase-fit/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/xrd-mixture-phase-fit/tests/test_outputs.py).

## Input & Output

Input: 2-theta/intensity data, wavelength, background, candidate structures. Output: identified phases, space groups, refined scale factors, weight fractions and fit residuals.

## Procedure Guidance

Confirm wavelength and angular axis before comparing simulated reflections. Shortlist phases using several characteristic peaks, not one coincident line; fit the full pattern jointly so overlapping reflections are assigned consistently. Convert refined scale factors to mass fractions with an appropriate quantitative-phase model, then normalize over explicitly modeled crystalline phases. If residual peaks remain systematic or preferred orientation dominates, expand the phase set or qualify the reported fractions rather than forcing them to sum to one as a complete sample composition.

## Success Criteria

The selected phases explain the major reflections, the modeled fractions are normalized, and residuals support the phase count.

## Matters & Troubleshooting

Peak broadening, texture, fluorescence, amorphous content, and near-isostructural phases limit quantitative reliability.
