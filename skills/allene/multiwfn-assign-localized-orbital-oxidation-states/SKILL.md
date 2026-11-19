---
name: multiwfn-assign-localized-orbital-oxidation-states
description: Use Multiwfn to localize occupied molecular orbitals and assign atomic or fragment oxidation states by LOBA, including threshold sensitivity checks. Select for a prepared wavefunction with basis and orbital information.
---

# Assign oxidation states with localized orbitals in Multiwfn

## Prepare the program and wavefunction

Use **Multiwfn 2026.11.10**. Obtain the Windows 64-bit binary archive from the [official download page](http://sobereva.com/multiwfn/download.html), extract it, and retain the accompanying `settings.ini` and program resources. The example below uses Windows PowerShell. The [official 2026.11.3 manual](http://sobereva.com/multiwfn/misc/Multiwfn_manual_2026.11.3.pdf), sections 3.10.100, 3.22 and 4.8.4, documents this interface.

Required input is an externally prepared single-determinant SCF wavefunction, normally a Gaussian formatted checkpoint (`.fch`), containing basis functions, orbital coefficients and occupations. Geometry optimization, orbital generation, charge and spin selection are upstream tasks. A geometry-only file is insufficient. Preserve atom ordering for fragment definitions. If using effective core potentials, retain the wavefunction's atomic-charge information; use `.fch` for the localized output.

Run in a writable analysis directory. Localization exports `new.fch` there and, by default, reloads it, replacing the orbitals in memory. Keep the original input separately and preserve any existing `new.fch` before another localization run.

## Localize and run ordinary LOBA

Adapt these example paths to the extracted executable, its settings file and your prepared wavefunction. Set the current directory to your analysis directory before launching:

```powershell
Set-Location 'C:\work\loba'
& 'C:\Tools\Multiwfn\Multiwfn.exe' 'C:\work\inputs\complex.fch' -set 'C:\Tools\Multiwfn\settings.ini'
```

At the interactive prompts, enter one value per line:

```text
19
1
8
100
50
```

| Entry | Operation |
| --- | --- |
| `19` → `1` | Localize occupied orbitals only; enough for LOBA. The default is Pipek–Mezey localization with Mulliken populations. |
| `8` → `100` | Enter orbital composition analysis, then LOBA/mLOBA. LOBA itself uses **Hirshfeld** orbital compositions, independently of the localization population scheme. |
| `50` | Ordinary LOBA threshold of **50 percent**, not a fractional input of 0.5. This is an illustrative starting choice. |

Before entering `8`, check that localization reports `Successfully converged!` and that `new.fch` has been loaded. Do not interpret an unconverged localization. `Warning: Convergence failed!` requires revisiting the localization settings; errors about missing basis information or a non-SCF wavefunction require an appropriate upstream input.

When diffuse functions are heavily used, the default PM-Mulliken localization can mislead. In menu `19`, enter `-6`, then `3` for PM-Becke, then `1` to localize occupied orbitals. PM-Becke is more expensive. Record the localization method used; do not confuse it with LOBA's Hirshfeld composition analysis.

## Inspect, compare and retain results

LOBA prints `Oxidation state of atom`, with atom index and element, followed by `The sum of oxidation states`. These are oxidation-state assignments, distinct from atomic partial charges. Copy the console output into an analysis record, and retain `new.fch` under a descriptive name for later inspection or reuse.

At the repeated LOBA threshold prompt, enter `60` to compare with `50` without relocalizing. The manual suggests 50–60% as a useful range for transition-metal assignments. Treat these as sensitivity checks, not universal correctness criteria or paper-specific settings. Report both assignments if they differ.

Ordinary LOBA attributes an occupied localized orbital's electrons to an atom only when that atom's composition is **strictly greater** than the threshold. Occupation weights matter: a doubly occupied orbital contributes two electrons. Because some electrons can remain unattributed, or be attributed more than once at low thresholds, the sum of atomic oxidation states need not equal the net molecular charge. A mismatch is an interpretation diagnostic, not an automatic program failure; do not adjust the threshold merely to force a desired charge sum.

For a fragment, remain at the LOBA threshold prompt and enter:

```text
-1
1,3-5,9
50
```

Replace `1,3-5,9` with the **1-based atom indices** of your actual fragment; these example indices have no chemical meaning for an arbitrary input. Multiwfn then prints `Oxidation state of the fragment` alongside the atomic results. Ordinary LOBA applies the threshold to the **summed fragment contribution** of each orbital, so its fragment result need not equal the sum of its atomic assignments. Enter `-1` again to redefine the fragment. Enter `0` to leave LOBA; follow the displayed menus back to the main menu and use `q` to quit.

Record the input identity, charge/spin, atom-index mapping, program version, localization method, threshold, atomic table, printed total and any fragment result. For attribution diagnostics, set `outmedinfo=1` in the selected `settings.ini` before starting Multiwfn; it prints which orbital electrons were assigned.

## Optional methodological alternative

Entering `m` instead of a number selects **modified LOBA (mLOBA)**. Label that result separately. It assigns each orbital's electrons to its largest atomic contributor, eliminating the threshold and conserving total charge for the usual integer-occupation case. Symmetry can produce unequal assignments to equivalent atoms; a chemically meaningful fragment can help interpret that case. For mLOBA, the fragment result is the sum of its atomic assignments. Do not silently substitute mLOBA when ordinary LOBA was requested.
