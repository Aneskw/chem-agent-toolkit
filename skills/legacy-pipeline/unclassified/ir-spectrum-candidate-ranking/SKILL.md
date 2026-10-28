---
name: ir-spectrum-candidate-ranking
description: "Rank candidate compounds against an experimental IR spectrum. Invoke for: comparing candidate reference spectra with a measured trace; not for assigning structure from one isolated peak."
license: MIT
---

# IR Spectrum Candidate Ranking

## Applicability

Use when a query spectrum and candidate spectra are available. A SMILES list alone is insufficient unless comparable predicted or measured references can be obtained.

## Input & Output

Input: query axis/intensity, candidate IDs and comparable spectra, instrument or simulation provenance. Output: complete ranked candidate IDs and diagnostic matched and unmatched bands.

## Procedure Guidance

Verify axis direction, units, absorbance versus transmittance, and whether spectra are measured or computed. Align and normalize consistently before comparing; allow bounded peak shifts when reference and query conditions differ. Weight diagnostic regions and penalize strong unexplained bands, rather than selecting on one favorable peak. If references are simulated, avoid pretending their intensities or frequencies are exact experimental matches. Rank every candidate once and mark close scores as ambiguous.

## Success Criteria

All supplied candidate IDs appear exactly once in a reproducible ranking, with the top assignment supported by multiple spectral regions.

## Matters & Troubleshooting

Mixtures, solvent bands, baseline errors, phase, and hydrogen bonding can invalidate a neat one-compound match.

## Comparison contract

Supply each spectrum as paired wavenumber (`cm^-1`) and intensity arrays plus its intensity type. Convert percent transmittance to fractional transmittance before `A = -log10(T)`; zero/nonpositive T is unusable for that conversion. Restrict all comparisons to a shared measured range and resolution; do not extrapolate absent bands into evidence.

Choose a declared numerical similarity metric with fixed preprocessing/region weights, or explicitly return a qualitative evidence ranking. In the latter case report diagnostic matches, unexplained strong bands and ambiguity per candidate; do not invent numerical scores. Any peak-shift tolerance must be justified by acquisition/reference conditions and applied equally to all candidates.

Source: [NIST quantitative IR reference spectra and measurement conventions](https://webbook.nist.gov/chemistry/quant-ir/).
