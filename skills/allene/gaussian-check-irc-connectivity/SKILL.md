---
name: gaussian-check-irc-connectivity
description: Follow both IRC directions from a frequency-characterized transition structure in Gaussian 16 and optimize the endpoints to assess which minima it connects. Use when the transition structure and consistent model chemistry are already supplied.
---

# Check transition-state connectivity with Gaussian IRC

## Prepare the environment and starting artifacts

Use licensed **Gaussian 16 Revision C.02** on a compatible platform from the [official platform table](https://gaussian.com/g16/g16_plat.pdf). Obtain access through your institution or [Gaussian](https://gaussian.com/contact/); follow its [installation instructions](https://gaussian.com/techsupport/#install). The commands below use a Bash shell and a configured `g16` executable in an allocated compute environment. A documented institutional setup is [GWDG Gaussian](https://docs.hpc.gwdg.de/software_stacks/applications/gaussian/index.html), where `module load gaussian/16-C.02` selects this revision. Other sites have their own environment and scheduler setup. Match `%NProcShared` to allocated cores and `%Mem` to available job memory.

Have these inputs ready:

| Input | Required content |
| --- | --- |
| Characterized TS | Optimized geometry, charge, multiplicity, atom identities/order and frequency result establishing a first-order saddle (one imaginary vibrational mode). Inspect that mode for the intended reaction motion. |
| Model chemistry | The supplied method, basis/ECP, dispersion, solvent, integration/grid and other settings defining the surface. Retain these through IRC, endpoint optimization and frequency analysis. Include any required extra basis/ECP or solvent input sections. |
| Optional frequency checkpoint | A compatible Gaussian checkpoint containing the Cartesian force constants at that same TS and model chemistry, for `RCFC`. Otherwise use `CalcFC`. |

This workflow starts after TS characterization. It assesses the connected minima; it does not discover a TS or establish that all competing mechanisms have been found. For methods without analytic second derivatives, consult the [IRC availability and GradientOnly options](https://gaussian.com/irc/) before adapting this normal path.

## Follow the path

Create an ASCII file `ts-spec.inc`: first the supplied integer charge and spin multiplicity, then one `Element x y z` line per atom in the supplied TS geometry, and a terminating blank line. Retain atom order and isotope assignments. Use the coordinate units of the characterized Gaussian input and retain its unit-setting route option, if present, in `MODEL_AND_SETTINGS`. This is an external molecular input, not coordinates supplied by this package. Gaussian's [input syntax](https://gaussian.com/input/) supports `@filename` inclusion.

Create `irc.com` below. Replace `MODEL_AND_SETTINGS` with the supplied route settings (for example, `HF/6-31G(d)` only if that is the model used to characterize this TS). Remove previous job-type keywords such as `Opt` and `Freq`. The resource values and `MaxPoints=20` are illustrative choices. Preserve the blank lines and add any required extra input sections after the molecule specification.

```text
%Chk=irc.chk
%Mem=2GB
%NProcShared=8
# MODEL_AND_SETTINGS IRC=(CalcFC,Report=Cartesians,MaxPoints=20)

IRC from characterized transition structure

@ts-spec.inc

```

From the directory containing these inputs, run inside the site's compute allocation:

```bash
g16 < irc.com > irc.log
```

`irc.log` is the text result and `irc.chk` preserves checkpoint state. Use new names for independent runs; shell `>` replaces an existing log. Retain the TS input/frequency artifacts separately.

To reuse the initial Hessian, copy the supplied frequency checkpoint to `irc.chk` before running, and replace only `CalcFC` by `RCFC` in the template. Keep the explicit molecule input at exactly the checkpoint's characterized geometry and atom order. `RCFC` reads Cartesian force constants from that checkpoint; it cannot substitute an unrelated optimization checkpoint. The copy protects the original frequency checkpoint as the IRC updates its working state.

| IRC control | Meaning |
| --- | --- |
| Direction | Both directions are followed by default. `Forward` or `Reverse` selects only one. These labels depend on the transition-vector phase, not reactant/product identity. |
| `MaxPoints=N` | Maximum path points **per direction**; default 10. A point limit alone does not establish arrival at a minimum. |
| `StepSize=N` | Default 10. Positive N uses units of 0.01 bohr; negative N uses 0.01 amu^(1/2)-bohr. These are path-step units. |
| `Report=Cartesians` | Reports all Cartesian coordinates. It does not change the default mass-weighted Cartesian path to an unweighted path; `Cartesian` is a separate option. |
| `Restart` | Continues an incomplete IRC or extends a completed path. Preserve the IRC checkpoint and use the documented [IRC restart option](https://gaussian.com/irc/), increasing `MaxPoints` when more points are needed. |

## Inspect the path and optimize both endpoints

Locate `Reaction path calculation complete.` and `Summary of reaction path following` in `irc.log`; inspect any failure or nonconvergence messages before interpreting the path. The summary reports energies relative to the TS, whose reaction coordinate and relative energy are zero. Identify the terminal point on **each** branch and recover its full geometry from the Cartesian reporting, matching point labels and atom order. Do not assume the last geometry printed is both endpoints or that a completed short path has reached minima. If either branch needs more tracing, extend the IRC before assigning connectivity.

Prepare `endpoint-a-spec.inc` and `endpoint-b-spec.inc` from those two terminal geometries, in the same molecule-specification format as `ts-spec.inc`. Read the coordinate units from the output and convert the extracted values to the units used in `ts-spec.inc`, retaining the same unit-setting option; never treat a reaction-coordinate value as an atomic coordinate. Preserve the full system, charge, multiplicity and isotope identities.

For endpoint A, create `endpoint-a.com`:

```text
%Chk=endpoint-a.chk
%Mem=2GB
%NProcShared=8
# MODEL_AND_SETTINGS Opt Freq

Optimize IRC endpoint A and characterize it

@endpoint-a-spec.inc

```

Use the same model/settings as the IRC, with required additional input sections. Make the corresponding endpoint B input with its own checkpoint, title and include filename. Run both:

```bash
g16 < endpoint-a.com > endpoint-a.log
g16 < endpoint-b.com > endpoint-b.log
```

`Opt` searches for a local minimum by default; `Opt Freq` automatically follows optimization with a frequency calculation at the optimized geometry. Inspect `Optimization completed.`, the final optimized coordinates and energy, and the `Frequencies --` entries in each log. A minimum should have no imaginary vibrational modes. Investigate residual imaginary modes or failed convergence before assigning a minimum; use the [Freq documentation](https://gaussian.com/freq/) for low-frequency interpretation. Frequencies must use the same model chemistry as the endpoint optimization.

Assign reactant/product identities by the optimized structures and relevant bond changes, not by forward/reverse names. Deliver the two endpoint structures, their optimization/frequency status, their branch-to-minimum mapping, and the IRC log/checkpoint alongside the endpoint logs/checkpoints. If either endpoint remains unresolved, report connectivity as unresolved for that branch. These calculated connections support a local connectivity assignment on the chosen potential-energy surface, rather than proving a unique experimental mechanism.
