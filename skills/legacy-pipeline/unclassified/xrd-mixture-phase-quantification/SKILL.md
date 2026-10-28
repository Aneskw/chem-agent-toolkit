---
name: xrd-mixture-phase-quantification
description: "Separate phase identification from quantitative mixture fitting. Invoke for: powder-XRD analysis of multiphase samples; not for treating peak-height ratios as weight fractions."
license: MIT
---

# XRD Mixture Phase Quantification

## Applicability

Use when a measured pattern may contain multiple crystalline phases. Account for amorphous material or preferred orientation before calling fractions absolute.

## Input & Output

Input: 2-theta/intensity data, wavelength, background, candidate structures. Output: identified phases, space groups, refined scale factors, weight fractions and fit residuals.

## Procedure Guidance

Confirm wavelength and angular axis before comparing simulated reflections. Shortlist phases using several characteristic peaks, not one coincident line; fit the full pattern jointly so overlapping reflections are assigned consistently. Convert refined scale factors to mass fractions with an appropriate quantitative-phase model, then normalize over explicitly modeled crystalline phases. If residual peaks remain systematic or preferred orientation dominates, expand the phase set or qualify the reported fractions rather than forcing them to sum to one as a complete sample composition.

## Success Criteria

The selected phases explain the major reflections, the modeled fractions are normalized, and residuals support the phase count.

## Matters & Troubleshooting

Peak broadening, texture, fluorescence, amorphous content, and near-isostructural phases limit quantitative reliability.

## Quantitative-phase requirements

Use a configured whole-pattern/Rietveld refinement engine or supplied refinement results. This guide does not implement an XRD simulator/refiner. Retain its background, radiation, phase structures, scale-factor convention and residual diagnostics.

For the usual Hill–Howard Rietveld scale convention, compute crystalline weight fraction `w_i = S_i*(Z*M*V)_i / sum_j(S_j*(Z*M*V)_j)`: `S` is the refined scale, `Z` formula units per cell, `M` formula mass, and `V` cell volume. Use consistent units and the engine's own conversion when its scale convention differs. A raw peak-height or arbitrary fitted-profile coefficient is not this `S`.

Return phase ID/structure source, refined scale, weight fraction, uncertainty and unexplained peaks. Without an internal/external standard or another validated amorphous-content method, these fractions normalize over modeled crystalline phases, not necessarily the whole sample.

Source: [IUCr quantitative phase analysis](https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o9v0001/).
