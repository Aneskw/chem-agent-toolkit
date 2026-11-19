---
name: gaussian-calculate-rhodium-thf-free-energies
description: Use Gaussian 16 to validate prepared rhodium intermediates and transition states and assemble THF solution free energies with mixed basis sets, frequency analysis and IRC connectivity checks.
---

# Rhodium stationary points and solution free energies

## Environment and starting inputs

Use **Gaussian 16 Revision C.02**, licensed from [Gaussian, Inc.](https://gaussian.com/), on a compatible Linux AVX2 installation. Check the [manufacturer's platform list](https://gaussian.com/g16/g16_plat.pdf); it lists RHEL 8.3 and specified SUSE platforms for this binary. Follow the installation instructions supplied with the licensed distribution. The [vendor execution manual](https://www.hpc.co.jp/wp-content/uploads/sites/9/2021/01/GaussianManual.pdf), sections 2–4, covers setup and invocation.

Load the site's Gaussian environment so `g16` resolves and `GAUSS_SCRDIR` points to writable scratch space with sufficient capacity. The examples use Bash, 4 shared-memory cores and 4 GB of memory; adjust these to the allocated resources. Work in a job directory with unique filenames: the commands below create or overwrite the named input and log files.

Supply chemically checked geometries, charge, multiplicity and the intended intermediate/TS connections. This workflow handles C/H/O/Rh species. Preparing a mechanism or assigning an unknown electronic state requires separate chemical work.

| Input | Required content |
|---|---|
| `state.geom` | Signed integer charge and multiplicity on the first line; then one `Element x y z` row per atom, in angstroms. End with a newline. No XYZ atom-count or comment header. |
| TS guess, when needed | The same format, with a geometry already near the intended transition structure. |
| Reaction mapping | Intended endpoint identities and a balanced reference state, including any separate reactants, ligands or counterions needed for energy comparisons. |

Keep atom identities/order traceable across optimization and IRC. Geometry filenames and labels alone do not establish chemical identity.

## Optimize and classify a stationary point

Create `low.gbs` below. Its leading blank line separates the preceding geometry from the basis section. The final blank line terminates the ECP section. Remove absent light elements from the first line if needed; an element named in a basis block must be present in the molecule.

```bash
cat > low.gbs <<'EOF'

C H O 0
6-31G(d)
****
Rh 0
LANL2DZ
****

Rh 0
LANL2DZ

EOF

cat > state-opt.com <<'EOF'
%chk=state-opt.chk
%mem=4GB
%nprocshared=4
#p M06/GenECP Opt Freq Int=UltraFine 5D 7F Temperature=298.15 Pressure=1.0

Rhodium intermediate optimization and frequencies

EOF
cat state.geom low.gbs >> state-opt.com
g16 < state-opt.com > state-opt.log
```

`GenECP` reads both orbital basis sets and ECPs: the Rh entry occurs in **both** sections. The calculation uses gas-phase M06 geometries and harmonic frequencies. `Int=UltraFine` explicitly retains the Gaussian16 default grid; use the same grid throughout energy comparisons. `5D 7F` explicitly fixes the general-basis angular representation. The thermochemistry settings are 298.15 K and 1 atm, with unscaled frequencies and default isotopic masses.

Inspect `state-opt.log` for completed optimization, converged electronic calculations and the final frequency analysis. A minimum has no imaginary vibrational frequencies. For a supplied TS guess, construct `ts-opt.com` in the same way using its geometry, a unique checkpoint, and replace `Opt` by `Opt=(TS,CalcFC)`. A transition structure must have one imaginary mode whose displacement matches the intended chemical step. Zero imaginary modes indicate a minimum; additional imaginary modes require further investigation. Do not impose an invented numerical cutoff to discard an inconvenient mode.

For each accepted structure, save `state-final.geom`: its original charge/multiplicity line followed by the final optimized Cartesian coordinates, converted to element labels if the output uses atomic numbers. Retain the corresponding log and checkpoint. Frequencies and thermal corrections must belong to this exact geometry and electronic state.

## Verify TS connectivity

For each frequency-validated TS, supply its final coordinates as `ts-final.geom`. This explicit-coordinate route recomputes the initial Hessian, avoiding dependence on a previous checkpoint:

```bash
cat > ts-irc.com <<'EOF'
%chk=ts-irc.chk
%mem=4GB
%nprocshared=4
#p M06/GenECP IRC=(CalcFC,MaxPoints=50,Report=Cartesians) Int=UltraFine 5D 7F

Rhodium transition structure connectivity

EOF
cat ts-final.geom low.gbs >> ts-irc.com
g16 < ts-irc.com > ts-irc.log
```

Gaussian follows both directions by default. `Report=Cartesians` exposes path geometries; energy and reaction coordinate alone are the default report. The illustrative limit of 50 points per direction is a computational limit, not evidence that the endpoints were reached. Inspect both trajectories against the intended intermediates. If a path remains incomplete, extend it using the [IRC options](https://www.conflex.co.jp/gaussian_support/irc.php). Optimize endpoint geometries as minima and classify them using the preceding workflow before assigning connectivity. A run that stops at its point limit or follows the wrong mode does not validate the intended reaction.

When reusing a frequency checkpoint instead, `IRC=RCFC` reads its Cartesian force constants; preserve the matching geometry, method, basis and state. Do not use `RCFC` with an unrelated checkpoint.

## Calculate THF single-point energies

At each accepted optimized geometry, change the orbital basis and Rh ECP together. Create `high.gbs` and build a separate single-point job:

```bash
cat > high.gbs <<'EOF'

C H O 0
6-311+G(d,p)
****
Rh 0
SDD
****

Rh 0
SDD

EOF

cat > state-sp.com <<'EOF'
%chk=state-sp.chk
%mem=4GB
%nprocshared=4
#p M06/GenECP SCRF=(IEFPCM,Solvent=TetraHydroFuran) Int=UltraFine 5D 7F

Rhodium THF single point

EOF
cat state-final.geom high.gbs >> state-sp.com
g16 < state-sp.com > state-sp.log
```

Keep the leading/final blank lines in the basis file, and remove absent light elements as before. This job has no `Opt` or `Freq`: it evaluates the optimized gas-phase geometry in solution. The named THF solvent has dielectric constant 7.4257; do not substitute a different solvent model by changing only a dielectric number.

The combined method is M06/6-311+G(d,p)–SDD/IEFPCM(THF) single points on M06/6-31G(d)–LANL2DZ geometries. Read [GenECP](https://www.conflex.co.jp/gaussian_support/gen.php) or [SCRF](https://www.conflex.co.jp/gaussian_support/scrf.php) when adapting basis blocks or solvation options.

## Assemble and interpret the energies

For each species, retain a record with these fields:

| Field | Source and unit |
|---|---|
| Geometry/state identity | Final coordinates, charge, multiplicity, isotope assignment and job filenames |
| Classification | Imaginary-frequency count and relevant mode; TS endpoint identities from IRC |
| `Gcorr_gas` | `Thermal correction to Gibbs Free Energy` from the matching low-level frequency log, Hartree |
| `Esol` | Final converged solution electronic energy in `SCF Done` from the THF single-point log, Hartree |
| `Gsol` | `Esol + Gcorr_gas`, Hartree |

Use the final converged energy from the intended job, not an intermediate optimization cycle. The frequency log's `Sum of electronic and thermal Free Energies` already includes its **low-level gas-phase electronic energy**. Adding that whole value to `Esol` would double count electronic energy.

For states with the same composition:
```text
Gsol(species) = Esol(species) + Gcorr_gas(species)
DeltaG(A -> B) = [Gsol(B) - Gsol(A)] * 627.5095   kcal/mol
DeltaG_dagger = [Gsol(TS) - Gsol(reactant state)] * 627.5095
```

For association/dissociation steps, sum all species in each balanced state before subtraction. Do not compare absolute energies of differently composed complexes without accounting for the missing components. Maintain the same temperature, pressure, isotope choices and computational settings across a comparison. This construction combines solution electronic energies with gas-phase harmonic thermal corrections; it does not itself introduce a 1 M standard-state correction.

Report relative energies/barriers together with the reference composition, units and stationary-point/connectivity checks. A lower calculated barrier supports a model comparison; it is not an experimental rate or proof of a complete catalytic mechanism.

A missing final energy, unconverged optimization, SCF failure, or `Error termination` leaves that species without a usable result. Preserve the log and address the reported failure before assembling energies. A chemically unexpected minimum or IRC endpoint is a scientific outcome to inspect, not a valid replacement for the requested species.

For the method and energy assembly, see the [study's supplementary computational methods and Table 1, printed pp. 94–97](https://static-content.springer.com/esm/art%3A10.1038%2Fs41929-021-00643-9/MediaObjects/41929_2021_643_MOESM1_ESM.pdf). For output interpretation, consult [Gaussian16 frequency documentation](https://www.conflex.co.jp/gaussian_support/freq.php) and [Gaussian thermochemistry, sections 3–4](https://gaussian.com/wp-content/uploads/dl/thermo.pdf).
