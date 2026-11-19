---
name: gaussian-calculate-dp4plus-compatible-giao-shielding
description: Generate Gaussian GIAO shielding logs for a declared DP4+ calculation protocol, including the DP4+App NMR-only example level. Use with prepared optimized conformers and a matched downstream statistical calibration.
---

# Gaussian GIAO shielding from optimized conformers

Use one NMR single-point job per supplied conformer. Inputs must already have optimized geometries, known charge and spin multiplicity, and a consistent atom order across the ensemble. Conformer searching, optimization, minimum verification, population weighting and stereochemical ranking are external steps.

## Declare the DP4+ calculation protocol

For the **DP4+App 2.2.3 NMR-only example**, the [official example manual](https://github.com/Sarotti-Lab/DP4plus-App/blob/66113d495a64de0e0a179ae8a134b4094fb36707/User%20Guides%20and%20Examples/0%20DP4%2B/0%20Example%20Manual-DP4%2B_nmr_only.pdf) specifies:

| Stage | Compatibility requirement |
| --- | --- |
| Supplied geometries | B3LYP/6-31G(d), also written B3LYP/6-31G*. Retain the optimization settings and stationary-point checks from their producer. |
| NMR single points | mPW1PW91/6-31+G(d,p), also written 6-31+G**, with PCM chloroform; the complete route appears below. |
| Downstream statistical analysis | Select the corresponding functional, basis, PCM and CHCl3 parameter set; the example uses `SCF (nmr)` energies for conformer weighting. |
| Atom mapping | Preserve atom identities/order within each candidate and provide the experimental-to-calculated atom correlations downstream. |

This combination establishes the example's intended DP4+App input path. For a different geometry level, NMR level or solvent, first confirm a supported matching statistical calibration, or supply a separately calibrated Custom analysis. Changing a menu selection does not transform incompatible calculations. A general GIAO calculation at another level remains shielding data, without an established DP4+ compatibility claim.

## Obtain and configure Gaussian

Use a licensed **Gaussian 16 Revision C.02** installation. Obtain access through your institution or [Gaussian ordering](https://gaussian.com/orders/), and follow the [official installation entrypoint](https://gaussian.com/techsupport/#install). Match the executable to a platform in the [official platform table](https://gaussian.com/g16/g16_plat.pdf). For example, its C.02 AVX2 Linux binary lists Red Hat Enterprise Linux 8.3; the Apple M-series binary lists macOS 12-15. These instructions use a Bourne-compatible shell on a listed UNIX platform.

Following [Running Gaussian](https://gaussian.com/running/), replace these paths with the installed parent directory and an existing writable scratch directory with adequate free space:

```sh
export g16root=/path/containing-g16
. "$g16root/g16/bsd/g16.profile"
export GAUSS_SCRDIR=/path/to/scratch
```

`g16root` is the directory **above** `g16`, not the executable directory itself. The profile makes `g16` available. Use site-approved resource settings and submission procedures on scheduled systems; the invocation below belongs inside the site's job allocation when required.

## Prepare one input per conformer

| Input | Contract |
| --- | --- |
| `01_001_sample_nmr.coords` | External optimized Cartesian geometry: one `element x y z` line per atom, coordinates in angstroms. No XYZ atom-count or comment header. Preserve atom order. |
| Charge and multiplicity | Two integers, e.g. `0 1` for a neutral singlet; set them for the actual molecule. |
| Theory and solvent | Use the declared calibrated combination above consistently across conformers. A protocol change requires checking downstream calibration compatibility before calculating. |

In the working directory containing the geometry file, construct `01_001_sample_nmr.gjf`. The stem illustrates DP4+App's `n_m_*_nmr` convention: candidate `01`, conformer `001`, annotation `sample`. Use distinct candidate/conformer numbers, with consistent zero-padding, for the full supplied ensemble. This example uses neutral-singlet settings; edit `0 1` as needed. The blank lines separating the route, title and molecule specification, and terminating the geometry, are significant.

```sh
cat > 01_001_sample_nmr.gjf <<'EOF'
%chk=01_001_sample_nmr.chk
# mPW1PW91/6-31+G(d,p) scrf=(PCM,solvent=chloroform) nmr

Conformer 001 shielding

0 1
EOF
cat 01_001_sample_nmr.coords >> 01_001_sample_nmr.gjf
printf '\n\n' >> 01_001_sample_nmr.gjf

g16 < 01_001_sample_nmr.gjf > 01_001_sample_nmr.log
```

Use distinct basenames for each conformer. Shell `>` replaces existing input/log files with the same names, and a reused checkpoint name can overwrite prior state.

`NMR` uses GIAO by default and can be combined with SCRF, as documented in the [NMR keyword reference](https://gaussian.com/nmr/). This route computes shielding at the supplied geometry; it does not optimize it. The PCM chloroform route is also demonstrated in the [DP4+App NMR-only example manual](https://github.com/Sarotti-Lab/DP4plus-App/blob/66113d495a64de0e0a179ae8a134b4094fb36707/User%20Guides%20and%20Examples/0%20DP4%2B/0%20Example%20Manual-DP4%2B_nmr_only.pdf).

## Inspect and hand off results

Read `01_001_sample_nmr.log` in the working directory. Require normal Gaussian termination at the end of this job and a complete GIAO shielding section. Inspect the echoed route, charge, multiplicity and geometry against the intended input. An error termination, truncated log or missing shielding block is a failed/incomplete calculation; inspect the preceding diagnostic before rerunning.

Find the GIAO magnetic shielding section, whose heading contains `Magnetic shielding` and `(ppm)` (wording varies between Gaussian versions). Each atom has an index, element, `Isotropic`, `Anisotropy`, and tensor components `XX` through `ZZ`. Extract **Isotropic shielding in ppm** for the nuclei required downstream, retaining the original atom indices and conformer identity. Check that indices and elements match the supplied atom mapping and that all required atoms are present.

If exporting a table, use fields such as `conformer_id, atom_index, element, isotropic_shielding_ppm, log_path`. This table is an optional handoff format; the full Gaussian log is the primary result. Preserve the `.gjf`, full `.log`, atom map and calculation settings. The named `.chk` is retained for later Gaussian use; unnamed scratch files are normally deleted on success and may remain after failure.

Shielding values are calculated quantities, not experimental chemical shifts. Referencing/scaling, ensemble averaging and comparison with measured shifts require the declared downstream method. Deliver the complete named logs, atom map, optimization-level record and NMR settings so the recipient can verify the selected calibration. An extracted table alone does not substitute for DP4+App's Gaussian logs. Preserve separate conformer-energy outputs when a downstream energy choice requires them; this NMR-only path does not create Gibbs corrections.
