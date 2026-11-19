---
name: matlab-estimate-oxygen18-incorporation
description: Fit labeled/unlabeled isotope-envelope mixtures in MATLAB and estimate oxygen-18 incorporation when the reference normalization and relative response support an amount-ratio interpretation.
---

# Oxygen-18 incorporation from isotope envelopes

Use a numeric least-squares mixture model when overlapping isotope peaks prevent reading incorporation from one peak. Start with measured abundances and supplied simulated envelopes for the intended oxygen-18-labeled and unlabeled forms of the same compound and ion/adduct. Spectrum acquisition, peak assignment and reference-envelope simulation are external preparation.

## Environment

Use **MATLAB R2026b** with numeric double arrays. Obtain the licensed software through MathWorks' [Download and Install MATLAB](https://www.mathworks.com/help/install/ug/install-products-with-internet-connection.html) instructions; select R2026b and sign in with the account associated with your license. The calculation uses core MATLAB matrix operations.

## Prepare the mixture

Keep one row per corresponding mass peak across all three spectra. Use the same ion/adduct and peak ordering throughout.

| Input | Shape | Meaning |
| --- | --- | --- |
| `observed` | m-by-1 | Measured relative peak abundances |
| `labeled` | m-by-1 | Simulated abundances for the 100% labeled reference form, with the intended label count |
| `unlabeled` | m-by-1 | Simulated abundances for the unlabeled form |
| Optional `response_scale` | 2-by-1 | Calibrated coefficient response per unit amount for the labeled and unlabeled forms, in that order, using the supplied reference-column scaling |

Use more than two informative peaks and references whose columns are distinguishable. Supply finite, nonnegative numeric abundances. The published example scales each spectrum's base peak to 100; retain that convention to reproduce its coefficient-ratio calculation. Divide the values by 100 to form `A` and `b`, without forcing fitted coefficients to sum to one.

Independent reference-column normalization changes the coefficient ratio. It does not generally preserve a molecular amount ratio, even for a perfect fit. Establish the relative response through calibration or complete reference envelopes with justified response assumptions. A measured peak window may omit different fractions of the two envelopes; normalizing those truncated columns to unit sum does not resolve that problem. Keep the response factors consistent with any deliberate rescaling of the reference columns.

## Fit and calculate

Run the following in the MATLAB Command Window or an Editor script. These are the published E-2h peak abundances from [He et al., section 4.3.18, pp. 4886-4887](https://doi.org/10.1016/j.tet.2009.04.023). Replace all three abundance vectors together for another prepared sample, retaining their row correspondence.

```matlab
peak_mz = [489.05; 490.06; 491.04; 492.06; 493.02; 494.04; 495.02];
observed = [20.64; 21.55; 56.66; 18.08; 100; 28.07; 22.58];
labeled = [18.561; 20.515; 52.147; 14.585; 100; 29.099; 21.547];
unlabeled = [52.134; 14.631; 100; 29.134; 21.739; 5.580; 0.837];

A = [labeled unlabeled] / 100;
b = observed / 100;

c = A\b;                    % c(1): labeled; c(2): unlabeled
fitted = A*c;
residual = b - fitted;

if any(~isfinite(c)) || any(c < 0) || sum(c) <= 0
    error('Unusable mixture coefficients: inspect inputs and the model.');
end
coefficient_share = c(1) / sum(c);
coefficient_share_percent = 100 * coefficient_share

% Supply calibrated factors in the reference-column convention above.
% Leave empty when their relative amount response is unknown.
response_scale = [];
incorporation_fraction = [];
incorporation_percent = [];
if isempty(response_scale)
    disp('Molar incorporation unavailable: reference response is not established.');
else
    response_scale = response_scale(:);
    if numel(response_scale) ~= 2 || any(~isfinite(response_scale)) ...
            || any(response_scale <= 0)
        error('Supply two positive finite response factors, labeled then unlabeled.');
    end
    relative_amount = c ./ response_scale;
    incorporation_fraction = relative_amount(1) / sum(relative_amount);
    incorporation_percent = 100 * incorporation_fraction
end
```

For numeric rectangular arrays, [`mldivide` (`A\b`)](https://www.mathworks.com/help/matlab/ref/double.mldivide.html) returns an unconstrained least-squares solution. Here `A` is m-by-2, `b` is m-by-1 and `c` is 2-by-1. Use numeric arrays rather than symbolic equations.

`response_scale(j)` means that one unit amount of component j produces a signal proportional to `response_scale(j) * A(:,j)`, with one common instrument factor across components. Thus `c(j)/response_scale(j)` is proportional to amount. The factors need only a common relative scale. Equal factors are justified only when the reference columns have equal coefficient response per unit amount; do not assume that from base-peak normalization. Without those factors, report the published-style coefficient share and its normalization rather than a calibrated incorporation percentage.

## Read the result

All results remain in the MATLAB workspace:

- `c`: fitted component scale coefficients in labeled/unlabeled order; these are not already fractions.
- `coefficient_share` and `coefficient_share_percent`: the labeled reference's share of fitted scale coefficients; these are normalization-dependent.
- `incorporation_fraction` and `incorporation_percent`: the labeled amount share after the supplied response correction; empty when that interpretation is unresolved.
- `fitted` and `residual`: m-by-1 vectors in the same row order as `peak_mz`, on the abundance/100 scale. Multiply by 100 to compare with the input abundance scale.

Inspect the coefficients, residuals and any solver warning before reporting incorporation. Investigate row mismatches, reference scaling or an inadequate mixture model if coefficients are negative or nonfinite, their sum is nonpositive, or the fit disagrees materially with the measured envelope. Do not clip coefficients or silently substitute a constrained fit. A zero labeled coefficient with a positive unlabeled coefficient gives zero labeled share within this two-component model; retain the response assumptions and measurement limits.

MATLAB may continue after scaling or near-singularity warnings; a returned vector alone does not establish a reliable estimate. A small residual resolves neither indistinguishable reference envelopes nor unknown relative response. Return the normalization, any response factors and their provenance, coefficients, residuals, and the interpretation actually supported. Isotope location and a reaction mechanism require separate evidence.
