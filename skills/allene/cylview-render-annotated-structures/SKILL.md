---
name: cylview-render-annotated-structures
description: Use CYLview26 on Windows to turn Gaussian output or coordinate files into consistently scaled molecular figures with corrected display bonds, distance/angle/dihedral labels and reusable styles.
---

# Annotated molecular figures with CYLview26

## Prepare the application and inputs

Use **CYLview26 Windows build 1203** on Windows 10+ x86-64 with OpenGL 3.3 or later; a dedicated GPU is recommended. Obtain `CYLview26_Win_Build1203.exe` from the official [Download section](https://www.cylview.org/#download), install it and launch CYLview26. The download form requests a name and institution; email is optional. Check the installed build in **About…**. The [October 2026 manual](https://www.cylview.org/wiki.html) documents this interface. This is an interactive GUI workflow requiring desktop control or an operator handoff.

Prepare:

- A Gaussian `.log` or `.out`, or a supported coordinate file such as `.xyz`. These formats are read natively; OpenBabel is only needed for additional formats.
- The intended geometry/frame and atom identities to annotate, plus chemically justified choices of display bond types.
- An output directory and a shared style and pixels-per-ångström setting for the figure series.

CYLview's geometric bond perception is a starting point for drawing. Rendering and changing display bonds do not establish chemical bonding or validate a mechanism.

## Open, inspect and style

Representative task: open the externally supplied `C:\project\results\TS7.log`, label a forming-bond distance, and export `C:\project\figures\TS7.png`. Paths, names and settings below are example choices.

1. Use **Open…** in the File Browser, or set its working directory to the results directory and click the file in **Files**. A file click replaces the loaded scenes, so save a useful pose before moving to another structure.
2. In **Data > File Content**, check **Active File**, **Parsed Data** and any red warnings against **Raw File Content**. Inspect the job type in **Analyze**. For an optimization, use **Analyze > Structures > Optimization** and its **Step** slider to display the intended step; inspect its convergence status. For a multi-structure input, select the intended row. Do not assume the initially displayed frame is the desired one.
3. Open **Select > Bonds**, sort by **Length** (ångströms), and inspect unusual contacts, especially forming/breaking bonds and metal coordination. Select a bond and use **Convert to…** to change its appearance. For a missing bond, press **Esc**, then **A**, select exactly two atoms, then right-click **Action on selected > Create bond…**. **Break bond(s)** removes an unwanted bond. Deleting a bond also removes its attached labels; converting preserves them.

   | Display type | Intended depiction |
   | --- | --- |
   | Full | Ordinary bond |
   | Transition State / TS | Dashed forming or breaking bond |
   | Interaction | Dotted noncovalent contact |
   | Dative | Coordination to a metal |

4. For a consistent whole-structure style, clear the selection with **Esc**, then press **Z** and Ctrl-drag a rectangle around the displayed molecule to select atoms and bonds. Apply **CYLview** or **Houkmol** under **Display > Appearance > Styles**; appearance changes act on the selection. Save a custom style and **Export** it as `.style` when it will be reused; use **Import** and **Apply** for subsequent structures.
5. Press **Esc** to clear the selection. Left-drag to rotate; Shift-left-drag rolls, Shift-Alt-left-drag pans and the wheel zooms. Choose a view that exposes the annotated atoms.

## Add measurements and preserve the view

With the selection cleared, right-click the viewport and choose **Toggle Atom Action…**:

| Action | Atom picks, in measurement order |
| --- | --- |
| Label distance on atom pair | 2 |
| Label angle on atom triplet | 3 |
| Label dihedral on atom quartet | 4 |

Pick the intended atoms, checking the **Current Mode** strip for pending picks. Actions stay armed; press **Esc** when finished. Alternatively, **Toggle Bond Action > Add distance label on bond** labels a clicked bond.

Select each created label in **Add > Labels** and edit its properties:

- **Decimals:** 0–5; for example, 2 for distances and 1 for angles.
- **Units:** toggle ångströms for distances or degrees for angles.
- **Format**, **Tether** and **Arc:** control legibility and measurement guides.

Use **Optimize all labels** after a large rotation. Press **L** to select and drag labels when manual placement is needed. Clear selections with **Esc**, then use **Display > Poses > Add** and name the pose, for example `TS7-final`. Double-clicking a saved pose restores it; **Update** overwrites the selected pose.

## Optional comparison overlay

For a two-structure overlay, load the first input normally and load the second as a new scene through **Display > Scenes > Load**. Check the scene table to identify both structures before setting alignment references.

For an overlay instead of Side, activate scene 1, select at least three equivalent atoms, then right-click **Action on selected... > Set as alignment reference**. Repeat for scene 2 with the corresponding reference set. Inspect the References table, then press **Align**. It uses Kabsch alignment onto the first referenced scene and reports RMSD. Reference sets must have equal atom counts. Lock the second scene to prevent accidental rotation/translation; zoom remains shared. **Center** only superposes centers and does not perform atom-based alignment. Interpret the RMSD in the context of the chosen references, rather than treating an arbitrary overlay as a whole-molecule comparison.

## Export and inspect the result

Open **Save Image…** rather than Shift-clicking Quick Save when setting up an export.

| Setting | Example / behavior |
| --- | --- |
| Absolute scale | Enable; choose **200 pixels/Å** for this example |
| Available scales | 50, 100, 200, 400 or 800 pixels/Å, independent of viewport zoom and molecule size |
| Max dimension | Output cap: 1024–32768 px; default 16384 |
| Filename / Browse… | Set the explicit destination `C:\project\figures\TS7.png`; the default filename is the structure name |
| Format / background | PNG with **Transparent background** enabled; JPEG cannot preserve transparency |

Save the image, then open the exported file at its destination. Check geometry/frame identity, label values and units, legibility, transparency and cropping. Use the same absolute scale for every structure in a scheme and retain that scale during layout.

The image is the publication artifact; the pose preserves editable scene state. CYLview normally autosaves poses, styles and labels against the input file checksum when a file is closed or replaced, restoring them when the same file is reopened; this can be disabled under **Options > Automation**. Exported `.style` files transfer appearance settings between machines.

Absent analysis panels mean the parser did not find the relevant data; they do not establish a successful calculation. If parsing is incomplete, inspect the raw input before trusting the displayed geometry or labels. Measurement labels describe the displayed coordinates; dashed or dotted bonds encode the chosen drawing convention.
