---
name: dp4plusapp-rank-stereoisomer-candidates
description: Rank two or more supplied stereoisomer candidates with DP4+App using assigned experimental 1H/13C NMR shifts and completed Gaussian conformer calculations.
---

# Rank stereoisomers with DP4+App

Use standard DP4+ to correlate experimental shifts with conformer-weighted Gaussian shieldings and rank the supplied candidates. Candidate structures, conformational sampling and completed calculations are external inputs. The ranking is conditional on that candidate set, conformer coverage, assignments and statistical model; it does not establish absolute structural truth.

## Setup

Use [DP4+App 2.2.3](https://pypi.org/project/dp4plus-app/2.2.3/) in a desktop environment. The [official setup guide](https://github.com/Sarotti-Lab/DP4plus-App#installation-requirements) documents Python 3.8–3.11.9 compatibility; choose [Python 3.11.9](https://www.python.org/downloads/release/python-3119/). Python 3.12 and later are outside that documented support range. In the selected Python environment:

```sh
python -m pip install dp4plus-app==2.2.3
dp4plus
```

The `dp4plus` GUI executable must resolve from that environment's Scripts/bin directory. This workflow requires GUI interaction; the launch command does not submit an analysis by itself. If desktop control is unavailable, hand the prepared inputs and settings to a GUI operator and resume from the exported workbook.

Open the DP4+ tab's User Guide/example chooser and export the NMR-only example (`example_nmr_only`). It copies the bundled example to the Desktop; that directory must exist. Copy its correlation workbook as a template, then replace the example data with the supplied assignments. The [official guides](https://github.com/Sarotti-Lab/DP4plus-App/tree/main/User%20Guides%20and%20Examples) are a fallback for interface details. Bundled examples contain deliberately broken `brk` files and incomplete demonstration ensembles; keep those out of production inputs.

## Prepare a working copy

Use a separate writable analysis folder: validation can **move Gaussian files** into `fail files`. Keep original calculations elsewhere.

For every conformer of each candidate, supply a Gaussian `.log` or `.out` containing NMR isotropic shieldings, SCF energy and normal termination. The Gaussian route must contain `nmr`. These are completed outputs from [Gaussian](https://gaussian.com/nmr/), not structure files or exported shift lists.

Name files `n_m_*_nmr.log`: `n` is the candidate ID, `m` the conformer number, and `*` an annotation. For example:

```text
analysis/
  01_001_sample_nmr.log
  01_002_sample_nmr.log
  02_001_sample_nmr.log
  02_002_sample_nmr.log
  correlation.xlsx
```

These names are illustrative; retain the full supplied conformer ensembles. Keep Gaussian atom numbering consistent across conformers of a candidate. Use equal-width numeric candidate IDs such as `01`, `02` to make the detected order unambiguous.

Edit the workbook's **`shifts`** sheet; other input sheets are ignored. Preserve these fields:

| Field | Required content |
|---|---|
| `index` | Experimental signal identifier |
| `nuclei` | Uppercase `H` or `C` |
| `sp2` | `x`, `X` or `1` for sp2; blank otherwise |
| `exp_data` | Numeric experimental chemical shift in ppm |
| `exchange` | Blank for fixed assignments; the same letter on exactly two interchangeable signals |
| `label 1`, `label 2`, `label 3` | Gaussian atom numbers, starting at **1**; unused cells blank |

Use one row per experimental signal. Put equivalent nuclei such as the three methyl protons in the same label triplet: the software averages their shieldings. Do not give them independent experimental rows. Each row needs at least one label in each mapping triplet. For unresolved diastereotopic signals, use two rows with the same exchange letter; the software reorders that pair to match calculated and experimental shift ordering. Leave exchange blank when independent evidence fixes the assignment.
If all candidates use identical atom numbering, share one triplet. Otherwise append one triplet per candidate, in the candidate order displayed in the status bar; retain the template's grouped-column layout. The parser assigns successive groups of three by position, not by candidate names in headers. Do not add annotation columns: every column beyond the five data fields is interpreted as a label column.

## Run the ranking

For a representative NMR-only analysis, assume the supplied calculations used B3LYP/6-31G(d) optimized geometries and mPW1PW91/6-31+G(d,p) NMR shieldings in PCM chloroform. This is the documented example configuration; adapt the selection to the actual calculations, rather than relabeling incompatible data.

1. In the **DP4+** tab select:

   | Control | Example selection |
   |---|---|
   | Functional | `mPW1PW91` |
   | Basis set | `6-31+G(d,p)` |
   | Solvatation | `PCM` |
   | Solvent | `CHCl3` |
   | Energy | `SCF (nmr)` |

2. Select the NMR directory `analysis/`, then `correlation.xlsx`. Check the detected candidate IDs/order against the mapping triplets. Correct workbook validation errors and inspect any files moved to `fail files`; restore corrected calculations before accepting a ranking from the intended ensemble.
3. Press **Run** once enabled. Resolve theory-level/route mismatches. The application permits proceeding after some warnings, but selecting a different statistical level does not transform the supplied calculations. Standard DP4+ parameters assume the supported QM geometry/theory combinations; an unparameterized level requires a separately prepared Custom analysis.
4. If a halogen prompt appears, select **DP4+** for this standard path. HALO changes referencing and is a different intentional analysis choice.
5. Wait for the completion notification, then open the exported workbook in the selected NMR working directory.

`SCF (nmr)` uses the NMR calculations' electronic energies for Boltzmann weighting. Version 2.2.3 weights conformers within each candidate at **298.15 K**; this is not an experimental-temperature input.

**Alternative supplied energies.** If the intended analysis requires separate energies, choose `SCF (other)` for single-point electronic energies or `Gibbs (freq)` for frequency-derived Gibbs free energies. Select the energy directory and leave Gaussian-link mode unchecked for separate files. Pair each NMR output with an identically named energy output except for replacing `nmr` with `energy`, e.g. `01_001_sample_energy.log`. Gibbs inputs must contain a completed frequency calculation and its thermal free energy. Energy choice changes conformer weights; record it with the ranking. For combined Gaussian-link outputs, use the dedicated link guide/example before proceeding; they are not separate-file inputs.

For a supported solvent absent from the preset list, `Other` requires externally supplied H1 and C13 TMS shielding references at the selected level/solvent. Do not invent reference values.

## Inspect and report the result

The standard output is **`QM_DP4+_results.xlsx`** in the NMR directory (`<mode>_DP4+_results.xlsx` generally). Existing filenames receive suffixes rather than being overwritten; inspect the workbook from the current run. Automatic opening can fail independently of export.

| Sheet | Use |
|---|---|
| `results` | Candidate probabilities plus selected theory, Gaussian commands and consistency warnings |
| `tens` | Conformer-weighted, mapped/averaged shieldings |
| `d_sca`, `d_uns` | Scaled and unscaled calculated chemical shifts |
| `e_sca`, `e_uns` | Calculated-minus-experimental shift errors; inspect highlighted `e_sca` cells |
| `parameters` | Statistical distribution parameters and reference shieldings |

In `results`, `Full` combines scaled and unscaled H/C evidence; `H_full` and `C_full` expose nucleus-specific support. `Sca`/`Uns` and their H/C rows distinguish scaling contributions. Rank the candidates by the applicable full probability and inspect disagreement between H and C support, large errors and flagged assignments. With only one nucleus type supplied, report the corresponding nucleus-specific full result; absent-nucleus rows contain no evidence.

Report candidate IDs, probabilities, included nuclei, theory/solvent, energy source, and any excluded files or unresolved warnings. Probabilities are normalized over supplied candidates; high relative support does not prove that the true structure was included. Missing-label errors, malformed workbooks and aborted runs are failures, not negative chemical evidence. Nonfinite probabilities likewise provide no usable ranking. A completion notification alone does not resolve questionable assignments or incomplete conformer coverage.

Cite the [DP4+App method](https://doi.org/10.1021/acs.jnatprod.3c00566) when reporting its use; the [Gibbs extension](https://doi.org/10.1002/mrc.5491) applies when using that functionality.
