---
name: olex2-refine-small-molecule-crystal-models
description: Use Olex2 to refine a supplied solved small-molecule crystal model against reduced reflections, inspect residual peaks and displacement parameters, and add riding hydrogen atoms.
---

# Refine a solved crystal model with Olex2

## Prepare

Use **Olex2 1.5 Release** with its built-in **olex2.refine** engine and an interactive graphical session. Obtain it from the official [Installation Notes](https://www.olexsys.org/olex2/docs/getting-started/installing-olex2/): on Windows select 1.5 Release in the installer and satisfy its Visual Studio Redistributable prompt. macOS has a 1.5 DMG; Linux has platform ZIP archives launched with the included `start` script. The [release series](https://www.olexsys.org/olex2/docs/getting-started/versions/) updates automatically within 1.5.

Work on a copy of the supplied structure directory: refinement and model edits change the working model, and saving can replace its instruction file.

| Input | Required content |
|---|---|
| `crystal.ins` | Solved model in SHELX instruction syntax, including cell, radiation, symmetry, atom types, coordinates and applicable constraints/restraints. |
| `crystal.hkl` | Matching reduced reflection data, with the same basename and directory as the instruction file. |
| Chemical context | Expected composition and connectivity for assessing atom types and hydrogen placement. |

`crystal` is an example basename. Obtain these inputs from the structure provider; this workflow starts after structure solution. Acquisition, integration, structure solution and absolute-configuration assignment require separate workflows.

## Refine and inspect

1. In Olex2, use **Start > Open** to open `crystal.ins`. Under **Work**, expand the arrow beside **Refine** and explicitly select **olex2.refine** as the refinement program. The controls set cycles and residual peaks; do not assume another previously selected engine has the same behavior.
2. At the **Olex2 command prompt**, enter:

   ```text
   refine
   ```

   Wait for completion and inspect the model. Correct an atom type only when chemistry and density support the change: select it and click the appropriate element button, then run `refine` again. Comparatively small isotropic spheres can indicate an assigned element is too light; large spheres can indicate it is too heavy. Motion and disorder also affect size.
3. Once the non-hydrogen model is sensible, clear the atom selection and enter:

   ```text
   anis
   refine
   ```

   Inspect ellipsoids in comparable chemical environments. Pancake shapes, tetrahedral/non-positive-definite representations or unusually large ellipsoids require investigation of atom assignment, disorder, space group or data quality before proceeding.
4. Add geometrically constrained hydrogens, then refine:

   ```text
   hadd
   refine
   ```

   `hadd` uses riding positions with AFIX instructions. Cycle **Ctrl+H** to inspect hydrogens and hydrogen bonds. Remove extra H atoms by selecting them and pressing **Delete**, then refine. Check for missing H and misplaced OH hydrogens; repeated refinement may improve OH orientation. If adjustment is needed, select the H, choose **Toolbox-Work > Fit**, Shift-drag it toward the supported residual peak, press **Esc**, and refine; AFIX constraints preserve the required geometry. Unresolved placement needs manual crystallographic review.

The [official refinement tutorial](https://www.olexsys.org/olex2/docs/tutorials/sucrose/refining/) illustrates these diagnostics. Its R-factor and peak-height thresholds are specific to sucrose.

## Inspect and retain results

Use **Ctrl+Q** to toggle residual Q peaks. Hidden peaks do not mean zero residual density. Inspect their locations alongside the model and hydrogen positions.

Run `text` to open the full console transcript. Read R1/wR2 and other indicators under **Info > Refinement-Indicators**. In **Work > Refine**, Olex2.refine can stop before the maximum cycle count when converged. A residual shift that fails to approach zero calls for model investigation. Apply automatic weight updating only near completion; if enabled, refine until weights stop changing. See [refinement controls and output access](https://www.olexsys.org/olex2/docs/tasks/tasks/structure-refinement/).

Use full-matrix least squares for final cycles; the method control is **Work > Refine > Refinement-Method**. After inspection, enter:

```text
file
```

The documented [`file` command](https://www.olexsys.org/olex2/docs/reference/commands/file/) saves and reloads the current model as an `.ins` file by default. Retain that saved model with its matching `.hkl`, the refinement transcript and a short record of unresolved diagnostics. Report the actual engine/version and R1/wR2 observed. A low R factor alone does not resolve suspicious geometry, displacement parameters or residual peaks; do not declare an unresolved model final.
