---
name: nmr-kinetics-deconvolution
description: "Separate spectral mixture estimation from kinetic-model fitting. Invoke for: extracting reaction time courses from overlapping NMR spectra; not for fitting a rate law to unverified peak areas."
license: MIT
---

# NMR Kinetics Deconvolution

## Applicability

Use when reactant and product signals overlap or individual peaks are unreliable. The species set and acquisition conditions must be sufficiently known to make spectral unmixing identifiable.

## Input & Output

Input: chemical-shift axis or buckets, spectra over time, reference spectra, acquisition frequency, and candidate kinetic models. Output: inferred fractions with residuals, fitted parameters with time units, and model diagnostics.

## Procedure Guidance

Match simulated or measured references to the acquisition field and broaden/resample them onto the observed bins. Fit nonnegative species contributions per time point before fitting kinetics; normalize fractions only after checking unexplained signal. For a reversible first-order approach, fit product fraction as f_eq + (f_0 - f_eq) exp(-k_obs t). If residuals or fraction trajectories contradict that model, report model failure rather than forcing a half-time. Propagate spectral uncertainty into rate uncertainty when feasible.

## Success Criteria

Reference-based fractions are plausible, spectral residuals are inspected, and kinetic parameters reproduce the time course with explicit units.

## Matters & Troubleshooting

Relaxation, changing line widths, exchange, impurities, and poor reference spectra may invalidate intensity-to-mole-fraction conversion.
