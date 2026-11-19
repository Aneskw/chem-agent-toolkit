---
name: multiwfn-compare-frontier-orbitals
description: Compare HOMO or LUMO shapes and recorded orbital energies from prepared wavefunctions using Multiwfn's built-in viewer, and export matched orbital pictures.
---

# Compare frontier orbitals with Multiwfn

## Prepare the viewer and inputs

Use **Multiwfn 2026.11.3, Windows 64-bit full binary package**, available from the [official download page](https://sobereva.com/multiwfn/download.html). Extract the entire `Multiwfn_2026.11.3_bin_Win64.7z` package into a writable directory. Keep its accompanying files, including `settings.ini`. This workflow requires an interactive graphical desktop; the noGUI package cannot provide it. The [matching manual](https://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), sections 2.1–2.2, 3.2 and 4.0.1, covers setup and viewer controls.

Required external inputs are two comparable, already calculated molecular wavefunctions:

| Input | Requirement |
| --- | --- |
| `.fch` / `.fchk` or `.mwfn` | Must contain the occupied and virtual orbitals to inspect, coefficients, occupations and meaningful recorded orbital energies. |
| Computational provenance | Retain method, basis, charge, spin state and geometry provenance for each file; interpret energy differences only for a justified comparison. |
| Orbital identity | Use canonical HF/KS orbitals for the normal HOMO/LUMO path. The convenience labels support restricted, unrestricted and restricted open-shell HF/KS wavefunctions. |

Ordinary `.wfn` and `.wfx` inputs cannot supply the virtual orbitals for this LUMO workflow. Geometry-only inputs cannot display molecular orbitals. If a required orbital or meaningful energy is missing, obtain a suitable wavefunction from the external calculation stage before continuing. Generating those calculations is outside this workflow.

## View, record and export

Example: compare `A.fch` and `B.fch`, supplied by the user. The following PowerShell command assumes the extracted executable is in `C:\Tools\Multiwfn` and the first input is in `C:\analysis`; replace these example paths:

```powershell
Set-Location 'C:\Tools\Multiwfn'
.\Multiwfn.exe 'C:\analysis\A.fch'
```

The invocation directory is Multiwfn's current folder. Alternatively, double-click `Multiwfn.exe` and enter the full input path at its prompt.

1. After loading, enter **`0`** at the main menu. The viewer opens; the console prints atom and frontier-orbital information.
2. In the lower-right orbital-selection text box, enter **`l`** and press Enter for LUMO, or **`h`** for HOMO. Numerical indices also work. For unrestricted inputs choose the intended spin explicitly: `la` / `lb` for alpha/beta LUMO, `ha` / `hb` for alpha/beta HOMO. A negative numerical index such as `-5` selects beta orbital 5.
3. Select **Orbital info. → Show all**. In the console, find the selected orbital and record its index, spin/type, occupation and energy. Listings labelled `Ene(au/eV)` give atomic units and eV in that order; retain the unit with the value.
4. Choose one shared isovalue through **Other settings → Set isovalue**. For example, `0.05` is an illustrative starting choice, not a universal threshold. Set **Isosur. quality → high-quality** for both structures. Changing quality deletes the displayed surface: reselect the orbital to regenerate it. Keep the wavefunction display rather than switching to Density when comparing orbital phase.
5. Match the molecular orientation and scale using mouse rotation/zoom or **Set view → Set rotation of viewpoint**. Use the same isovalue, quality, phase colors and molecular representation for both inputs; align corresponding molecular features rather than relying on identical rotation angles for differently oriented inputs.
6. Click **Save picture**. Retrieve the exported image from the current folder, following any displayed filename prompt. The default `graphformat` in `settings.ini` is `png`; `graph3Dsize` controls image dimensions. Preserve the image under a distinct descriptive name, such as `A-LUMO.png`, before saving another view.
7. Click **RETURN**, then `q` in the main menu. Launch a fresh instance with `B.fch`, repeat the same settings and export as `B-LUMO.png`. Repeat for HOMOs if requested.

## Interpret and deliver

Deliver both pictures with a compact comparison table containing input identity, orbital label/index, spin, occupation, energy with unit, and the shared visualization settings. Describe localization on corresponding atoms or bonds and any supported energy difference.

Default green and blue surfaces mark positive and negative wavefunction phase, respectively, not positive and negative charge. Surface extent depends on the chosen isovalue. Shape and recorded orbital energies support a qualitative orbital comparison; they do not yield reaction barriers or establish reaction selectivity by themselves.

If no surface appears, check that an orbital rather than `none` is selected and reselect it after changing quality. If a diffuse surface is clipped, enlarge **Other settings → Set extension distance** (Bohr) and regenerate the orbital; document the adjusted setting. An absent virtual orbital or placeholder energy is an input limitation, not a physical conclusion.
