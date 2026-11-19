---
name: gaussian-locate-and-validate-transition-paths
description: Locate and verify a transition structure in Gaussian 16, then trace both intrinsic reaction coordinate directions from prepared reactant/product structures or a plausible TS guess and a selected electronic-structure model.
---

# Gaussian transition-state search and reaction-path tracing

## Prepare the environment and structures

Use licensed **Gaussian 16 Rev. C.02**, with its AVX2 Linux binary on a platform listed in the [official platform table](https://gaussian.com/g16/g16_plat.pdf), such as Red Hat Enterprise Linux 8.3. Obtain Gaussian and follow its [official installation entry](https://gaussian.com/techsupport#install). The commands below use a Bourne-compatible Linux shell and a single host. Initialize the installed environment as described in [Running Gaussian](https://gaussian.com/running/):

```sh
export g16root=/site/path/containing-g16
. "$g16root/g16/bsd/g16.profile"
export GAUSS_SCRDIR=/existing/writable/scratch
```

Replace the paths with the installation parent and an available scratch directory. Work in a dedicated calculation directory; input, log and named checkpoint paths below are relative to it. Choose fresh output names: shell redirection replaces existing logs, and Gaussian updates named checkpoints. Allocate memory and cores within the host or scheduler allocation.

Supply:

- Reactant and product geometries with the **same atoms in identical order**, charge and spin multiplicity; use chemically prepared structures for the proposed elementary step. Alternatively supply a plausible TS geometry.
- A selected method, basis/ECP, electronic state and any solvent model. Preserve these across optimization, frequency analysis and IRC. The illustrative `HF/6-31G(d)` route below is a syntax example for a compatible system; replace it throughout with the selected model and include any required basis/ECP input sections.
- Cartesian coordinate rows `Element x y z`, in angstroms for these default input templates. Keep the atom mapping through every handoff. The shown `0 1` means neutral singlet; replace it consistently when needed.

These searches refine a proposed reaction, so a converged structure alone does not identify its chemical connectivity.

## Search and compute frequencies

Create `ts.gjf` from this template. Replace each bracketed coordinate block with all coordinate rows; retain blank-line separators and a final blank line:

```text
%Chk=ts.chk
%Mem=4GB
%NProcShared=4
#p HF/6-31G(d) Opt=QST2 Freq

Reactant endpoint

0 1
<reactant Cartesian coordinate rows>

Product endpoint

0 1
<product Cartesian coordinate rows in the same atom order>

```
Run:

```sh
g16 < ts.gjf > ts.log
```

`Opt` plus `Freq` performs the frequency calculation at the optimized structure with the same model. `%Chk` keeps `ts.chk` after successful completion; do not suppress its retention with `%NoSave`.

Search alternatives from the [Opt manual](https://gaussian.com/opt/):

| Starting input | Change to the template |
| --- | --- |
| Endpoints plus a TS guess | Use `Opt=QST3`; append a third title, charge/multiplicity and geometry block for the TS guess, again in identical atom order. |
| TS guess only | Use `Opt=(TS,CalcFC)`; supply just one title and molecule block containing the guess. |

Never combine `TS` with `QST2` or `QST3`. Here `Opt=CalcFC` calculates the initial optimization Hessian; it does not replace frequency verification at the final geometry.

Before tracing, inspect `ts.log` for completed optimization (`Optimization completed.` / `Stationary point found.`) and a completed frequency stage. Read the final vibrational `Frequencies --` table in cm^-1 and its normal-mode displacement vectors. A first-order saddle should have one imaginary vibrational mode, printed as a negative frequency, and that mode must describe the intended bond rearrangement. Inspect the vectors directly or animate them in a Gaussian-compatible viewer.

Zero imaginary modes, additional imaginary modes, or a mode describing another motion require reassessing the structure/search. Do not count the preliminary near-zero rotation/translation frequencies as reaction modes. If near-zero modes make classification ambiguous, inspect convergence and refine the optimization before repeating same-model frequencies; `Opt=(QST2,Tight)` (or the corresponding search alternative) and `Int=UltraFine` for DFT are documented refinement options. See [Freq](https://gaussian.com/freq/) and the [vibrational-analysis notes, sections 2.1 and 4](https://gaussian.com/wp-content/uploads/dl/vib.pdf).

## Trace the verified transition structure

Copy the **final optimized TS Cartesian geometry**, rather than an endpoint or an intermediate optimization geometry, from `ts.log` into `irc.gjf`. Keep charge, multiplicity, atom order and the selected model. This normal path recomputes the initial Hessian:

```text
%Chk=irc.chk
%Mem=4GB
%NProcShared=4
#p HF/6-31G(d) IRC=(CalcFC,MaxPoints=30,StepSize=10,Report=Cartesians)

IRC from verified transition structure

0 1
<final verified TS Cartesian coordinate rows>

```

```sh
g16 < irc.gjf > irc.log
```
The selected model must support the force-constant calculation used here; the normal example uses analytic HF second derivatives. For methods lacking analytic second derivatives or ONIOM(MO:MM), consult the [IRC manual's algorithm and availability sections](https://gaussian.com/irc/) before adapting this route.

| IRC control | Meaning |
| --- | --- |
| `CalcFC` | Compute force constants at the initial TS. An initial-Hessian option is required. |
| `RCFC` alternative | Read Cartesian force constants from the preceding **frequency** checkpoint. Before running, copy `ts.chk` to a fresh `irc.chk` with `cp ts.chk irc.chk`, then replace `CalcFC` with `RCFC` in the same template. Keep the unchanged verified TS geometry and model; an optimization Hessian alone is insufficient for this handoff. The copy preserves `ts.chk` while IRC updates `irc.chk`. |
| Direction | Both directions are followed by default. `Forward` or `Reverse` limits the run to one. Labels follow the transition-vector phase, not a guaranteed reactant/product assignment. |
| `MaxPoints=30` | Example limit of 30 points **per direction**; default is 10. Reaching a point limit does not prove arrival at a minimum. |
| `StepSize=10` | Example uses the default, 0.10 Bohr: positive N is in 0.01 Bohr units. Negative N instead uses 0.01 amu^(1/2) Bohr units with magnitude abs(N). |
| Coordinates | Mass-weighted Cartesian path coordinates are the default. `Report=Cartesians` requests all Cartesian coordinates; default output otherwise reports energies and reaction coordinate only. |

The point limit, memory and core counts are example choices, not system-independent requirements.

## Read and interpret the path

In `irc.log`, locate `Reaction path calculation complete.` and `Summary of reaction path following`. The summary reports energies relative to the TS, whose energy and reaction coordinate are both zero. Inspect the requested Cartesian reports along both branches to track forming/breaking bonds and identify their chemical direction. Retain `ts.gjf`, `ts.log`, the verified frequency checkpoint `ts.chk`, `irc.gjf`, `irc.log` and the evolving path checkpoint `irc.chk`.

Report the final geometry reached on each branch and whether it approaches the intended endpoint. A finite IRC segment may stop before a minimum; if endpoint identity remains unclear, extend the path (`IRC=Restart` is documented for continuation/additional points) or optimize the last geometries separately with the same model and verify their frequencies. Do not label an unverified branch endpoint as a minimum.

If Gaussian terminates with an error, the optimization/frequency stage is incomplete, or the path stops unexpectedly, inspect the last diagnostic and the relevant stage before continuing. An absent path summary is not an empty successful connectivity result. A valid TS with a path leading elsewhere supports a different connection; revisit the proposed endpoints or TS guess.

For each terminal branch geometry, prepare a separate same-model `Opt Freq` job with its own input, log and checkpoint. Confirm optimization completion and no imaginary vibrational modes before reporting it as a minimum. Deliver the final endpoint geometries and their frequency assessments with the branch-to-species mapping.
