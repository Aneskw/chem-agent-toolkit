---
name: gaussian-compare-electronic-and-thermal-pathway-energies
description: Use Gaussian 16 to optimize supplied intermediates and transition-state guesses, check frequencies, and compare electronic or thermochemical energies for competing reaction pathways. Select when prepared molecular inputs and the intended model chemistry are available.
---

# Compare reaction-pathway energies with Gaussian

## Environment and starting inputs

Use **Gaussian 16 Revision C.02**, Linux AVX2 build, with licensed access and an allocated compute node. Obtain access through [Gaussian](https://gaussian.com/) or an institution with a Gaussian license. Check the [official supported-platform matrix](https://gaussian.com/g16/g16_plat.pdf) against the machine. This workflow uses single-node CPU execution.

For an existing installation, follow the institution's environment setup. For example, [CURC's Gaussian instructions](https://github.com/ResearchComputing/Documentation/blob/main/docs/software/gaussian.md) document `module load gaussian/g16_c.02` on Alpine. That module name and its scratch paths are site-specific; use the local C.02 equivalent elsewhere. Set `GAUSS_SCRDIR` to an existing writable scratch directory for the allocated job. Match Gaussian's processor and memory requests to the allocation, leaving memory for process overhead.

Supply complete Gaussian input files for an intermediate and the competing transition-state guesses. Each must already contain:

- The intended functional, basis/ECP assignments, solvent treatment and other model-chemistry settings.
- A chemically prepared geometry, charge and spin multiplicity; keep the supplied coordinate representation and any required additional input sections.
- Consistent temperature, pressure, isotope and frequency-scaling conventions across the comparison.

Geometry construction, model-chemistry selection, conformer enumeration and fragment decomposition are external preparation. Do not infer missing basis/ECP assignments from element names. Frequencies must use the same method and basis as the geometry optimization.

## Prepare and run the jobs

Work in a new calculation directory. The example starts with three externally supplied complete decks in `inputs/`. Copy them so that job-type edits preserve the originals:

```bash
mkdir pathway-run
cp inputs/intermediate.com pathway-run/intermediate.com
cp inputs/ts-a.com pathway-run/ts-a.com
cp inputs/ts-b.com pathway-run/ts-b.com
cd pathway-run
```

In the copies, replace existing job-type keywords with the following route options, retaining the supplied model chemistry and its additional sections:

| File | Route options | Purpose |
| --- | --- | --- |
| `intermediate.com` | `Opt Freq` | Optimize a local minimum, then calculate frequencies there |
| `ts-a.com`, `ts-b.com` | `Opt=(TS,CalcFC) Freq` | Optimize a supplied TS guess with an initial computed Hessian, then calculate frequencies |

Retain blank lines separating the route, title, charge/multiplicity and geometry sections, plus the required terminal blank line. Give each deck a distinct checkpoint name. For example, the Link 0 section of `ts-a.com` could be:

```text
%Chk=ts-a.chk
%Mem=5GB
%NProcShared=4
```

These resource values are illustrative. Use values suitable for the allocated node and molecule. Keep checkpoint directives after any `%NoSave` directive so the checkpoints are retained. The relative checkpoint names resolve in the calculation directory.

Once the copies are complete and the local C.02 environment and scratch are configured, invoke Gaussian from that directory:

```bash
g16 < intermediate.com > intermediate.log
g16 < ts-a.com > ts-a.log
g16 < ts-b.com > ts-b.log
```

Each command writes the calculation's text output to its `.log`; the `%Chk` directive names the binary checkpoint. Shell `>` replaces an existing log, so use a fresh directory or new names for reruns. Preserve both logs and checkpoints. The [MSU command-line example](https://docs.icer.msu.edu/Running_Gaussian_by_Command_Lines/) explains the input sections and redirection form.
## Inspect results before comparing energies

Search each log, then inspect the surrounding final optimization and frequency sections:

```bash
grep -nE 'Optimization completed|Stationary point found|Frequencies --|Sum of electronic and|Thermal correction to' intermediate.log ts-a.log ts-b.log
```

An `Optimization completed` message alone does not establish the stationary-point type. Inspect all vibrational modes from the final frequency calculation:

- A minimum should have no imaginary vibrational modes.
- A first-order saddle should have exactly one. Gaussian prints imaginary frequencies as negative values in `Frequencies --` rows, in cm^-1. Inspect that mode's atomic displacements to determine whether they describe the intended chemical motion.
- Multiple imaginary modes, a wrong reaction mode or unresolved very small negative modes require further examination. Do not apply an arbitrary cutoff to erase them.

One imaginary mode alone does not establish which minima the structure connects. If endpoint connectivity is unknown, obtain separate reaction-path validation before assigning the barrier to a specific reaction. This package does not perform that validation.

Inspect the final optimized geometry and the energy immediately preceding the completed optimization. Frequency output can itself contain Berny initialization text; this does not imply a new completed optimization. If convergence fails, the frequency section is absent, or the calculation stops early, report an incomplete result rather than substituting an earlier iteration's energy. Consult [Opt examples](https://gaussian.com/opt/) and [Freq output documentation](https://gaussian.com/freq/) for these distinctions.

Build a compact result table with state label, geometry/checkpoint path, frequency classification and the chosen energy quantity:

| Quantity | Output access | Meaning |
| --- | --- | --- |
| Electronic energy | Final optimization step | Electronic energy at the optimized structure |
| Zero-point-corrected energy | `Sum of electronic and zero-point Energies` | Electronic energy plus ZPE |
| Enthalpy | `Sum of electronic and thermal Enthalpies` | Electronic energy plus thermal enthalpy correction |
| Gibbs energy | `Sum of electronic and thermal Free Energies` | Electronic energy plus thermal Gibbs correction |

The thermochemical energy values are in Hartree per particle. The `Thermal correction to ...` fields are corrections, not total energies; do not add ZPE again to a printed corrected total. Record the temperature and pressure actually used. Gaussian's documented defaults are 298.15 K, 1 atmosphere, unscaled frequencies and the most abundant isotopes.

## Compare like quantities

For alternatives A and B with the same composition and a common intermediate I, calculate either electronic-energy differences or corresponding Gibbs-energy differences consistently:

```text
barrier_A = G(TS_A) - G(I)
barrier_B = G(TS_B) - G(I)
relative_TS_preference = G(TS_B) - G(TS_A)
```

Keep these differences in Hartree unless explicitly converting units. A positive last value places TS_A lower within this model. If a reference state comprises several separate species, use the stoichiometric sum of their corresponding energies; include all components needed to balance the comparison. Report the reference state and energy type with each difference.

Gaussian's default thermochemistry uses ideal-gas statistical expressions and harmonic vibrations. Low-frequency internal rotations can strongly affect entropy and Gibbs energies. A solvent model does not automatically establish a solution standard-state correction. Report the conventions actually supplied; do not silently add corrections or change methods between states. Treat the resulting ordering and barriers as model predictions, with scientific interpretation dependent on the supplied structures, connectivity and computational model.
