---
name: spartan-screen-constrained-conformers
description: Generate and inspect Spartan MMFF conformer ensembles while holding selected interatomic distances fixed, for screening constructed reaction complexes before quantum refinement.
---

# Constrained conformer screening in Spartan

## Prepare the complex

Use licensed **Spartan '26 v1.1.0 for Windows**. Obtain the [official installer](https://downloads-s3.wavefun.com/windows/Spartan26Installer110.exe) from Wavefunction's [version/download page](https://www.wavefun.com/spartan-version-history), and complete licensed setup. The Help menu's **License Utility** exposes individual/network licensing and **About Spartan '26** identifies the installed release. This workflow requires access to the graphical interface.

Start with one constructed molecular complex and a chemically justified constraint specification:

| Input | Required detail |
|---|---|
| Geometry | Native `.spartan` document; alternatively import a supported 3D format such as `.mol2` using **File → Open**. Verify connectivity, hydrogens and stereochemistry after import. |
| Atom pairs | Unambiguous labels for each pair, for example the forming B–O and C–C pairs in a reaction complex. Pairs need not be bonded. |
| Target distances | Supplied values in Å, or an explicit decision to retain the starting geometry's current distances. No universal forming-bond distances are implied. |

Work on a saved copy, for example `complex-screen.spartan`, because Conformer Distribution replaces the original document's displayed geometry with the lowest-energy conformer. Keep all fragments of the complex in the same molecular entry.

## Set constraints and submit

For the example `complex-screen`, retain the current B–O and C–C distances, or substitute the supplied targets:

1. Choose **Geometry → Constrain Distance**. Click the two atoms defining B–O (or its bond). Click the lock control to turn the constraint on. Retain the displayed current distance, or type the supplied target into the constraint-distance box. Repeat for C–C and any other required pair. Active constraints have magenta markers. A target constraint value can differ from the actual current distance; start reasonably near the requested geometry.
2. Open **Setup → Calculations…** and set:

   | Control | Setting |
   |---|---|
   | Calculate | **Conformer Distribution** |
   | Method | **Molecular Mechanics** |
   | Force field | **MMFF** |
   | Subject to | Check **Constraints** |

   Explicitly choose ordinary MMFF. **Corrected MMFF** adds a neural network and changes the model; its documented element coverage excludes boron. Drawing or locking constraints alone does **not** enable them for a calculation. **Frozen Atoms** fixes Cartesian positions and is a different operation.
3. Record the search settings used. Spartan automatically chooses systematic or Monte Carlo searching from the conformational degrees of freedom. **Maximum Conformers Examined** caps exploration; a cap below the estimated conformer count forces Monte Carlo. The manual's MMFF tutorial states that, by default, only conformers within **40 kJ/mol** of the lowest-energy conformer are retained; consult **Help → Conformations and Energy Profiles** if changing retention settings. These controls affect which structures reach inspection.
4. Click **Submit**, save/name the job if prompted, and wait for completion. **Options → Monitor** shows queued/running status. For a failed job, inspect **Display → Output**, especially **Output** and **Job Log**, and any linked error in the Calculations dialog before resubmitting.

## Inspect and retain results

Open the generated ensemble when prompted. For a one-entry input, the reference names it `document.Conf` (here `complex-screen.Conf`); multi-entry inputs create `document.Conf.identifier` documents that must be opened explicitly. The tutorial also uses an `_Conf` spelling: use the actual returned document/prompt rather than assuming a suffix.

1. In the **ensemble document**, choose **Display → Spreadsheet**. Each row represents a conformer; click its label to inspect that structure. Check boxes beside labels to display several together.
2. Click **Add… → Molecule → Energy**, choosing **kJ/mol**, to post individual energies. For relative rankings, select the intended reference conformer, then use **Add… → Molecule List → rel. E** and select units. Relative energy is measured against the selected molecule. Use these per-conformer values: the original Conformer Distribution document contains Boltzmann-averaged energy, dipole moment and charges alongside its lowest-energy geometry.
3. Use **Geometry → Measure Distance** on each specified atom pair to read the actual resulting distances in Å. Compare them with the requested targets; inspecting the constraint label alone does not establish that the geometry satisfies it. Check connectivity, stereochemistry, clashes and relevant fragment orientations. If distances drift or the calculation fails, revisit the locks, **Subject to → Constraints**, and diagnostics before accepting the ensemble.
4. Save the full ensemble in native Spartan format. To retain a subset, use **File → Save As…** to make a separate native document, for example `complex-selected.spartan`. In that copy, select unwanted rows and use **Delete Molecule** or the spreadsheet's **Delete** button. Deletion removes structures from that document. Keep the full ensemble separately.

Hand off the selected geometries with atom-pair labels, target and measured distances, force field, energy units/reference and search settings for subsequent **constrained quantum refinement**. A downstream program needing another format can receive a supported format via **File → Save As… → Save as type** (for example `.mol2`); transfer the constraint specification separately and verify the imported geometry.

MMFF ranks constrained screening geometries. It does not validate transition states, activation barriers or reaction selectivity. Monte Carlo searching does not guarantee the global minimum, and a small returned ensemble does not establish exhaustive coverage. Spartan extends MMFF parameters beyond the published element set, but that does not establish accuracy for a particular reacting complex; inspect atom typing and geometry for unusual bonding, including boronate complexes, before using rankings to select quantum starting points.

For interface details, use the official [Spartan '26 Tutorial and User's Guide](https://downloads-s3.wavefun.com/support/Spartan26Manual.pdf): constrained distances pp. 251–252, MMFF conformer tutorial pp. 194–196, search controls pp. 297–299, constraint activation p. 324, result documents p. 340, and spreadsheet operations pp. 380–386.
