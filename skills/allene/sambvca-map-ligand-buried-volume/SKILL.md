---
name: sambvca-map-ligand-buried-volume
description: Calculate and compare ligand buried volumes, quadrant occupancies and topographic steric maps from prepared molecular coordinates using the SambVca 2.1 web interface.
---

# Map a catalytic pocket with SambVca

## Service and inputs

Use the hosted [SambVca 2.1 interface](https://www.aocdweb.com/OMtools/sambvca2.1/index.html) in a browser with its interactive JSmol viewer. No local installation is needed. The [official help](https://www.aocdweb.com/OMtools/sambvca2.1/help/help.html) documents the form and result downloads.

Supply a prepared molecular structure in XYZ, PDB, CIF or MOL format. For XYZ, use an atom-count line, a title line, then one element symbol and Cartesian x/y/z coordinates per atom; prepare coordinates in angstroms. Geometry optimization and transition-state generation are external inputs to this workflow.

Before opening the form, identify the metal, the ligand or other atom subset whose occupancy is being measured, and chemically corresponding atoms for orientation across structures. Atom deletion in the web viewer changes the analyzed subset; keep the original coordinate file separately. A comparison is meaningful only with consistent subset definitions and calculation settings.

## Representative run: a Cu-bound bidentate phosphine

Start with an externally supplied `cu-binap.xyz` containing the Cu complex. Identify Cu and the two ligand phosphorus atoms, here called P_A and P_B; these labels refer to atoms in that supplied structure, not literal form entries. This example measures the phosphine ligand's occupancy around Cu.

1. **Load file:** upload `cu-binap.xyz` and identify the atoms in the viewer.
2. **Select the atoms coordinated to the center of the sphere:** select Cu itself. Set **Distance of the coordination point from the center of the sphere** to **0.0 Å** so the sphere stays centered at its coordinate.
3. **Select the atoms for z axis definition:** select P_A and P_B and choose **Z-negative**. Multiple selected atoms define their geometric average. This puts the ligand-facing direction on negative Z. If using atoms outside the analyzed ligand instead, choose Z-positive as appropriate.
4. **Select the atoms for xz-plane definition:** choose P_A, provided it is not on the center–Z line. Keep the same chemically corresponding choice in comparison structures; changing this plane rotates the quadrant assignment.
5. **Select the atoms to be deleted:** remove Cu and every atom outside the ligand being measured, then apply **delete selected atoms**. Define the center and axes before deleting their reference atoms. Retain additional groups only when their occupancy is intentionally part of the stated analysis.
6. **Check the chosen orientation / Preview:** verify the retained ligand and its placement toward negative Z. Use the documented INVERT MOLECULE or INVERT DUMMY controls if needed. Preview also exposes the reoriented coordinates. Resolve an unintended orientation or atom subset before submission.

For an isolated ligand without a metal coordinate, select its coordinating donor atom(s) and supply the intended metal–coordination-point distance in Å instead of 0.0. That distance is an external structural assumption, for example from an experimental structure, and must accompany the result.

## Calculation and submission

Set these fields explicitly for the example, then click **SUBMIT** to calculate and open the results page.

| Field | Example value | Meaning |
| --- | --- | --- |
| Atomic radii | Bondi radii scaled by 1.17 | Documented default; unscaled Bondi radii are also offered |
| Sphere radius | 3.5 Å | Spatial region being measured; the help's suggested radius |
| Coordination-point distance | 0.0 Å | Uses the selected Cu coordinate as the center |
| Mesh spacing for numerical integration | 0.10 Å | Documented default cubic integration spacing |
| Include H atoms | Unchecked | Hydrogens are normally omitted; enable deliberately for an analysis that includes them |

A 4.5 Å sphere is an alternative for a larger pocket. Run it as a separate calculation and label it by radius; percentages from different sphere sizes describe different regions. For a pair of structures, repeat the same atom-selection and orientation convention and all parameter values for both.

## Results to retain and interpret

On successful completion the results page shows the analyzed structure in JSmol, tables of total **%V_Bur** and quadrant **%V_b**, and a steric map with a color bar. Use its download buttons to save:

- the steric map as PNG and/or PS;
- the Cartesian coordinates reoriented according to the chosen axes;
- the Cartesian grid points defining the steric-map surface.

Save each run under a distinct local stem, for example `cu-binap-r3p5`, and record the version label, input filename, retained/deleted atoms, center and axis selections, radii set, sphere radius, distance, mesh spacing and hydrogen setting alongside its table values. Downloaded coordinates are transformed output; retain them separately from the input. The stem is a local naming convention, not a server filename.

**Buried volume** is the percentage of sphere volume occupied by the selected atoms' van der Waals volumes. Greater total %V_Bur means less free volume within that particular sphere. Derive total free volume as **%V_free = 100 − %V_Bur**. Keep the service's quadrant labels and values with the saved orientation; a quadrant is defined by those axes, not an intrinsic region of the molecule.

**Map contours** report the first occupied surface height along Z at each X/Y position, in Å. In the computational protocol, positive heights mean protrusion into the positive-Z, reacting-group side. Read the color bar and oriented structure together; map color alone does not give an interaction energy. These are geometric descriptors, not a computed activation barrier or a prediction of stereoselectivity.

A page with no calculated tables or map is an incomplete run, not evidence of zero buried volume. If preview shows the wrong subset or orientation, correct those selections and rerun before comparing results. Zero free or buried volume, if actually returned in a completed table, is a geometric result under the chosen settings and should first be checked against the retained atoms and sphere placement.

For a free ligand requiring an artificial coordination direction, the official help's **ADD DUMMY** path uses three atoms P1, P2 and P3 to define a plane, with P1 the coordinating atom. Inspect the direction in preview and use **INVERT DUMMY** when needed; retain the externally justified donor-to-center distance with the result.
