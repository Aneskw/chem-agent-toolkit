---
name: autodock-vina-dock-prepared-ligands
description: Dock chemically checked ligand PDBQT files into a rigid receptor with AutoDock Vina, configure the search box, and interpret ranked poses and affinity scores.
---

# Dock prepared ligands with AutoDock Vina

## Setup and input handoff

Use **AutoDock Vina 1.2.7** with Vina scoring. Obtain the executable matching your OS and architecture from the [official release assets](https://github.com/forlilab/AutoDock-Vina/releases/tag/v1.2.7). Assets include `vina_1.2.7_win.exe` and Linux/macOS x86_64 and aarch64 binaries. On Unix, grant execute permission to the downloaded binary. The commands below assume it is available on PATH as `vina`; otherwise use its full path. In PowerShell, invoke a quoted executable path with `&`.

Require these external inputs in a working directory:

| Input | Contract |
| --- | --- |
| `receptor.pdbqt` | Chemically checked, prepared rigid receptor, with appropriate protonation and atom types. |
| `ligand.pdbqt` | One prepared 3D ligand, with checked protonation, atom types and rotatable-bond definition. |
| `box.txt` | Justified binding-site box in the receptor's coordinate frame: center coordinates and full side lengths in angstroms. |

Preparation is a handoff. If you only have PDB/SDF structures, obtain checked PDBQT files first; the [official preparation tutorial](https://github.com/forlilab/AutoDock-Vina/blob/v1.2.7/docs/source/docking_basic.rst) describes Meeko preparation. Renaming a structure file does not prepare it. This workflow keeps the receptor rigid and uses no `--flex` input. Vina computes its affinity maps internally; AutoGrid maps are unnecessary here.

## Configure and dock

Create `box.txt` with the following six keys. These numbers are the official **1IEP tutorial example**, usable only with the corresponding coordinates. Replace all six values with the justified box for your target:

```text
center_x = 15.190
center_y = 53.903
center_z = 16.917
size_x = 20.0
size_y = 20.0
size_z = 20.0
```

Sizes are angstroms, not AutoDock4 grid-point counts. Cover the binding region and room for the ligand; enlarging the box makes the search harder.

From the directory containing the three inputs, run:

```sh
vina --receptor receptor.pdbqt --ligand ligand.pdbqt --config box.txt --scoring vina --exhaustiveness 32 --seed 12345 --out poses.pdbqt > docking.log 2>&1
```

Relative paths resolve from this working directory. Choose fresh output names for each run and ligand. Read `docking.log` after completion; it captures terminal output and errors. The receptor and ligand files remain inputs; `poses.pdbqt` contains predicted ligand poses.

| Control | Meaning |
| --- | --- |
| `--exhaustiveness 32` | Example search effort from the tutorial; default is 8. Increase effort for harder searches without treating this as a guarantee of accuracy. |
| `--seed 12345` | Illustrative explicit random seed. Preserve the seed together with all inputs, version and parameters for repeat comparisons. |
| `--num_modes` | Maximum output modes; default 9, not a promise of nine poses. |
| `--energy_range` | Output window above the best score; default 3 kcal/mol. |

For several ligands, repeat this single-ligand invocation with distinct output/log paths. Keep receptor, box, scoring function and search settings consistent across comparisons; preserve the actual command and inputs with each result.

## Read and report the results

Read the `mode | affinity | dist from best mode` table in `docking.log` alongside the models in `poses.pdbqt`. Report the ligand identity, mode number, affinity in **kcal/mol**, scoring function, box and search settings. More negative Vina scores rank as more favorable within this scoring model; they are predictions, not measured binding affinities or proof of inhibition. AutoDock4 and Vina scores are not directly comparable.

The `rmsd l.b.` and `rmsd u.b.` columns give lower and upper RMSD bounds relative to Vina's best mode. The best mode's zero distance is expected and does not establish redocking accuracy. Validation against a crystallographic ligand needs a separate, explicitly supplied experimental-pose comparison; do not substitute the terminal RMSD columns for it. Input protonation matters even though output hydrogen coordinates are arbitrary under Vina's united-atom scoring.

Fewer modes can be normal because the search finds fewer distinct poses or the energy window filters them. The warning `Could not find any poses. No poses were written.` indicates no pose output was produced. A missing or empty pose output is not evidence of nonbinding. Inspect the log and process exit status: configuration/PDBQT parse errors, missing parameters, and file-open errors require correction before interpreting results. If a search completes but poses are implausible, revisit the prepared structures and box, then consider increased exhaustiveness or a recorded alternative seed. Docking and scoring remain approximate.
