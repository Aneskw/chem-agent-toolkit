---
name: gaussian-validate-palladium-stationary-points
description: Validate supplied palladium reaction intermediates and transition-state guesses with Gaussian 16 optimization, harmonic frequencies and IRC connectivity checks.
---

# Validate palladium stationary points with Gaussian

Use this workflow when geometries and a proposed reaction connection are already available. It validates minima and transition structures at a specified DFT level; it does not discover mechanisms or establish experimental selectivity.

## Environment and inputs

Use a licensed **Gaussian 16 Revision C.02** installation on supported AVX2 Linux hardware. Obtain access through Gaussian or your licensed computing facility. Consult the official [binary setup instructions](https://gaussian.com/g16/g16bin_install.pdf) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf).

Load your facility's C.02 environment, or configure an existing installation by replacing these paths:

```bash
export g16root=/path/to/installation-parent
export GAUSS_SCRDIR=/path/to/writable-scratch
. "$g16root/g16/bsd/g16.profile"
```

The parent contains the `g16/` directory. Create the writable scratch directory before use. Run on allocated compute resources; scheduler requests must accommodate the input's memory and shared CPU count.

Prepare:

| Input | Required content |
| --- | --- |
| Starting structure | Complete atom list and Cartesian coordinates in angstroms, including ligands and hydrogens |
| Electronic state | Net charge and spin multiplicity supplied for that structure |
| Proposed connection | Intended reactant/product structures and the bonds expected to change |
| Coordinate file | `ts-coordinates.txt`: only `Element x y z` rows; no XYZ atom-count line, comment line or blank rows |

The example uses B3LYP with LANL2DZ basis/ECP on Pd and 6-31G(d) on the other atoms, tight SCF convergence and an ultrafine grid. It optimizes without an implicit solvent. Its element block assumes C, H, O and P are present; edit it to match the actual non-Pd elements supported by the chosen basis. The charge/multiplicity `0 1`, four cores and 4 GB below are example choices, not inferred properties of every Pd complex.

## Optimize and classify the structure

In a new calculation directory containing the coordinate file, save this as `ts.com`. Replace `0 1` with the supplied electronic state. Preserve the blank lines, including a final blank line after the ECP section.

```text
%nprocshared=4
%mem=4GB
%chk=ts.chk
#p B3LYP/GenECP Opt=(TS,CalcFC) Freq SCF=Tight Int=UltraFine Units=Ang

Pd transition structure

0 1
@ts-coordinates.txt

C H O P 0
6-31G(d)
****
Pd 0
LANL2DZ
****

Pd 0
LANL2DZ

```

The first Pd block assigns its orbital basis; the final Pd block assigns its ECP. `GenECP` reads both. `Opt=(TS,CalcFC)` seeks a transition structure and calculates the initial Hessian; `Freq` then analyzes the optimized structure at the same level.

For an intermediate, use this same template with `Opt` instead of `Opt=(TS,CalcFC)`, its own supplied coordinates, and distinct input/checkpoint/output names.

Execute from that directory:

```bash
g16 < ts.com > ts.log
```

Inspect `ts.log` for successful optimization and completion of the frequency calculation. Read the **harmonic vibrational** `Frequencies --` entries in cm⁻¹, not just the separate `Low frequencies` diagnostic:

- A minimum should have no imaginary vibrational frequencies.
- A transition structure should have exactly one imaginary frequency, conventionally printed as a negative value. Inspect its displacement vectors to determine whether the mode corresponds to the intended bond changes.
- Extra imaginary modes, the wrong mode, or incomplete convergence leave the structure unvalidated. Small modes near zero require convergence/grid inspection rather than automatic acceptance or an invented cutoff.

Keep the original input and `ts.chk`; the checkpoint is binary and carries the geometry and basis information needed next.

## Follow the reaction path

After the transition structure passes the frequency check, copy its checkpoint so the IRC job cannot overwrite the original:

```bash
cp ts.chk irc.chk
```

Save `irc.com`:

```text
%nprocshared=4
%mem=4GB
%chk=irc.chk
#p B3LYP/ChkBasis Geom=AllCheck IRC=(CalcFC,Report=Cartesians,MaxPoints=50) SCF=Tight Int=UltraFine

```

End this file with a blank line. Add no title, charge, coordinates or basis blocks: `Geom=AllCheck` reads the title, charge, multiplicity and geometry from the checkpoint; `ChkBasis` also retrieves its ECP. `CalcFC` recomputes initial force constants. Both directions are followed by default. The example requests up to 50 points **per direction**, rather than the default 10; that number is a configurable tracing limit, not a connectivity acceptance criterion.

```bash
g16 < irc.com > irc.log
```

Inspect `irc.log` for the reaction-path completion status, `Summary of reaction path following`, and Cartesian reports along both branches. The path summary reports energies relative to the transition structure; it is not a free-energy profile. Forward/reverse labels do not themselves identify reactant/product.

Compare the geometric changes and branch ends with the supplied intended connection. If a branch stops at the point limit before the connection is clear, extend it using the documented [IRC restart/options](https://www.conflex.co.jp/gaussian_support/irc.php); do not treat the limit as proof of arrival at a minimum. Where branch ends have not established minima, take each terminal geometry into a separate same-level `Opt Freq` calculation using the first template. Preserve element identities and atom order, and convert the reported coordinate units to angstroms before reuse. Check the resulting minimum structures against the intended reactant/product.

## Deliver and interpret

Retain the `.com`, `.log` and explicitly named `.chk` files for each calculation; scheduler scratch files may be removed. Report:

| Result | Interpretation |
| --- | --- |
| Converged structure and vibrational classification | Minimum, first-order saddle candidate, or unresolved |
| Imaginary mode and IRC branches | Whether the proposed bond changes and connection were supported |
| Failed or truncated calculation | Unresolved, with the actual convergence/path limitation |
| Wrong IRC connection | A computed saddle for a different connection, not validation of the proposed step |

These are calculated structures and connectivity evidence at the chosen level. A validated connection alone does not supply a barrier ranking or establish the observed reaction mechanism.
