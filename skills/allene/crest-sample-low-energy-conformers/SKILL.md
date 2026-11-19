---
name: crest-sample-low-energy-conformers
description: Sample conformers through the CREST external-xTB command-line interface, including GFN2/GBSA solvent sampling, from a prepared neutral closed-shell XYZ geometry for DFT refinement.
---

# Sample conformers with CREST

Use the iMTD-GC search to generate candidate geometries for subsequent DFT optimization. This workflow covers ordinary conformational sampling of a prepared molecule; preserving a transition-state geometry requires a separately specified constrained workflow.

## Environment and input

Use **CREST 3.0.2** and **xTB 6.8.0** in a Linux/UNIX command-line environment.

- Obtain a stable CREST binary from the [3.0.2 release](https://github.com/crest-lab/crest/releases/tag/v3.0.2), following the [official installation guide](https://crest-lab.github.io/crest-docs/page/installation/install_basic.html). Use the versioned release assets rather than the continuous-development download.
- Obtain xTB from its [6.8.0 release](https://github.com/grimme-lab/xtb/releases/tag/v6.8.0) and follow its [setup instructions](https://xtb-docs.readthedocs.io/en/latest/setup.html). Make both `crest` and `xtb` available on `PATH`; configure `XTBPATH` for the distribution's parameter/configuration files as described there.
- Check the selected executables with `crest --version` and `xtb --version`. For production calculations, the xTB setup guide recommends `ulimit -s unlimited` and an appropriate `OMP_STACKSIZE` (its example uses `4G`).

Supply `struc.xyz`: one molecule with its intended protonation and stereochemistry, including hydrogens. Use standard XYZ layout: atom count, comment line, then that many element-symbol and x/y/z rows, with coordinates in angstroms. This normal path assumes charge zero and a closed shell.

Prefer a starting geometry already optimized at the search level, GFN2-xTB/GBSA(water). CREST uses the input as a topology reference during sorting, including coordination-number checks. Preparing that geometry is an input handoff.

## Run the search

Copy the prepared input into a fresh calculation directory and run there; CREST creates its working files and results in that directory. The following example uses GBSA water and four CPU threads:

```bash
# Run in the directory containing struc.xyz.
crest struc.xyz --imtdgc --gfn2 --gbsa h2o -T 4 > crest.out
```

| Setting | Meaning |
| --- | --- |
| `--imtdgc` | Iterative metadynamics and genetic-crossing conformer search |
| `--gfn2` | GFN2-xTB search energy model |
| `--gbsa h2o` | GBSA implicit water solvent |
| `-T 4` | Four CPU threads; adapt to the available allocation |
| `> crest.out` | Save standard output; terminal diagnostics may appear separately |

Water is an example choice: select the solvent model appropriate to the task and keep it consistent with input preparation. GBSA and ALPB are distinct models; changing to `--alpb` changes the calculation. Consult the [command documentation](https://crest-lab.github.io/crest-docs/page/documentation/keywords.html) for solvent and sampling options.

## Inspect results and hand off geometries

Check `crest.out` for final ensemble information and `CREST terminated normally.` before using the results.

| Result in the calculation directory | Use |
| --- | --- |
| `crest_conformers.xyz` | Multi-frame Xmol/XYZ ensemble of conformers; primary geometry handoff |
| `crest_rotamers.xyz` | Ensemble including conformers and their degenerate rotamers |
| `crest.out` | Settings, search progress, final relative-energy/population information and termination status |

Inspect the ensemble with a multi-frame XYZ reader. Use the final table's `Erel/kcal` values to compare retained structures at the search level. The conformational-search energy-window default is 6 kcal/mol; it filters the sampled ensemble and does not establish that every possible conformer has been found.

Extract selected complete XYZ frames for separate DFT optimizations, preserving atom identities and order. Retain the search settings with the geometries. Search-level rankings and populations describe this model and sampled ensemble; reassess energies after DFT refinement rather than treating them as final DFT results.

A single retained conformer can be a valid result. Missing or empty ensemble files, or absence of normal termination, require inspection of the log and terminal diagnostics before handoff. Do not treat partial files as a completed search.

The [official sampling example](https://crest-lab.github.io/crest-docs/page/examples/example_1.html) documents this command form and the ensemble-file distinction.
