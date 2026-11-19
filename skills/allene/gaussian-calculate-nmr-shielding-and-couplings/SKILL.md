---
name: gaussian-calculate-nmr-shielding-and-couplings
description: Calculate atom-resolved NMR shielding tensors and optional spin-spin couplings with Gaussian 16 from an optimized molecular structure and chosen model chemistry.
---

# Gaussian NMR shieldings and spin-spin couplings

Use this workflow for calculated magnetic properties. Start with an adequately optimized structure; geometry optimization, conformer averaging, reference-based chemical shifts, spectral assignment and experimental spectrum processing are separate tasks.

## Environment

Use licensed **Gaussian 16 Rev. C.02**, with its AMD/Intel x86_64 AVX2 Linux binary on a listed system, such as RHEL 8.3. Obtain it through [Gaussian orders](https://gaussian.com/orders/) and follow the official [installation entry](https://gaussian.com/techsupport#install) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf). This single-machine workflow needs no cluster setup.

In a Bourne-compatible shell, initialize the installed environment unless the site already does so:

```sh
export g16root=/actual/parent/of/g16
. "$g16root/g16/bsd/g16.profile"
export GAUSS_SCRDIR=/actual/writable/scratch
```

Replace both locations with existing site paths. `g16root` is the directory containing `g16`, and scratch must have sufficient free space. The [execution guide](https://gaussian.com/running/) documents these settings and job resource controls.

## Prepare the input

Supply `optimized-spec.txt` in the job directory, containing the molecular specification only:

- First line: integer total charge and spin multiplicity, e.g. `0 1` for a neutral singlet.
- Remaining lines: one atom per line as `Element x y z`, with Cartesian coordinates in angstroms, preserving the optimized structure's atom order. Do not include an XYZ atom-count or comment header.
- End the final atom line with a newline. Keep an atom-number-to-identity map for reporting; Gaussian output atom numbers are 1-based.

Choose a method/basis applicable to all elements and the requested property. The example uses **B3LYP/6-31G(d)** and **1 GB** as illustrative choices; replace them with the supplied model chemistry and suitable available memory. Shieldings support HF, DFT and MP2; `SpinSpin` supports **HF or DFT only**. GIAO is the default shielding method and is explicit below. See the official [NMR interface](https://gaussian.com/nmr/) for method availability and options.

From the directory containing `optimized-spec.txt`, assemble a shielding job:

```sh
cat > nmr.gjf <<'EOF'
%Chk=nmr.chk
%Mem=1GB
# B3LYP/6-31G(d) NMR=GIAO

NMR properties of supplied optimized geometry

EOF
cat optimized-spec.txt >> nmr.gjf
printf '\n' >> nmr.gjf
```

The blank lines separate the route, title and molecular specification and terminate the geometry. For shieldings **and** couplings, change the route option to `NMR=(GIAO,SpinSpin)` before running. This adds a substantial computation: Gaussian estimates roughly twice the cost of vibrational frequencies alone. The simple example uses default isotopes and no solvent model; retain any required environmental model in the route and record it with the result.

### Optional selective couplings

For a restricted atom list use `NMR=(GIAO,SpinSpin,ReadAtoms)` and append a separate section **after the geometry's terminating blank line**:

```text
atoms=1-4 notatoms=3

```

This illustrative list selects atoms 1, 2 and 4; adapt indices to the actual molecule. Terminate the selection section with a blank line. The list starts empty. `atoms=` adds atom numbers, inclusive ranges or element types; `notatoms=` removes them, and keywords apply in succession. An empty selection is not a request for all atoms.

## Run and inspect

```sh
g16 < nmr.gjf > nmr.log
```

These relative paths resolve in the current job directory. Redirection replaces an existing `nmr.log`; use distinct basenames for separate calculations and checkpoints. `%Chk=nmr.chk` retains the checkpoint in this directory. Scratch files are normally deleted after success and may remain after abnormal termination.

Confirm successful completion at the end of `nmr.log` and inspect diagnostics if the job stops early. Missing requested property blocks are incomplete results, not zero shieldings or couplings. Read the full blocks, rather than only matching their headings:

| Output in `nmr.log` | Interpretation |
| --- | --- |
| `Magnetic shielding (ppm):` | For each numbered atom and element, collect `Isotropic`, `Anisotropy` and all nine labeled components `XX`, `XY`, `XZ`, `YX`, `YY`, `YZ`, `ZX`, `ZY`, `ZZ`, in ppm. Preserve labels and the geometry/orientation associated with the calculation. |
| `Total nuclear spin-spin coupling K (Hz):` | Isotope-independent isotropic pair coupling matrix, with the heading and units as printed by Gaussian. |
| `Total nuclear spin-spin coupling J (Hz):` | Isotopic pair couplings in Hz, using the job's explicitly specified or default isotopes. |

K and J tables are lower triangular and may span column blocks. Match row and column atom numbers using each block's header; retain signs. For machine-readable exports, interpret Fortran `D` exponents as scientific notation. Individual coupling contributions precede the total matrices; do not substitute one contribution for the total.

Return the input/log/checkpoint paths, model chemistry, geometry identity and atom map, isotope assumptions, atom-indexed shielding values and requested pair couplings. Label the values as **calculated shieldings**, not experimental chemical shifts. A chemical shift requires a separate reference/calibration workflow; these predictions alone do not establish a spectral assignment.
