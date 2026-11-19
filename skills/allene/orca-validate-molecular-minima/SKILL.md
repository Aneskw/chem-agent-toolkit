---
name: orca-validate-molecular-minima
description: Optimize prepared molecular structures with ORCA and assess local-minimum character from geometry convergence and vibrational frequencies. Use when validating a candidate structure at a chosen electronic-structure model.
---

# Validate molecular minima with ORCA

An optimized structure is a candidate local minimum on the selected model's potential-energy surface. Validate geometry convergence and vibrational curvature together. This workflow starts from prepared coordinates, charge, multiplicity and a chosen model; it does not search conformers or establish the global minimum.

## Environment and inputs

Use **ORCA 6.1.1**. Obtain the appropriate platform distribution through the [official release and download entrypoints](https://www.faccts.de/orca-6-1-1/) or the [ORCA Forum](https://orcaforum.kofo.mpg.de/) (registration required). Follow the [official installation instructions](https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html), then open a new terminal with the ORCA executable directory on PATH. The example below runs serially.

Prepare these inputs before running:

| Input | Meaning |
| --- | --- |
| Atomic coordinates | Element symbols and Cartesian coordinates; the XYZ block defaults to angstroms. |
| Charge and multiplicity | Net integer charge and spin multiplicity, 2S+1; both belong on the XYZ opening line. |
| Electronic-structure model | Functional or wavefunction method, basis and any required dispersion/solvation settings. Optimization and frequencies must describe the same model and state. |

Use a separate working directory and job basename for each calculation. Preserve the starting input: optimization produces a new geometry. Redirecting output to an existing filename overwrites that log.

## Optimize and calculate frequencies

Save this complete illustrative input as `water_min.inp`. The water coordinates come from the official quickstart; BP/def2-TZVP is an illustrative model supported by the frequency documentation. Replace the coordinates, charge, multiplicity and model together for the actual system.

```text
! BP def2-TZVP TightSCF TightOpt Freq

* XYZ 0 1
O   0.0000   0.0000   0.0626
H  -0.7920   0.0000  -0.4973
H   0.7920   0.0000  -0.4973
*
```

`TightOpt` requests tighter geometry thresholds than ordinary `Opt`; it still performs a minimum optimization. `TightSCF` reduces numerical noise in derivatives. `Freq` requests analytical frequencies after optimization for this supported DFT model.

From the directory containing the input, run in a POSIX shell or Windows Command Prompt:

```sh
orca water_min.inp > water_min.out
```

If ORCA is not on PATH, use the full executable path. Inspect `water_min.out` after completion. Retain `water_min.gbw`, the binary geometry/basis/wavefunction summary, with the input and log for subsequent calculations. Obtain the optimized coordinates from the completed calculation rather than reusing the starting coordinates.

For another model, check [frequency-method availability](https://www.faccts.de/docs/orca/6.1/manual/contents/structurereactivity/frequencies.html) before retaining `Freq`. Analytical Hessians have restrictions, including double-hybrid functionals and RI-JK. Where supported, `NumFreq` is the alternative; it is more expensive and sensitive to SCF convergence, grids and finite-difference increments. For larger analytical jobs, set `%maxcore` according to available memory using that manual's guidance.

## Assess the completed calculation

Read both the optimization status and the frequency section:

| Evidence in the log | Interpretation and next action |
| --- | --- |
| `THE OPTIMIZATION HAS CONVERGED` | Geometry optimization converged. Continue to the frequency results. |
| Warning that optimization reached the maximum number of cycles | Geometry validation is incomplete, even if `ORCA TERMINATED NORMALLY` also appears. Resolve nonconvergence before claiming a minimum. |
| Missing or incomplete `VIBRATIONAL FREQUENCIES` section | Curvature validation is incomplete. Inspect the calculation failure before interpreting the structure. |
| Significant negative vibrational frequencies, printed in `cm**-1` | The stationary point has saddle-point curvature and is not a minimum. Inspect the associated displacement before revising the geometry and reoptimizing. |
| Small negative modes | Assess numerical sensitivity using tighter geometry/SCF convergence and appropriate grids; for numerical frequencies also examine the displacement increment. Do not classify them using an invented universal cutoff. |
| No significant negative vibrational modes after numerical concerns are resolved | Supports local-minimum character at the chosen model and electronic state. |

Default frequency processing projects out translations and rotations; ordinary nonlinear molecules therefore show six zero modes. These projected zeros do **not** measure Hessian quality. Keep the default projection for ordinary thermochemical use; disabling it can contaminate entropy and Gibbs-energy estimates.

Report the model and electronic state, geometry convergence status, any negative frequencies and their interpretation, and paths to the input, completed log and optimized structure artifact. Keep unresolved convergence or curvature concerns explicit. See [geometry convergence notes](https://www.faccts.de/docs/orca/6.1/manual/contents/structurereactivity/optimizations.html#some-general-notes-on-geometry-optimization) when termination and optimization status disagree.

## Supplied PBEh-3c protocol

When the supplied protocol is PBEh-3c, retain its complete composite model. A
representative route is:

```text
! PBEh-3c TightSCF Opt Freq
```

`PBEh-3c` includes its modified def2-mSVP basis, gCP and D3 dispersion treatment.
Do not add a separate basis or replace its dispersion with D4. Check element
coverage in the [ORCA 6.1 method entry](https://www.faccts.de/docs/orca/6.1/manual/contents/modelchemistries/3cmethods.html#pbeh-3c).
For a supplied SMD-benzene protocol, retain this block before the coordinates:

```text
%cpcm
  smd true
  SMDsolvent "benzene"
end
```

Omit that solvent block for gas phase. Keep the chosen model and solvent through
optimization and frequencies; plain C-PCM is a different solvent treatment. The
same convergence and vibrational checks above apply.
