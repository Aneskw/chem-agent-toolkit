---
name: crest-generate-and-export-conformer-ensembles
description: Generate low-energy conformer ensembles from prepared neutral, closed-shell molecular XYZ geometries with CREST/GFN2-xTB, then extract structures for quantum-chemical refinement.
---

# Molecular conformer ensembles with CREST

Use the iMTD-GC search for a supplied molecular structure whose conformational alternatives are needed. Prepare the molecular identity, protonation and stereochemistry externally. This workflow covers neutral closed-shell molecules; constrained transition-state sampling requires a separately specified method.

## Environment and input

Use **CREST 3.0.2** and **xTB 6.8.0** in a Linux Bash environment. Obtain the platform-compatible binaries from the tagged [CREST release](https://github.com/crest-lab/crest/releases/tag/v3.0.2) and [xTB release](https://github.com/grimme-lab/xtb/releases/tag/v6.8.0). Follow the official [CREST setup](https://crest-lab.github.io/crest-docs/page/installation/install_basic.html) and [xTB setup](https://xtb-docs.readthedocs.io/en/latest/setup.html), including executable permissions, PATH, xTB parameter-file paths and stack settings. Both executables must resolve in the calculation environment. Confirm their versions with `crest --version` and `xtb --version`.

Supply one XYZ frame: atom count, a comment line (possibly blank), then that many `Element x y z` records with coordinates in **angstroms**. Include all atoms, including hydrogens. Use a fresh work directory for each molecular species and search condition: these tools read and write files in their current directory.

The representative route uses **GFN2-xTB with GBSA water**. Water is an example solvent choice, not a universal scientific requirement. For another solvent, verify its spelling and support in both tools using the [CREST keyword documentation](https://crest-lab.github.io/crest-docs/page/documentation/keywords.html) and [xTB solvent documentation](https://xtb-docs.readthedocs.io/en/latest/gbsa.html); apply the same method and solvent model during preparation and sampling.

## Prepare the topology reference

CREST uses the initial structure as a reference for topology checks during sorting. Prefer a geometry optimized at the search level. If that geometry is already supplied, copy it directly to `search/struc.xyz` and skip the preoptimization.

Otherwise, replace the input path below with the prepared molecule:

```bash
mkdir conformer-job
cd conformer-job
mkdir preopt search
cp /absolute/path/molecule.xyz preopt/input.xyz
cd preopt
xtb input.xyz --gfn 2 --gbsa h2o --chrg 0 --uhf 0 --opt > xtb.out 2>&1
```

Read `xtb.out` before proceeding. Require the geometry-optimization convergence message; a `NOT_CONVERGED` file or a failure message means the preparation did not converge. Inspect the optimized molecular connectivity and stereochemistry. The original `input.xyz` is preserved; `xtbopt.xyz` contains the optimized coordinates.

## Sample and access the ensemble

After accepting the preoptimization, continue from `preopt/`:

```bash
cp xtbopt.xyz ../search/struc.xyz
cd ../search
crest struc.xyz --imtdgc --gfn2 --gbsa h2o -T 4 > crest.out 2>&1
```

For an already optimized input, enter its prepared `search/` directory and run the same CREST command. Here `--imtdgc` selects the sampling workflow, `--gfn2` selects GFN2-xTB, and `-T 4` requests four CPU threads; adjust the thread count to the allocated resources.

Read `crest.out` for errors and the final `CREST terminated normally.` message. Then access:

| File | Role |
| --- | --- |
| `struc.xyz` | Input topology reference for this search. |
| `crest.out` | Settings, progress, relative-energy/population summary and termination status. |
| `crest_conformers.xyz` | Multi-frame Xmol/XYZ ensemble of distinct conformers. |
| `crest_rotamers.xyz` | Ensemble including conformers and their degenerate rotamers. |

Use the distinct-conformer file for selecting candidate geometries; use the rotamer file when those degenerate forms are relevant. The relative-energy column labeled `Erel/kcal` in the log is in kcal/mol.

## Select structures for refinement

Inspect the ensemble's molecular identity and geometries and select candidates under the downstream study's supplied coverage or energy-window requirements. No universal selection cutoff is imposed here. Use CREST's built-in [`-splitfile` utility](https://github.com/crest-lab/crest/blob/v3.0.2/docs/man/crest.adoc#other-tools-for-standalone-use) to separate the accepted ensemble before selecting downstream structures. From the accepted `search/` directory, create a new export directory:

```bash
mkdir export
cd export
crest -splitfile ../crest_conformers.xyz > split.out 2>&1
```

Inspect `split.out` and the per-structure directories under `export/SPLIT/` (relative to `search/`). Check the exported coordinates against the intended source frames, then hand off the selected structures with their source-frame correspondence and atom order. Keep the original ensemble intact. If preparing individual XYZ files directly, retain the atom-count line, comment line and exactly that number of coordinate records for each frame.

Transfer each selected geometry, with its declared charge 0 and singlet multiplicity 1, into the downstream quantum-chemistry input format. Optimize and rerank at that downstream method before using the results for final energetic comparisons.

CREST energies and populations describe the sampled ensemble at its search model. Normal termination does not establish exhaustive conformational coverage or DFT-level ranking. A single retained conformer can be a valid result; missing or empty ensemble files after an interrupted or failed run are not evidence that the molecule has no alternative conformations.
