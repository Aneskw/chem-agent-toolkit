---
name: crystalexplorer-analyze-hirshfeld-contact-fingerprints
description: Generate CrystalExplorer Hirshfeld surfaces and element-filtered contact fingerprints from a validated CIF to inspect crystal packing and surface-area contributions.
---

# Hirshfeld surfaces and contact fingerprints with CrystalExplorer

## Prepare the application and structure

Use the desktop GUI from [CrystalExplorer release v25.8](https://github.com/peterspackman/crystalexplorer/releases/tag/v25.8). Obtain the prebuilt package for your platform; the Windows x86_64 installer under that release is named `CrystalExplorer-25.09-windows-x86_64.exe`. Install and launch the application. This workflow requires graphical interaction.

Start with an externally supplied, validated `structure.cif`, the identity of the crystal/data block, and the complete molecule to analyze. Structure solution, refinement, and resolving an ambiguous molecular selection are upstream inputs.

The normal path generates a molecular Hirshfeld surface, maps `d_norm`, displays full and element-filtered fingerprints, and saves plots plus a recorded contact-percentage table. These results describe crystal contacts; percentages are surface-area fractions, not interaction energies or biological affinity.

## Generate the surface

For example, analyze O···H/H···O contacts in a molecule containing oxygen and hydrogen:

1. Choose **File → Open** and load `structure.cif`. Opening a CIF adds its crystal structures to the project; select the intended crystal in the top-right selection box.
2. If the displayed asymmetric unit contains incomplete fragments, use **Complete Fragments** on the main toolbar. Clear unrelated selections, then double left-click an atom or bond of the target molecule. Check that the selected fragment is the complete intended molecule.
3. Open **Surface Generation** from the toolbar and use:

   | Control | Setting |
   | --- | --- |
   | Surface | Hirshfeld |
   | Resolution | High |
   | Property | None; map the built-in property after generation |

   High corresponds to a 0.2 Å surface separation in this release. Keep the Hirshfeld isovalue at its default 0.5. Confirm with **OK**. Fingerprints require high-resolution Hirshfeld surfaces; lower-resolution plots can be meaningless.
4. Select the generated surface in the surface list. In the Surface Controller's **Options**, choose **d_norm** as the mapped property. Record the displayed colour range when preparing comparisons.

The [surface-generation guide](https://crystalexplorer.net/docs/quick-start/generate-surfaces/) explains surface selection and the controller. Hirshfeld contact-distance properties are built in; this path does not require a separate quantum-chemical wavefunction calculation.

## Display, filter and export

With that surface selected, click **Display Fingerprint Plot** in the bottom-right Surface Controller. The x axis is `di` and the y axis is `de`: distances from the surface to the nearest internal and external nuclei, respectively.

1. Set **Filter → None** to inspect the full fingerprint. Use **Save As...** to save `structure-all.eps`; EPS export prompts for an optional title. PNG is also supported.
2. Set **Filter → By Element**, then:

   | Control | Example setting and meaning |
   | --- | --- |
   | Inside | O: the closest atom inside the molecular surface |
   | Outside | H: the closest atom outside |
   | Include reciprocal contacts | Check to include both O···H and H···O; uncheck for O-inside/H-outside only |
   | Surface area included | Read the percentage for the current filter; displayed to one decimal place |

3. Inspect the filtered fingerprint and corresponding surface regions. Click a fingerprint feature to display highlight cones on its associated surface points. Save `structure-OH-reciprocal.eps` with the reciprocal setting recorded.
4. Repeat with other requested element pairs, retaining the same molecule and resolution. For H···H, treat the result as one contact class; do not double it.
5. Open **Show Crystal Information → Surface** for the selected surface and locate **Fingerprint Breakdown**. Rows identify inside elements and columns identify outside elements. Record the needed table entries. For a combined O···H/H···O value, sum the O-row/H-column and H-row/O-column entries once each. The table and filter readout use separate sampling implementations; retain their labels and displayed precision rather than assuming exact equality.

Deliver the saved plots and a compact record of CIF/crystal identity, selected molecule, release, resolution, colour range, inside/outside elements, reciprocal setting, and percentages. Suggested filenames are example choices. The [GUI workshop](https://crystalexplorer.net/docs/workshop/getting-started/) provides the selection, fingerprint and information-panel controls.

## Interpret and check results

With the standard d_norm colour scheme, red marks contacts shorter than the sum of van der Waals radii, white marks contacts near that sum, and blue marks longer contacts. d_norm is dimensionless. See [Surface Properties](https://crystalexplorer.net/docs/manual/isosurfaces/properties/) for the definitions. A large contact percentage describes prevalence over the surface, not bond strength.

An empty filtered contribution can mean that no sampled contacts match the selected element direction; check the element pair and reciprocal setting before interpreting it. If the whole fingerprint is empty or the breakdown is absent, verify that a generated Hirshfeld surface is selected and has internal/external distance properties. Regenerate at High if necessary. A missing breakdown is not a zero measurement.

Use a supported lowercase extension such as `.eps` or `.png` when exporting and confirm the file exists at the chosen path. PNG save failures display **Unable to save image**. Expand or translate the fingerprint plot range when long-distance contacts lie outside the visible range.
