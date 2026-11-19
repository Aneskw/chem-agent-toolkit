---
name: gaussian-compare-transition-state-free-energies
description: Optimize supplied transition-state guesses with Gaussian 16, validate the resulting stationary points, and compare their computed Gibbs energies using a supplied calculation protocol.
---

# Compare transition states with Gaussian 16

Use this workflow when candidate geometries and their scientific calculation settings are already available. It starts from Gaussian-ready inputs; it does not generate conformers or choose a basis, solvent model, electronic state or thermochemical correction scheme.

## Environment and prepared inputs

Use licensed **Gaussian 16 Rev. C.02** on a compatible Linux AVX2 host. Obtain the software through [Gaussian](https://gaussian.com/) and follow its [official installation instructions](https://gaussian.com/techsupport/#install); check the [platform requirements](https://gaussian.com/g16/g16_plat.pdf) against the installed binary. The shell examples below use Bash on the calculation host, with `g16` resolved by the site's Gaussian environment. Allocate compute resources and writable scratch through the local scheduler/site setup; Gaussian uses scratch files as well as the retained outputs.

Prepare one input per candidate and keep the originals separately:

| Input | Required content |
| --- | --- |
| `ts-a.com`, `ts-b.com` | Complete Gaussian molecular specifications for supplied TS guesses, including charge, multiplicity, coordinates and any required general-basis/ECP sections. |
| Calculation protocol | Method, basis/ECP, solvent treatment, numerical settings, temperature, pressure, isotope/scaling choices and any intended thermochemical corrections. |
| Comparison definition | Candidate identities and the common reference. Direct conformer comparisons require matching composition, charge and electronic state. |

Set a distinct `%Chk=ts-a.chk` or `%Chk=ts-b.chk` in each working input. Check that `%Mem` and `%NProcShared`, if present, fit the actual resource allocation. Use fresh output names: shell redirection replaces an existing log, and reused checkpoint paths can overwrite earlier results.

## Optimize and calculate frequencies

For each working input, retain the supplied model chemistry and required input sections. Request these route keywords together:

```text
Opt=(TS,CalcFC) Freq
```

This is a route fragment to integrate into the prepared input, not a complete input file. `TS` searches for a transition state; `CalcFC` computes the initial Hessian at the current method. The combined `Opt Freq` job runs frequencies after optimization using the same model chemistry. Do not combine `Opt=TS` with QST2 or QST3. If the supplied protocol requires a different Hessian strategy, preserve that documented strategy instead of adding conflicting options.

Set thermochemical conditions consistently. Gaussian's frequency-analysis defaults are **298.15 K, 1 atmosphere, unscaled frequencies and the most abundant isotopes**. For example, `Temperature=300.0 Pressure=1.0` explicitly selects 300 K and 1 atmosphere; these are illustrative values, not a prescribed scientific protocol. Gaussian 16 uses an UltraFine DFT integration grid by default; retain explicitly supplied numerical settings consistently across the set.

From the working directory containing the prepared inputs, run:

```bash
g16 < ts-a.com > ts-a.log
g16 < ts-b.com > ts-b.log
```

Relative paths in the inputs, including checkpoint paths, resolve from this working directory. Read each complete log before accepting its results. A compact navigation aid is:

```bash
grep -nE 'Optimization completed|Stationary point found|Frequencies --|Sum of electronic and thermal Free Energies|Normal termination|Error termination' ts-a.log ts-b.log
```

The search only locates relevant sections; it does not validate a job automatically. In multi-step or appended logs, associate each quantity with the intended final optimization and frequency calculation.

## Validate before ranking

Check the optimization convergence information and the final frequency calculation, not just the presence of a thermochemistry block. Gaussian prints `Optimization completed` and `Stationary point found` for a completed optimization. Require completion of the intended frequency step and inspect any error termination.

A first-order transition state should have one imaginary vibrational mode, printed as a negative frequency in `Frequencies --` (cm^-1). Inspect its normal-mode displacement vectors to establish that it describes the intended chemical motion. No imaginary mode suggests a minimum; multiple imaginary modes suggest a higher-order saddle or unresolved convergence problem. A single imaginary mode alone does not establish the connected reactants and products; connectivity verification is a separate calculation when required. Do not invent a numerical cutoff to dismiss small negative frequencies.

If optimization fails, the frequency step is missing, or the mode is wrong, report that candidate as unresolved and retain its log. Do not assign it a comparison energy from an earlier step. Correct the starting guess or documented calculation settings before retrying; do not suppress curvature checks merely to obtain convergence.

## Extract and interpret the energies

For each accepted candidate, record the final geometry, checkpoint/log paths, imaginary-mode identity and these quantities from the matching frequency calculation:

| Gaussian output field | Meaning |
| --- | --- |
| `Thermal correction to Gibbs Free Energy` | Correction to electronic energy, including zero-point contributions; not the total Gibbs energy. |
| `Sum of electronic and thermal Free Energies` | Computed total G in Hartree per particle. Use this for the direct, same-level comparison. |

For the accepted set, report `relative_G_i = G_i - min(G_accepted)` in Hartree, retaining the raw G values and calculation conditions. If no candidate passes validation, return the unresolved statuses rather than a ranking. Relative TS energies are computed comparisons; they are not experimental measurements, and a TS-only comparison is not an activation barrier without a reactant reference.

Gaussian's standard thermochemistry uses ideal-gas statistical mechanics and harmonic vibrational treatment. Low-frequency internal motions can materially affect entropy. A solvent electronic calculation does not by itself supply a solution standard-state or hindered-rotor correction. Apply such corrections only when the supplied protocol specifies them, and label the corrected quantities separately. If the protocol combines higher-level single-point energies with lower-level thermal corrections, follow that explicit bookkeeping rather than mixing totals from different jobs.

Consult the official [Opt reference](https://gaussian.com/opt/) for optimization/Hessian options and the [Freq reference](https://gaussian.com/freq/) for mode and thermochemistry output details.
