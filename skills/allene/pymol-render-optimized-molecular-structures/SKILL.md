---
name: pymol-render-optimized-molecular-structures
description: Use PyMOL to inspect prepared XYZ molecular geometries, including deposited DFT structures, and export PNG views and reusable PSE sessions.
---

# Inspect and export molecular geometries with PyMOL

## Prepare the software and coordinates

Use licensed **PyMOL 3.1.9**. Obtain the appropriate Windows, macOS Apple Silicon or Linux bundle from [PyMOL downloads](https://pymol.org/#download), follow the linked [installation instructions](https://pymol.org/support#installation), and obtain a license through the site's purchase or existing-user license links. These bundles include Python 3.10; this workflow uses PyMOL's own command line.

Supply a prepared XYZ file: atom count, comment line, then element and three Cartesian coordinates per atom. This workflow displays existing coordinates; it does not optimize them, determine spin states or establish chemical bonding. XYZ coordinates alone do not supply spin-density, SOMO or NCI maps.

For the study's inputs, download **DFT_optimised_xyz_structures.zip** from [Zenodo record 11363682](https://zenodo.org/records/11363682) ([direct archive](https://zenodo.org/api/records/11363682/files/DFT_optimised_xyz_structures.zip/content)). Its published MD5 is `31bb20c733407c9e8a7af1c856421583`. Extract it into a writable working folder, retaining the `DFT_optimised_xyz_structures/` directory and `readme.txt`.

| Input or result | Meaning |
| --- | --- |
| `DFT_optimised_xyz_structures/TS1.xyz` | Deposited geometry; 91 atoms, with a gas-phase electronic energy in Hartree in the comment line |
| `TS1.png` | Rendered image of the current display |
| `TS1.pse` | PyMOL session for reopening and adjusting the view |

## Load and inspect

Start a fresh PyMOL session. Enter the following in its command line, replacing `C:/molecular-work` with the absolute working-folder path containing the extracted directory. Use a suitable absolute path on macOS/Linux. Relative input and output paths below resolve against this folder.

```pml
cd C:/molecular-work
load DFT_optimised_xyz_structures/TS1.xyz, ts1
hide everything, ts1
show sticks, ts1
show nonbonded, ts1
zoom ts1, complete=1
```

Inspect and rotate the model before export. Check the displayed connectivity, especially around metal centers and forming or breaking bonds. The XYZ file has no explicit bond records, so displayed connections are visualization aids rather than evidence of bond order. The nonbonded representation makes isolated atoms visible. Do not edit coordinates or add bonds merely to make the picture resemble a proposed mechanism.

Object names matter: loading again into an existing object appends a coordinate state by default. Use distinct names for distinct conformers.

## Export and reuse

After choosing the view, run:

```pml
png TS1.png, width=1800, height=1400, ray=1
save TS1.pse
```

The dimensions are example choices in pixels; `ray=1` requests ray rendering before saving (default is 0). Without an explicit height, PyMOL preserves the viewport's aspect ratio. Choose unused output filenames when retaining earlier views.

Open the PNG to check framing, visibility and unwanted overlapping objects. Reopen the session in a fresh PyMOL instance with:

```pml
load TS1.pse
```

To inspect another deposited conformer separately in the current session:

```pml
load DFT_optimised_xyz_structures/TS1_c2.xyz, ts1_c2
disable ts1
hide everything, ts1_c2
show sticks, ts1_c2
show nonbonded, ts1_c2
zoom ts1_c2, complete=1
```

Rotate and export using new filenames; save a new PSE if retaining the expanded session. Use `disable ts1_c2` and `enable ts1` to return to the first object. PNG captures the current display, so check which objects are enabled before each export.

## Interpret and troubleshoot

The archive's `c1` (sometimes omitted), `c2`, `c3`, … suffixes order conformers by increasing Gibbs energy within a conformer series. The XYZ comment's gas-phase electronic energy is a different quantity. Read thermochemical values from [the study supplement](https://static-content.springer.com/esm/art%3A10.1038%2Fs44160-024-00658-7/MediaObjects/44160_2024_658_MOESM1_ESM.pdf), §5.7, printed pp.61–63: it separates SCF energy, enthalpy, quasi-harmonic Gibbs energy at 333.15 K and solvent single-point corrections. PyMOL does not calculate these energies.

If loading or saving reports an error, check the working directory, filename and write permissions before proceeding. An empty display can mean the object is disabled or its representations are hidden; both an enabled object and a shown representation are required. Confirm that both output files exist and that the session reopens; a saved image alone does not validate the molecular structure.

For parameter lookup, use the official [command reference](https://pymol.org/pymol-command-ref.html), especially `load`, `show`, `zoom`, `png` and `save`.
