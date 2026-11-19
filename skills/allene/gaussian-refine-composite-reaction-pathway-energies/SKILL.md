---
name: gaussian-refine-composite-reaction-pathway-energies
description: Refine supplied stationary-point energies with Gaussian 16 and combine matching thermochemical corrections to compare reaction profiles or competing stereoisomeric transition states.
---

# Compare solution-phase DFT pathway energies

Use this workflow after geometries and stationary-point identities have been validated. Structure generation, conformer selection, optimization, frequency analysis and transition-state connectivity are preparation supplied to this workflow.

## Environment and inputs

Use **Gaussian 16 Rev. C.02**, licensed and configured on Linux. Obtain it through your institution or the [Gaussian supplier and support entry](https://www.conflex.co.jp/product_gaussian.php). Match the binary to the CPU and OS in the [official platform list](https://gaussian.com/g16/g16_plat.pdf). Follow the distribution or site's setup instructions so `g16` resolves in the job shell and scratch storage is writable. Use your site's compute allocation and submission mechanism.

Prepare one record per species or complex:

| Input | Required content |
| --- | --- |
| `state.geom` | ASCII Gaussian molecule specification: first line is integer charge and spin multiplicity, followed by `element x y z` Cartesian coordinates in angstroms. Include all atoms of the supplied complex. End with a newline. Omit XYZ atom-count and comment headers. |
| Matching frequency result | Validated stationary-point geometry and its Gibbs correction at the selected lower level; identify the corresponding log and geometry. |
| Thermochemical convention | Temperature, pressure/standard state, frequency treatment and any separately supplied correction. Use the same convention for every compared state. |
| State bookkeeping | Species identities, stoichiometric coefficients and a common reference; include any separate molecules needed to balance each state. |

The representative refinement uses M06-2X/6-311+G(d,p) with SMD carbon tetrachloride on supplied B3LYP-D3(BJ)/6-31G(d) geometries. Keep the geometry and correction paired. Another solvent or method is a deliberate protocol change applied consistently across the comparison.

## Run the single-point jobs

Place externally supplied `TS2-S.geom` and `TS2-R.geom` in a working directory. These names denote two competing transition-state complexes with the same composition and charge. Run the following in a configured Bash job shell. Four shared-memory cores and 8 GB are illustrative resource choices; match the allocation. Existing files with these names are overwritten.

```bash
for state in TS2-S TS2-R; do
  {
    printf '%%Mem=8GB\n%%NProcShared=4\n%%Chk=%s.chk\n' "$state"
    printf '# M062X/6-311+G(d,p) SCRF=(SMD,Solvent=CarbonTetrachloride)\n\n'
    printf '%s single point\n\n' "$state"
    cat "$state.geom"
    printf '\n'
  } > "$state.com"
  g16 < "$state.com" > "$state.log"
done
```

This requests single-point calculations; it preserves the supplied coordinates. The generated `.com` files are auditable inputs, `.log` files contain energies and diagnostics, and `.chk` files retain checkpoint data. Gaussian input sections require the blank separators shown. See the [input manual](https://www.conflex.co.jp/gaussian_support/input.php) when adapting the molecule specification.

Open each log and confirm job completion and SCF convergence before accepting its energy. A partial log or failed SCF is an unresolved calculation, even if it contains an earlier energy. Check the echoed method, basis, solvent, charge and multiplicity. The final converged `SCF Done:` energy is in atomic units (hartree).

For this standard SMD calculation, the printed non-electrostatic SMD contribution is already included in the total energy. Do not add it again. The [SCRF manual's output example](https://www.conflex.co.jp/gaussian_support/scrf.php) documents this inclusion. Keep numerical settings and angular basis conventions consistent across all compared single-point jobs.

## Combine and compare

From each matching lower-level frequency log, obtain `Thermal correction to Gibbs Free Energy`, in hartree. This correction includes zero-point energy. The reported total free energy at the lower level already contains its electronic energy; adding that total to the refined energy would count electronic energy twice. The [Gaussian thermochemistry guide, section 3.1](https://gaussian.com/wp-content/uploads/dl/thermo.pdf) defines these fields.

Build a result table with:

`state, SP_log, frequency_log, E_SP_hartree, Gcorr_hartree, C_extra_hartree, G_hartree`

Calculate:

```text
G(state) = E_SP(state) + Gcorr(state) + C_extra(state)
delta_delta_G_R_minus_S = 627.5095 * (G(TS2-R) - G(TS2-S))  [kcal/mol]
```

`C_extra` contains only the separately supplied corrections required by the declared convention. Set it to zero when none are required; do not apply a correction already incorporated in `Gcorr`.

A positive R-minus-S difference places TS2-S lower in calculated free energy. It is a difference between competing transition states; an activation barrier additionally requires subtraction of the appropriate reactant reference.

For a full profile, run the same refinement for every required species. Sum component free energies with their stoichiometric coefficients before subtracting a common reference, then multiply the hartree difference by 627.5095 for kcal/mol. Include separate reactants, catalyst, water or other fragments wherever needed to conserve composition and charge. Compare barriers against the same declared reference.

Return the energy table, relative profile or transition-state difference, input/output paths, and the method and thermochemical convention. Missing corrections prevent a free-energy comparison; label any available electronic-energy difference accordingly. Predicted ordering alone does not establish a measured rate, enantiomeric excess or reaction mechanism.
