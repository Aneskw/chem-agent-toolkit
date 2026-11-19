---
name: orca-decompose-fragment-bonding
description: Use ORCA ETS-NOCV to decompose interactions between two prepared molecular fragments and export orbital-resolved deformation densities.
---

# Fragment interaction analysis with ORCA ETS-NOCV

## Prepare the calculation

Use **ORCA 6.1.1** with the [ORCA 6.1 EDA-NOCV interface](https://www.faccts.de/docs/orca/6.1/manual/contents/spectroscopyproperties/nocv.html). Obtain the platform package through the [official release/download entry](https://www.faccts.de/orca-6-1-1/) (academic forum registration or FACCTs access, as applicable). Follow the [official installation guide](https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html); open a new terminal after installation so PATH includes ORCA. The serial example below needs `orca` and `orca_plot` from that installation.

Start with a prepared adduct geometry and scientifically justified membership, charge and spin state for **two** fragments. This is a single-point interaction analysis at the supplied geometry. Fragment preparation energies relative to isolated equilibrium structures require separate calculations and are outside the reported instantaneous interaction energy.

| Input | Required choice |
|---|---|
| Geometry | Cartesian coordinates in Å by default; preserve the prepared adduct geometry |
| Whole-system state | Total charge and multiplicity in `* xyz charge multiplicity` |
| Fragment membership | Every atom assigned to fragment 1 or 2; labels `Element(1)`/`Element(2)`, or zero-based atom indices in `%Frag` |
| Electronic model | Whole-system method and `FRAG1`/`FRAG2` methods; normally the same level of theory |
| Fragment states | `FRAG1_C`, `FRAG2_C`: charges, whose sum equals total charge; `FRAG1_M`, `FRAG2_M`: multiplicities |

Basis functions on each fragment must agree with those on the corresponding atoms of the adduct. For different fragment basis sets, also specify the corresponding `FragBasis` entries in the adduct `%basis` block; see manual §5.35.1. Fragment methods containing blocks can instead be supplied through `FRAG1_METHODFILE` and `FRAG2_METHODFILE`; method strings/files do not require a leading `!`.

## Write and run an input

In a fresh working directory, save this as plain-text `adduct.inp`. This adapts the manual's Li⁺–NH₃ example, explicitly setting both fragment states. Its BP86/TZVP model and geometry are a usage example; choose the model, geometry and fragment states appropriate to the actual system.

```text
! BP86 TZVP EDA
%EDA
  FRAG1 "BP86 TZVP"
  FRAG2 "BP86 TZVP"
  FRAG1_C 1
  FRAG1_M 1
  FRAG2_C 0
  FRAG2_M 1
end
* xyz 1 1
Li(1)    -0.212072     1.951867     0.003088
N (2)    -0.424027    -0.022414    -0.010889
H (2)    -0.914047    -0.381589    -0.841562
H (2)    -0.958117    -0.388240     0.789150
H (2)     0.468043    -0.535155     0.011083
*
```

Alternatively remove the parenthesized atom labels and append this block to the same input. Fragment numbers start at **1**, while atom indices start at **0**; `1:4` includes atoms 1 through 4.

```text
%Frag
  Definition
    1 {0} end
    2 {1:4} end
  end
end
```

Run from that directory (Windows command prompt or a Unix shell, with ORCA on PATH):

```sh
orca adduct.inp > adduct.out 2>&1
```

The [running guide](https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/running.html) describes executable resolution and output redirection. Retain the complete calculation directory, including `adduct.out`, `adduct.gbw`, `adduct.NOCV.gbw` and the generated density container, until all exports are complete.

Neutral singlet fragments are defaults, so set states explicitly when adapting the example. Open-shell fragments default to spin-up unpaired electrons; `FRAG1_SF TRUE` or `FRAG2_SF TRUE` flips a fragment's unpaired spins when required by the chosen fragment coupling. Ordinary EDA runs generate fragment calculations internally; separate fragment single points are unnecessary. Degenerate fragment ground states can require deliberate orbital occupation/orientation preparation: consult §5.35.4 before interpreting integer NOCV eigenvalues coupled to unusually high orbital energy. Double-hybrid calculations require the additional density choices in §5.35.5.

## Read energies and NOCV pairs

Require completed EDA and NOCV sections in `adduct.out` before interpreting the calculation; missing sections or calculation errors require diagnosis rather than reporting a decomposition.

| Output section/field | Interpretation |
|---|---|
| Energy Decomposition Analysis | Terms printed in Hartree and kcal/mol |
| Bond Energy | Instantaneous interaction at the supplied geometry, without fragment preparation energies |
| Orbital Energy | Orbital relaxation/interaction contribution |
| Electrostatic Energy | Electrostatic interaction of frozen fragment densities |
| Pauli Energy and Delta E^0(XC) | Separately printed parts of the combined Pauli/exchange-correlation contribution |
| Delta Dispersion | Adduct-minus-fragments dispersion correction when used |
| NOCV analysis | Paired negative/positive eigenvalues in electrons; `DE_k`, `DT_k`, `DV_k` in kcal/mol |

For the illustrated mean-field workflow, reconcile:
`Bond Energy = Orbital + Electrostatic + Pauli + Delta E^0(XC) + Delta Dispersion`.
Do not omit `Delta E^0(XC)` when summing the printed rows. Negative energy contributions stabilize the interaction; positive contributions oppose it.

The sum of NOCV `DE_k` contributions should recover Orbital Energy within printed precision. Open-shell systems/fragments have separate Alpha and Beta NOCV tables; combine both spin-channel sums. Associate each pair's energy and eigenvalues with its spatial deformation density before assigning donation or back-donation.

## Export a deformation-density contribution

From the same calculation directory:

```sh
orca_plot adduct.gbw -i
```

Use the interactive menus documented in §5.35.3:

1. Choose **9 — List all available densities**. Copy the exact listed contribution name, for example `adduct.NOCV0_0.tmp`.
2. Choose **1 — Enter type of plot**, then **2 — (scf) electron density**.
3. Decline the proposed total density `adduct.scfp`; supply the selected NOCV density name.
4. Use **5 — Select output file format** to choose a format accepted by the downstream density viewer, and **4 — Enter number of grid intervals** to set the plotting grid.
5. Choose **11 — Generate the plot**. Retain the generated plot file at the path reported by `orca_plot`; hand it to the compatible viewer for positive and negative isosurfaces. Repeat for other saved contributions, then exit with **12**.

The suffix index `_0` through `_4` denotes the first five saved pair contributions. `NOCV0` denotes spin-up; open-shell calculations also save the first five spin-down contributions as `NOCV1`. Use names returned by the density listing, rather than treating those `.tmp` names as standalone files or assuming every printed pair is exportable.

A pair density is `Δρ_k = ν_k(ψ_+k² − ψ_−k²)`: positive regions gain density and negative regions lose density relative to the frozen-fragment reference. Record the viewer's sign/color convention, pair index, spin channel and isovalue with each image.

Use **`adduct.gbw`** for this density workflow. **`adduct.NOCV.gbw`** stores the NOCV orbitals for separate orbital visualization; it does not replace the main GBW for deformation-density export. If expected contributions are absent from option 9, check the EDA completion and retained density container before proceeding.
