---
name: gaussian-locate-transition-states
description: Locate a proposed reaction transition structure in Gaussian 16 using matched reactant/product geometries or a supplied TS guess, and check the optimized structure with a same-model frequency calculation.
---

# Locate and characterize a Gaussian transition structure

Use prepared structures and a validated model chemistry. This workflow returns an optimized candidate structure, its harmonic frequencies and normal modes, and a checkpoint for further analysis. It does not enumerate reaction mechanisms or conformers.

## Environment and inputs

Use **Gaussian 16 Revision C.02** through a licensed installation on a compatible platform. Obtain access through [Gaussian Inc.](https://gaussian.com/gaussian16/) or your institution; consult the official [platform requirements](https://gaussian.com/g16/g16_plat.pdf). The examples below use Bash and an initialized installation in which `g16` resolves. On GWDG, follow its [access and setup instructions](https://docs.hpc.gwdg.de/software_stacks/applications/gaussian/index.html), then use `module load gaussian/16-C.02`. Module names elsewhere are site-specific.

Arrange compute allocation and scratch storage using the installation's instructions. Match `%NProcShared` to allocated CPU cores and keep `%Mem` within the allocation.

| Input | Required preparation |
| --- | --- |
| Reactant and product for QST2 | Same atoms in exactly the same order, including hydrogens; consistent charge and multiplicity for the proposed reaction. Supply all atoms of a multicomponent system in each structure. |
| Model chemistry | Validated Gaussian route tokens for the method, basis, dispersion and solvent settings, plus any required extra input sections. Keep these consistent through optimization and frequencies. |
| Alternative TS guess | One prepared geometry near the proposed saddle point, with charge and multiplicity. Use the single-structure path below. |

For the example, prepare `reactant.geometry` and `product.geometry` as **Gaussian molecule-specification sections**: a charge/multiplicity line followed by all atom lines, with Cartesian coordinates in angstroms. These are external inputs. They contain no title, XYZ atom-count header, comment line or blank lines; each ends with one newline. For example, a neutral singlet section begins with `0 1`, then one `element x y z` line per atom. Convert other formats before using this template.

## QST2 search and frequency calculation

QST2 requires two title/molecule sections. Gaussian generates a TS starting structure from the reactant/product pair and searches for a first-order saddle. Do not add `TS` to `QST2`.

Run from a dedicated job directory containing the two prepared geometry files. This example assembles the sections without changing atom order:

```bash
# HF/6-31G(d) illustrates documented route syntax.
# Set this to the supplied validated model chemistry for the actual calculation.
model='HF/6-31G(d)'

{
  printf '%%Chk=ts.chk\n%%Mem=2GB\n%%NProcShared=8\n'
  printf '#p %s Opt=QST2 Freq\n\nReactant\n\n' "$model"
  cat reactant.geometry
  printf '\nProduct\n\n'
  cat product.geometry
  printf '\n'
} > ts.com

g16 < ts.com > ts.log
```

The resource values are examples. The assembly shown assumes the selected model chemistry needs no additional input sections. If it does, append those sections in the documented order before submission.

`Opt` and `Freq` on the same route request optimization followed by frequencies at that optimized geometry. Keep the model chemistry unchanged between those stages. A frequency calculation at a geometry optimized with a different method or basis does not provide the required stationary-point characterization.

The command writes the log to `ts.log`; `%Chk=ts.chk` retains the checkpoint in the job directory. Shell redirection replaces an existing log, and the job updates its checkpoint: use fresh output names or a separate directory for another attempt.

## Starting from a TS guess

When a prepared TS guess is available, use one title/molecule section and replace the optimization request with:

```text
#p <validated model chemistry> Opt=(TS,CalcFC) Freq
```

Replace the angle-bracketed text with the actual route tokens. Supply the same resource/checkpoint directives as above and one title, blank line, charge/multiplicity and complete geometry. `CalcFC` computes initial force constants at the selected method. Submit with the same `g16 < input.com > output.log` form, using distinct filenames.

## Inspect the result

1. In the optimization portion of the log, find `Optimization completed.` and `Stationary point found.`. Inspect the final optimized structure and the optimized-parameter table; QST2 also lists reactant/product parameter values for comparison. An interrupted or unconverged optimization is not a localized stationary point.
2. Confirm the subsequent frequency calculation completed. Inspect `Frequencies --` values in cm⁻¹ and the associated atomic displacement vectors. A first-order saddle has one imaginary vibrational mode, conventionally displayed as a negative frequency. All-real vibrational modes characterize a minimum; multiple imaginary modes indicate a higher-order saddle. Inspect near-zero modes carefully rather than imposing an arbitrary cutoff.
3. Check that the imaginary mode's displacements describe the proposed bond changes. Its count alone does not identify which reaction the structure connects. A wrong mode or wrong saddle requires revisiting the structures/search, not declaring success from optimization completion.
4. Retain `ts.com`, `ts.log`, `ts.chk`, the final geometry and the mode assessment. Use an [IRC calculation](https://gaussian.com/irc/) as a separate connectivity check when assigning reactant/product minima; preserve the frequency checkpoint for that handoff.

If optimization succeeds but frequencies fail or are absent, report the structure as uncharacterized. If frequency analysis indicates that the geometry was not sufficiently converged, the [Freq documentation](https://gaussian.com/freq/) describes `Opt=CalcAll` for further optimization using computed second derivatives. Consult the [Opt reference](https://gaussian.com/opt/) for search options and input details. Report the located structure and its calculated characterization separately from any experimental or mechanistic conclusion.
