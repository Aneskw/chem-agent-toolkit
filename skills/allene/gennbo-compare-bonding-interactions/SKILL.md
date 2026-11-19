---
name: gennbo-compare-bonding-interactions
description: Analyze supplied FILE47 wavefunction archives with standalone GenNBO to compare natural charges, Wiberg bond indices and donor–acceptor interactions across mapped structures.
---

# Compare bonding interactions with standalone GenNBO

Use this workflow when electronic-structure calculations have already supplied valid `.47` archives and an atom mapping between structures. It reanalyzes those wavefunctions without recalculating them. Wavefunction generation and orbital graphics are separate preparation. Deletion-energy calculations and other operations requiring the parent electronic-structure program's energy evaluation or two-electron integrals require an interactive host interface instead.

## Obtain and configure NBO

Use **NBO 7.0.10**, with a valid NBO license. Obtain the appropriate binary distribution through the [official NBO site](https://nbo7.chem.wisc.edu/) and its [Order entry](https://charge.wisc.edu/chemistry/order_nbo7.aspx); licensed users receive download access. Follow the installation instructions included in that distribution. The [NBO 7 manual](https://nbo7.chem.wisc.edu/nboman.pdf), §A.2, describes Windows and Linux/macOS distributions and their supplied GenNBO launchers (`gennbo.bat`, or `gennbo`/`gennbo.sh`). Configure the supplied launcher to resolve its executables as instructed by the distribution, and make it callable as `gennbo` for the commands below. A separately installed host electronic-structure program is unnecessary for this archive-only path.

## Prepare the archives

Keep the original archives and edit working copies with distinct basenames, for example `myjob.47` and `refjob.47`, in a working directory. Record the method, basis, density choice, charge and spin of each supplied calculation; comparisons depend on those inputs. Establish correspondence using chemical atom identities and each archive's `$COORD` order, rather than assuming identical numbering.

| Archive content | Requirement for this workflow |
| --- | --- |
| `$GENNBO ... $END` | Retain the exported atom/basis counts and matrix-format flags. `REUSE` must be absent for this path: it reads a prior FILE48 instead of the archive datalists. |
| `$COORD`, `$BASIS`, `$DENSITY` | Required geometry, basis and density data. Preserve their ordering and contents. |
| `$OVERLAP` | Required for the usual nonorthogonal AO basis. An archive explicitly marked `ORTHO` does not read it. |
| `$FOCK` | Required for `E2PERT`; obtain a complete archive from its producer if missing. Do not synthesize matrix data. |
| `$NBO ... $END` | Controls the requested analysis. Edit this keylist while retaining the wavefunction data. |

Preserve `OPEN` and the exported spin layout: with `OPEN`, alpha matrices precede beta matrices in the density and Fock datalists. Do not add `OPEN` to spin-averaged data. For unusual formats, consult manual §§B.7.3–B.7.8 before modifying anything beyond `$NBO`.

## Run and locate results

In both working archives, set the analysis keylist to:

```text
$NBO BNDIDX E2PERT=0.5 $END
```

This example requests bond-index tables and explicitly sets the donor–acceptor printing threshold to the standard default, **0.5 kcal/mol**. It is an analysis choice, not a criterion for chemical significance. Remove conflicting analysis controls when replacing an existing keylist; retain any intentionally required structure-selection keylists and document their use.

From the directory containing the archives, invoke the configured launcher with the basename **without `.47`**:

```sh
gennbo myjob
gennbo refjob
```

Read `myjob.nbo` and `refjob.nbo` in that directory. This invocation and output naming are documented in the [official FAQ, Q3](https://nbo7.chem.wisc.edu/faq_css.htm). Inspect the new output for errors and the requested sections before extracting values; a missing table is an incomplete analysis, not a numerical zero. If a command is unresolved, fix launcher configuration; if input parsing or matrix errors occur, check the exported archive and its format flags against manual §B.7. Do not interpret partial output as a successful comparison.

## Extract and compare

| Output section | Read and interpret |
| --- | --- |
| `Summary of Natural Population Analysis` | Use `Natural Charge` for each `Atom No`, in units of elementary charge. It is nuclear charge minus the atom's summed natural populations; more negative means greater electron population relative to that nucleus. |
| `Wiberg bond index matrix in the NAO basis` | Use the dimensionless off-diagonal element for the mapped atom pair. `BNDIDX` prints additional indices: do not substitute another table or the totals by atom for this pair value. Wiberg indices are nonnegative and do not distinguish net bonding from antibonding contributions. |
| `SECOND ORDER PERTURBATION THEORY ANALYSIS OF FOCK MATRIX IN NBO BASIS` | Match donor and acceptor by orbital type and mapped atoms. Record `E(2)` in **kcal/mol**, the orbital-energy difference in **a.u.**, and the Fock element in **a.u.** Orbital numbers are local to each analysis. |

Labels such as `LP` (lone pair), `BD` (bond) and `BD*` (antibond) identify orbital character. Inspect the NBO occupancy/composition listing to confirm the intended orbitals when assignments differ between structures; matching NBO serial numbers alone is insufficient.

Deliver a compact comparison with source filename, atom mapping, charge values, selected atom-pair Wiberg indices, and donor/acceptor labels with their `E(2)` values and printing threshold. If reporting differences, define the direction explicitly, for example `myjob minus refjob`.

An absent donor–acceptor row can mean its interaction falls below the printing threshold. Report it as unprinted at that threshold, not zero. If weaker entries matter, lower `E2PERT` consistently in both archives and rerun, retaining the threshold with the results. E(2) is a second-order delocalization estimate associated with the chosen NBO description, not a deletion energy, measured bond strength or reaction barrier. Charge, bond-index and interaction trends support a chemical interpretation; they alone do not prove a mechanism. Manual §§A.3.2–A.3.5 and B.6.5 provide the output definitions.
