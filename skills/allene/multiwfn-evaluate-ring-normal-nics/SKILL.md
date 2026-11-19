---
name: multiwfn-evaluate-ring-normal-nics
description: Use Multiwfn to generate ring-normal probe coordinates and obtain NICS(1)zz from externally calculated magnetic shielding tensors, including tilted or nonplanar rings.
---

# Ring-normal NICS with Multiwfn

## Prepare

Use **Multiwfn 2026.11.10**. Obtain the Windows 64-bit precompiled archive from the [official download page](http://sobereva.com/multiwfn/download.html), extract it, and run `Multiwfn.exe`. The same page supplies the applicable **2026.11.3 manual**; consult §3.28.4 for this operation. Read the download terms and use the package's citation guidance when publishing.

Have these inputs ready:

| Input | Contract |
|---|---|
| Molecular geometry | A coordinate file such as `.xyz`, `.pdb`, `.mol`, or `.fch`. A geometry-only file is sufficient. Only the first frame of a multi-frame XYZ is loaded. |
| Ring selection | Atom indices in the loaded structure, normally all atoms of the ring; at least three noncollinear atoms are needed to define a plane. Lists/ranges such as `2,3,7-10` are accepted. |
| Ring center | Default: geometric center of the selected atoms. Alternatively supply explicit X,Y,Z coordinates in Å, with the center convention recorded. |
| Probe tensors | All nine magnetic **shielding** components in ppm at each selected probe, in the same Cartesian frame as the loaded geometry. Isotropic shielding or principal values alone cannot supply the orientation-dependent result. |

Electronic-structure calculation is an external handoff. Geometry determines the probes and normal; it does not supply the shielding or establish aromaticity.

## Generate probes and obtain tensors

For a molecule in `C:\work\ring.xyz`, with ring atoms 1–6 (an example selection to replace), launch from the extracted Multiwfn directory in PowerShell:

```powershell
.\Multiwfn.exe 'C:\work\ring.xyz'
```

At the interactive prompts enter:

```text
25
4
```

At the ring-center prompt **press Enter on an empty line** to use the geometric center. At the next prompt enter:

```text
1-6
```

Record the fitted-plane RMS error in Å, unit normal `u`, ring center `c`, and both printed probe coordinates. The program prints **below first, above second**, corresponding to `c − u × 1 Å` and `c + u × 1 Å`. Label the points consistently as minus/plus; the normal's sign does not give a universal chemical meaning to “above.” For a puckered ring, retain the fitting error because the chosen plane affects interpretation; this workflow defines no acceptance threshold.

If tensors are not yet available at these exact points, hand off the unchanged geometry, probe coordinates and requested electronic method to the calculation provider. Request full Cartesian shielding tensors in ppm and the correspondence between each tensor and probe. For Gaussian, the [author's worked example](http://sobereva.com/261) uses `Bq` probe atoms and **`NoSymm`** to prevent automatic reorientation; [Gaussian's NMR documentation](https://gaussian.com/nmr/) specifies `NMR=GIAO` and the tensor output. Method/basis choice belongs to that calculation. Preserve the coordinate frame: if the provider rotates the geometry, obtain compatible tensors/geometry before projecting them.

Leave Multiwfn waiting at the tensor prompt, or cancel with `q` and later select `4` again from menu 25 with the same center and atom selection.

## Project each tensor

At the tensor prompt, paste the three labeled tensor lines from the corresponding Gaussian shielding block, in this order:

```text
XX= <value>   YX= <value>   ZX= <value>
XY= <value>   YY= <value>   ZY= <value>
XZ= <value>   YZ= <value>   ZZ= <value>
```

The angle-bracket fields above are placeholders for the external results. Alternatively enter three numeric triples separated by commas, in precisely the same order. Keep all nine components; they need not be symmetric. Check Multiwfn's echoed tensor against the source block before using the result.

Read the terminal output:

- `The shielding value normal to the plane is`: projected shielding `σ⊥ = uᵀ σ u`.
- `The NICS_ZZ value is thus`: already negated, `−σ⊥`, in ppm. Use this value directly; do not negate it again.

For the other probe, select subfunction `4` again in menu 25 and repeat the center/atom inputs with its tensor. The routine returns after one tensor; it does not automatically process both sides or export a results table. Save the printed values in your report. Entering `q` at the tensor prompt cancels that projection and gives no NICS result.

## Report and interpret

Report ring indices, center convention and coordinates, normal, plane-fit RMS error, both probe coordinates, electronic method/basis, tensor provenance, and each signed NICS value in ppm. If a two-sided value is appropriate, calculate `(NICS_plus + NICS_minus)/2` and retain the individual values alongside it. An asymmetric environment can give different values on the two sides. For a cage, an exterior probe may be the intended choice rather than an average with an interior probe; state the choice.

The projected direction is the fitted ring normal, not necessarily the laboratory Z axis. Negative NICSzz supports an aromatic interpretation; interpret it with the molecular context rather than treating its sign as a standalone aromaticity verdict. If isotropic NICS(1) is also requested, negate the external isotropic shielding separately and label it distinctly from NICS(1)zz. Missing tensors or a frame mismatch leave the projection unresolved; they are not zero shielding.
