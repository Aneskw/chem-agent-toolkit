---
name: gaussian-export-ecd-transition-data
description: Generate TD-DFT excitation energies and signed ECD rotatory strengths with Gaussian 16 for supplied optimized molecular conformers, and export per-conformer transition tables.
---

# Gaussian TD-DFT ECD transition data

## Prepare the environment and inputs

Use licensed **Gaussian 16 Revision C.02, Linux x86_64 AVX2**. Obtain access through [Gaussian Orders/Contact](https://gaussian.com/orders/) or a licensed institutional installation. Follow the official [installation entrypoint](https://gaussian.com/techsupport#install). Use an AVX2-capable host and a supported OS from the [binary platform table](https://gaussian.com/g16/g16_plat.pdf), such as RHEL 8.3. Have the installation administrator configure executable access and writable scratch storage; `g16` must resolve in the execution shell. On a cluster, use its Gaussian module and scheduler allocation; module names are site-specific.

Required inputs per conformer:

| Input | Required content |
| --- | --- |
| Geometry | Supplied optimized coordinates, one `Element x y z` row per atom, distances in angstroms. Preserve the intended stereochemistry. |
| Molecular state | Integer net charge and spin multiplicity. |
| Model | Explicitly chosen Gaussian DFT functional/basis and, if required, solvent settings and any additional basis/ECP input. |
| State count | Positive integer `M` for `TD=(NStates=M)`. The default is only three states. |
| Resources | Allocated CPU count and memory for `%NProcShared` and `%Mem`. |

The normal path is a vertical TD calculation at each supplied geometry. Conformer searching, optimization, population weights, spectrum broadening and absolute-configuration assignment are external workflows.

## Write and run one conformer job

In a separate working directory for each conformer, save its coordinate rows as ASCII `conf01.coords`. This file contains **only atom rows**, without an XYZ atom-count/comment header, charge/multiplicity or internal blank lines. Gaussian's `@filename` input inclusion expands this file at the indicated position.

Create `conf01.com`:

```text
%NProcShared=4
%Mem=5GB
%Chk=conf01.chk
# B3LYP/cc-pVDZ TD=(NStates=20)

Conformer 01 vertical TD

0 1
@conf01.coords

```

Keep the blank lines after the route, title and molecule specification, including a terminating empty line. The model, 20 states, resources and neutral singlet above are **example choices**: replace them with the selected model, requested count, allocated resources and supplied charge/multiplicity. If the chosen model includes solvent or extra basis/ECP sections, include its corresponding Gaussian keywords and required input sections. Consult [input syntax](https://www.conflex.co.jp/gaussian_support/input.php) for section layout.

For a closed-shell reference, TD defaults to singlet excited states. `Singlets` and `Triplets` options apply only to closed-shell singlet systems; do not force them onto an open-shell input. Use the supplied reference and multiplicity. See the [TD options and output reference](https://www.conflex.co.jp/gaussian_support/td.php) for other state manifolds.

From that directory in the configured Linux shell, run within the allocated compute resources:

```bash
g16 < conf01.com > conf01.log
```

The redirection creates or overwrites `conf01.log`; choose unique input, log and checkpoint names for each conformer. Read the log after completion, including its revision banner and termination/error diagnostics. A partial log or unconverged calculation is not a completed transition dataset; resolve the reported failure before exporting it as successful.

## Extract and hand off the transitions

Within the same completed job, locate:

1. `Excited State n:` lines: retain state number, spin/symmetry label, excitation energy in **eV**, wavelength in **nm**, and `f=` oscillator strength.
2. The `Rotatory Strengths (R)` table with column **`R(length)`**. Match rows to the excitation lines by their integer state number, rather than by nearby line position. This table may precede the excitation summary.

Export `conf01-transitions.csv` with this header and one row per matched state:

```csv
conformer,state,state_label,energy_eV,wavelength_nm,oscillator_strength,R_length_cgs
```

`oscillator_strength` is dimensionless and describes ordinary absorption; it is not the signed ECD quantity. Preserve the sign of `R(length)`. The documented table reports it in **10^-40 erg-esu-cm/Gauss**; retain those printed values in `R_length_cgs` and carry this unit in accompanying table metadata. Do not substitute `R(au)`, tensor components, or another gauge's column.

Check that the completed calculation contains the requested states and that every exported state has both excitation and rotatory-strength records. Report missing or unmatched records explicitly; do not fill them with zeros. Actual printed zero rotatory strengths are valid output, including all-zero tables in the documentation example. Keep printed precision.

Deliver each conformer's input, coordinate file, full log and transition CSV, with a small manifest recording Gaussian revision, model/solvent settings, charge/multiplicity, requested state count and rotatory-strength units. Retain the checkpoint if further Gaussian work needs it. Keep conformers separate: state indices identify records within one calculation and do not establish state correspondence across conformers.

These are calculated discrete transitions for downstream population averaging and spectrum construction. Their signs alone do not assign absolute configuration.
