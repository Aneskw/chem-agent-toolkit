---
name: widom-sorbent-screening
description: "Gate porous sorbent rankings on valid and precise infinite-dilution sampling. Invoke for: comparing CO2 uptake proxies at low partial pressure; not for claiming full working capacity from Henry coefficients."
license: MIT
---

# Widom Sorbent Screening

## Applicability

Use for low-pressure adsorption screening with Widom insertion. Do not apply an infinite-dilution ranking directly to high-pressure or cyclic process performance.

## Input & Output

Input: framework cells, probe geometry, temperature, force field or potential, sampling plan. Output: Henry coefficient, heat of adsorption, uncertainty, overlap fraction, and qualified/unqualified decision per framework.

## Procedure Guidance

Check the cell's minimum interplanar separation before insertion; an inadequate cell blocks a trustworthy ranking. Use identical randomized positions, orientations, overlap rules, energy references, and sampling counts across frameworks. Exclude physically invalid overlaps and pathological energies by a declared rule, then estimate uncertainty from repeated sampling or bootstrap. If relative Henry uncertainty or heat uncertainty exceeds the decision tolerance, sample more or mark the candidate inconclusive; do not promote the largest noisy point estimate. Keep heat sign convention explicit.

## Success Criteria

Each framework has a traceable sampling-quality verdict; the selected framework is the best among those meeting the predefined quality gates.

## Matters & Troubleshooting

Flexible frameworks, water, defects, and finite-loading effects are outside rigid infinite-dilution screening.

## Required sampler and ranking record

Use an already configured Widom sampler (or supplied sampler results) with documented Henry/heat estimators and output units. A calculator returning single interaction energies alone is not a complete insertion workflow. Required output per framework:

```text
framework_id, temperature_K, sampler_version, repeats,
Henry_value, Henry_unit, Henry_uncertainty,
heat_value, heat_unit, heat_sign_convention, heat_uncertainty,
overlap_fraction, cell_valid, quality_verdict, reason
```

Apply task-supplied precision tolerances; if none were supplied, report uncertainty and abstain from a threshold-based pass/fail claim. Overlap rejection must remain consistent with the sampler's estimator normalization: zero-weight inaccessible insertions must not silently disappear from the total trial count. Compare identical physical settings and comparable precision; random-number sequences need not literally coincide between differently shaped cells. This guide does not implement a force field, insertion engine, or a finite-pressure isotherm.
