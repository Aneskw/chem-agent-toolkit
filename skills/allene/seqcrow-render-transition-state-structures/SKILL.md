---
name: seqcrow-render-transition-state-structures
description: Create transition-state structure figures from supplied molecular coordinates or quantum-chemistry output using SEQCROW in ChimeraX, including reactive-bond annotations, orientation, and PNG export.
---

# Transition-state figures with SEQCROW

Render supplied structures and mark identified forming or breaking bonds. The reactive atoms and scientific assignment must come from the supplied calculation or user; a graphical TS bond does not validate a transition state or establish a mechanism.

## Setup and inputs

Use **UCSF ChimeraX 1.12** from the [official download page](https://www.rbvi.ucsf.edu/chimerax/download.html) and **SEQCROW 1.10.2** from this [pinned official wheel](https://raw.githubusercontent.com/QChASM/SEQCROW/449e6853aeef0469057b62742889e657ca2224e8/dist/seqcrow-1.10.2-py3-none-any.whl). The bundle declares ChimeraX compatibility from 1.6 through 1.14 and includes AaronTools. No Gaussian installation is needed to render existing files.

Open ChimeraX and install the downloaded wheel through its **ChimeraX command line**, using its actual local path:

```text
toolshed install "C:/work/seqcrow-1.10.2-py3-none-any.whl"
```

Restart ChimeraX. When replacing an existing SEQCROW installation, the [official installation instructions](https://github.com/QChASM/SEQCROW/blob/449e6853aeef0469057b62742889e657ca2224e8/README.md#installation) prescribe `toolshed uninstall SEQCROW`, a restart, then installation and another restart.

Prepare these inputs:

| Input | Required preparation |
| --- | --- |
| Structure | A single-geometry `.xyz`, or supported quantum-chemistry output such as a Gaussian `.log`. For XYZ: atom count, comment line, then element and Cartesian x/y/z for every atom. |
| Reactive endpoints | Two identified atoms per forming/breaking bond, in the same molecular model. |
| Orientation | Two distinct atoms defining the desired viewing direction. |
| Output | A writable directory and a new PNG filename. |

Commands below run inside ChimeraX, not a system shell. Replace example paths, model IDs, and atom names with those for the supplied structure.

## Import, annotate, and orient

Open the structure in a fresh ChimeraX session:

```text
open "C:/work/ts.xyz"
```

For existing Gaussian output, substitute its `.log` path. Check that the displayed geometry is the intended one. The Models panel identifies model IDs. Hover over an atom to find its name; `#1@C1` means atom C1 in model 1. In XYZ imports, names count each element separately (C1, C2, O1, etc.); they are not global XYZ row numbers.

For a ball-and-stick presentation, choose SEQCROW's **ball-stick-endcap** preset. It draws non-hydrogen atoms as balls and sticks and hydrogen atoms as sticks/endcaps.

Select the first reactive atom with Ctrl-click, then add the second with Ctrl-Shift-click. Confirm that exactly those two atoms are selected in the same model, then run:

```text
tsbond sel transparency 50
```

Repeat with a new two-atom selection for each additional reactive bond. This creates a graphical pseudobond and removes the corresponding ordinary bond from the working model, if present. It does not alter atom positions. The 50 setting gives a half-transparent depiction; valid values are strictly between 0 and 100.

Orient along a separate pair of atoms. For example, **if C1 and O1 are the intended orientation pair in model 1**:

```text
lookDown #1@C1 atom2 #1@O1 axis z
```

The default z axis points out of the screen; x and y are alternatives. Both atom specifications must match the same model. `lookDown` rotates the model's coordinates about the second atom; it is not merely a camera change. Use the same chemically corresponding orientation pair for related figures, then adjust framing with the mouse as needed. Keep the original coordinate file unchanged.

## Export and inspect

Export the visible scene to a new file:

```text
save "C:/work/ts.png" width 2400 supersample 3 transparentBackground true
```

Width is in pixels; omitted height follows the window aspect ratio. Supersampling 3 smooths edges and is also the default. Transparent background adds an alpha channel to PNG. These are example presentation settings. See [Save Image options](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/save.html#image) when another size or background is required.

Open the PNG and confirm framing, atom visibility, and reactive-bond depiction. It contains the displayed scene, including other visible models. For an editable handoff, additionally save the session under a new name:

```text
save "C:/work/ts-figure.cxs"
```

A coordinate-only XYZ export does not preserve the figure's graphical annotations.

If the Log reports `2 atoms must be selected` or `atoms must be on the same structure`, correct the selection before repeating `tsbond`. If orientation does nothing, check the model ID and both atom names, and ensure the two endpoints are distinct. Inspect the model after either operation before exporting; graphical annotations and orientation do not establish optimization convergence, vibrational character, or relative energy.
