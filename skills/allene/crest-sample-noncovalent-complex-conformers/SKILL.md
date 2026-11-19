---
name: crest-sample-noncovalent-complex-conformers
description: Sample conformations and fragment arrangements of a prepared noncovalent complex with CREST/GFN2-xTB, producing XYZ ensembles for subsequent refinement or structural analysis.
---

# Sample noncovalent complexes with CREST

Use CREST's NCI mode when the relative arrangements of weakly bound molecular fragments matter. It applies an ellipsoid wall during biased dynamics to limit dissociation, then removes that wall during geometry optimization. The result is a sampled ensemble at the chosen search level; DFT refinement and thermochemical ranking are separate downstream tasks.

## Environment

Use a Linux terminal with **CREST 3.0.2** and **xTB 6.8.0** available as `crest` and `xtb` on `PATH`.

- Obtain the Ubuntu CREST binary from the [versioned release](https://github.com/crest-lab/crest/releases/tag/v3.0.2), following the official [installation guide](https://crest-lab.github.io/crest-docs/page/installation/install_basic.html).
- Obtain the matching-architecture xTB distribution from its [6.8.0 release](https://github.com/grimme-lab/xtb/releases/tag/v6.8.0). Follow the [setup guide](https://xtb-docs.readthedocs.io/en/latest/setup.html) for executable and parameter-file paths, including `XTBPATH` when needed. Keep the distribution's parameter files available.

Check `crest --version` and `xtb --version` before using the commands below. For large systems, follow the xTB setup guide's stack-memory and OpenMP settings. When using a dynamically linked OpenBLAS CREST build, its installation guide recommends `OPENBLAS_NUM_THREADS=1` to avoid nested-threading problems.

## Prepare the input

Supply `complex.xyz`: one chemically prepared complex containing every fragment and explicit hydrogen atom. XYZ contains an atom count, a comment line, then element symbols and Cartesian coordinates in angstroms. Choose the protonation state, stereochemistry, total charge and spin before sampling; CREST does not construct the intended chemical complex from a name.

| Setting | Meaning |
| --- | --- |
| `--chrg 0` | Total charge; replace for an ionic complex. |
| `--uhf 0` | Number of unpaired electrons, expressed as N_alpha minus N_beta; zero for this closed-shell example. |
| `-T 4` | Four CPU threads for CREST; adjust to allocated resources. |
| Solvation | The example below is gas phase. For a solvated search, select a supported model and solvent consistently in both steps. |

Use a fresh working directory per complex, with `complex.xyz` inside it. Both programs write fixed-name files relative to the current directory; separate directories prevent output and restart-file collisions. Preserve the prepared input independently of generated geometries.

## Preoptimize, then sample

The following neutral, closed-shell example uses GFN2-xTB throughout. Execute each step only after checking the preceding result.

```bash
xtb complex.xyz --gfn 2 --chrg 0 --uhf 0 --opt > xtb.out 2>&1
```

Inspect `xtb.out` for optimization convergence and inspect the optimized `xtbopt.xyz`. Confirm that the intended fragments and chemical structure remain suitable for the search. Preoptimization at the search level matters because CREST uses the reference geometry for topology checks. An `xtbopt.xyz` file alone does not establish convergence: xTB can retain the last geometry after an optimization fails to converge. Resolve that failure before continuing.

```bash
crest xtbopt.xyz --v3 --nci --gfn2 --chrg 0 --uhf 0 -T 4 > crest.out 2>&1
```

`--v3` selects iterative metadynamics sampling; `--nci` applies the noncovalent-complex settings. These flags are supported by CREST 3.0.2. For a water-GBSA calculation, for example, append `--gbsa h2o` to **both** commands; other solvents and models require their documented identifiers. This is a modeling choice, not an automatic consequence of supplying a complex.

## Retrieve and assess the ensemble

Check `crest.out` for `CREST terminated normally.` and the final ensemble summary. Then inspect the output files:

```bash
ls -lh crest_conformers.xyz crest_rotamers.xyz
head -n 8 crest_conformers.xyz
```

| File | Use |
| --- | --- |
| `crest_conformers.xyz` | Multi-structure Xmol/XYZ ensemble of distinct conformers for further calculations. |
| `crest_rotamers.xyz` | Ensemble including conformers and their degenerate rotamers. |
| `crest.out` | Search settings, progress, energy/population summary and completion status. |
| `xtbopt.log` | Preoptimization trajectory with energies in XYZ comment lines, useful when diagnosing an unsuitable starting geometry. |

Each XYZ structure repeats the atom-count, comment and coordinate block. Retain the complete ensemble and inspect representative structures with an XYZ-capable molecular viewer before handing conformers to refinement or geometry analysis. Check the intended fragment composition, connectivity and stereochemistry rather than inferring these from successful termination.

The default search energy window is 6 kcal/mol. It filters structures relative to the lowest conformer found at the search level; it does not establish exhaustive sampling or a global minimum. Search-level energies and reported populations are model-dependent. They do not establish Gibbs free-energy rankings, binding affinities or experimental selectivity without the appropriate downstream calculations.

Missing or empty ensemble files, abnormal termination, or an unfinished log require diagnosis rather than interpretation as absence of conformers. xTB severe errors return a nonzero status; its explicit `ANCopt failed to converge the optimization` warning also requires attention even if a geometry was written. For NCI confinement details or changes to the wall size, consult the official [NCI example](https://crest-lab.github.io/crest-docs/page/examples/example_3.html).
