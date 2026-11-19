---
name: orca-analyze-natural-bonding
description: Run ORCA with licensed NBO to obtain natural atomic charges, bond-orbital occupancies and NAO-based Wiberg bond indices from a prepared molecular calculation.
---

# Natural bonding analysis through ORCA and NBO

## Prepare the interface and calculation

Use **ORCA 6.1.1** and **NBO 7.0.10**. Obtain ORCA from the [official downloads portal](https://www.faccts.de/customer/) or [ORCA Forum](https://orcaforum.kofo.mpg.de/app.php/portal) (registration required); follow the [ORCA installation instructions](https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html). Obtain licensed NBO binaries through the official [NBO Products](https://nbo7.chem.wisc.edu/products_css.htm) and [Order](https://charge.wisc.edu/chemistry/order_nbo7.aspx) pages, then follow the instructions supplied with that distribution.

ORCA requires the **i8 integer build** of the NBO executable. Set `NBOEXE` to the full path of `nbo7.i8.exe`, not the GenNBO driver and not the i4 executable. The distributed filename ends in `.exe` on Linux too. Ensure ORCA executables are discoverable through `PATH`.

Start with a prepared ORCA input: molecular coordinates, total charge, spin multiplicity, and an explicitly chosen electronic-structure model and basis. Keep those scientific choices when adding the analysis. Use a separate working directory for each calculation: output redirection replaces the named log, and the archive uses the generic name `FILE.47`.

## Request and run the analysis

Add this block to the prepared single-point input:

```text
%nbo
  NBOKEYLIST = "$NBO NBO NPA BNDIDX AONBO=C ARCHIVE $END"
end
```

| Keyword | Requested result |
| --- | --- |
| `NPA` | Natural populations and atomic charges |
| `NBO` | Bond orbitals, occupancies and hybrid compositions |
| `BNDIDX` | Wiberg indices in the NAO basis, plus related index tables |
| `AONBO=C` | AO-to-NBO transformation checkpoint used for orbital output |
| `ARCHIVE` | Text wavefunction archive for later GenNBO analysis |

The shorthand `! NBO` requests `NBO NPA AONBO=C ARCHIVE`; it does **not** include `BNDIDX`. Use the explicit block above when Wiberg indices are required.

For example, save this complete formaldehyde input as `bonding.inp`. RHF/SVP is an illustrative model from the ORCA interface example, not a prescribed model for other molecules. Coordinates are in angstroms; `0 1` specifies a neutral singlet.

```text
! RHF SVP
%nbo
  NBOKEYLIST = "$NBO NBO NPA BNDIDX AONBO=C ARCHIVE $END"
end
* xyz 0 1
C   0.000000   0.000000   0.000000
O   1.200000   0.000000   0.000000
H  -0.550000   0.952628   0.000000
H  -0.550000  -0.952628  -0.000000
*
```

Run from the directory containing the input. Substitute the actual installation paths.

Linux/macOS shell:

```bash
export NBOEXE="/absolute/path/to/nbo7.i8.exe"
/absolute/path/to/orca bonding.inp > bonding.out 2>&1
```

Windows Command Prompt (`cmd.exe`):

```bat
set "NBOEXE=C:\NBO7\nbo7.i8.exe"
"C:\ORCA_6.1.1\orca.exe" bonding.inp > bonding.out 2>&1
```

## Inspect and retain results

Open `bonding.out` and locate the NBO banner and these sections:

| Section | Read and report |
| --- | --- |
| `Summary of Natural Population Analysis` | Atom number, element and natural charge in units of elementary charge; populations are electron counts. Match the printed atom labels to the input order, starting at 1. |
| `NATURAL BOND ORBITAL ANALYSIS` | Occupancy in electrons, orbital label, atom assignments and hybrid composition. `BD` = bond, `BD*` = antibond, `LP` = lone pair, `CR` = core, `RY` = Rydberg. |
| `Wiberg bond index matrix in the NAO basis` | Dimensionless pair indices using the printed row/column atom numbers; distinguish this matrix from other `BNDIDX` tables and the totals by atom. |

Check SCF convergence, normal ORCA termination and presence of all requested analysis sections before reporting completion. An ORCA log without NBO output is insufficient. If NBO fails to start, check `NBOEXE`, executable access and i8 compatibility. Missing Wiberg output calls for checking the explicit `BNDIDX` request.

Retain `bonding.inp`, `bonding.out`, the generated `bonding.nbo` orbital file (ORCA GBW format), and `FILE.47`. The orbital file supports later visualization with ORCA's `orca_plot`; the archive retains the wavefunction data for additional NBO analysis. ORCA leaves the potentially large archive for manual deletion.

Wiberg indices are nonnegative density-based descriptors: they do not distinguish net bonding from antibonding character and are not NRT natural bond orders. Interpret them alongside orbital occupancies and the selected wavefunction. Review poor Lewis-structure localization or substantial non-Lewis populations before assigning unusual bonding; do not force a preferred structure by silently altering search settings.

For post-HF inputs, consult [ORCA's NBO density instructions](https://www.faccts.de/docs/orca/6.1/manual/contents/spectroscopyproperties/nbo.html#nbo-for-post-hf-densities): density generation may need an explicit request, and the output may contain both SCF and correlated-density analyses. Identify which density each reported result describes.

## Reuse the archive when needed

Copy the archive into a fresh working directory as `bonding-archive.47` and edit its `$NBO ... $END` keyword list while preserving the wavefunction data. Configure the NBO distribution's GenNBO launcher (`gennbo`/`gennbo.sh` on Unix, `gennbo.bat` on Windows) according to its installation instructions. With that launcher callable as `gennbo`, pass the basename **without `.47`**, following the [NBO vendor FAQ, Q3](https://nbo7.chem.wisc.edu/faq_css.htm):

```text
gennbo bonding-archive
```

Inspect the newly generated `bonding-archive.nbo` for completion and the requested sections. The ORCA manual also shows stdin/stdout redirection; use that form only with an executable or wrapper documented to accept an archive on stdin. It is not the basename launcher's input contract. `NBOEXE` for ORCA and the standalone GenNBO launcher serve different roles.

GenNBO can vary the analysis without recomputing the wavefunction, but cannot perform deletion energetics or other operations requiring energy evaluation or the parent program's two-electron integrals. Consult the [NBO 7 manual](https://nbo7.chem.wisc.edu/nboman.pdf), §B.6.5 for index definitions and §B.7 for archive options.
