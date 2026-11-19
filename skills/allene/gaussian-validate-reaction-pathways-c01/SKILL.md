---
name: gaussian-validate-reaction-pathways-c01
description: Use Gaussian to optimize supplied intermediates and transition-state guesses, classify them with harmonic frequencies, and verify connectivity with IRC calculations.
---

# Validate stationary points and reaction connectivity with Gaussian

Use optimization, frequency analysis and IRC together to assess a proposed elementary reaction step. Starting structures, charge/spin assignments and the electronic-structure model must be supplied. This workflow produces computed structural evidence; it does not search for a mechanism or assemble a solution free-energy profile.

## Environment and inputs

Use **Gaussian 16 Rev. C.01**, CPU execution on a supported Linux platform. Obtain licensed access through [Gaussian orders](https://gaussian.com/orders/) and follow the official [installation instructions](https://gaussian.com/techsupport#install). Match the binary to the [platform matrix](https://gaussian.com/g16/g16_plat.pdf). The commands below use Bash on an allocated compute node with `g16` on PATH and writable scratch configured through `GAUSS_SCRDIR`.

At an HPC site, use its Gaussian module and scheduler allocation. For example, NIH documents `module load Gaussian/G16-C01`; that module name is site-specific. Allocate memory, cores and local scratch before running; keep any supplied `%Mem` and `%NProcShared` settings within that allocation. See [NIH's execution and scratch guidance](https://helixweb.nih.gov/apps/Gaussian.html).

Have these complete Gaussian input decks in a working directory:

| Supplied file | Required preparation |
| --- | --- |
| `reactant.com`, `product.com` | Proposed minima for the same elementary step. |
| `ts-guess.com` | A chemically plausible transition-state guess. |
| All decks | Title, charge and multiplicity, molecular geometry, method, basis and any ECP/additional input sections. |

Retain the supplied method, basis/ECP, solvent and electronic-state settings throughout validation. Keep an atom mapping across the structures. For a mixed-basis or heavy-element calculation, preserve the complete supplied basis/ECP sections; the illustrative light-element route lines below are not replacements for them.

Work on copies and give each job a distinct log and checkpoint filename. Shell `>` overwrites an existing log; a job also updates the checkpoint named by `%Chk`.

## Optimize and classify

Copy the supplied decks to `r-optfreq.com`, `p-optfreq.com` and `ts-optfreq.com`. In each copy, replace the previous job-type keywords with the following while retaining the model chemistry and its required input sections:

| Job | Job-type keywords | Example route for supplied B3LYP/6-31G(d) inputs |
| --- | --- | --- |
| Reactant and product | `Opt Freq` | `#p B3LYP/6-31G(d) Opt Freq` |
| Transition state | `Opt=(TS,CalcFC) Freq` | `#p B3LYP/6-31G(d) Opt=(TS,CalcFC) Freq` |

These are illustrative method choices. `CalcFC` computes initial force constants for the TS search. Combining `Opt` and `Freq` runs the frequency analysis at the optimized geometry, with the same electronic-structure model. For the TS deck, use `%Chk=ts-optfreq.chk` before its route section; use different checkpoint names for the minima.

Run each job, inspecting it before continuing:

```bash
g16 < r-optfreq.com > r-optfreq.log
g16 < p-optfreq.com > p-optfreq.log
g16 < ts-optfreq.com > ts-optfreq.log
```

Read the optimization convergence information, the final geometry and the `Frequencies --` blocks, including normal-mode displacement vectors. Gaussian reports an optimized stationary point with `Optimization completed.` and `Stationary point found.`; that alone does not classify it.

- **Minimum:** no imaginary vibrational frequencies.
- **First-order saddle:** one imaginary frequency, represented by a negative frequency value. Inspect that mode's displacement pattern to establish whether it describes the intended bond changes.
- **Unexpected imaginary modes or incomplete optimization:** revise the structure or convergence treatment and repeat the calculation before using it as a validated minimum or TS.

Do not combine frequencies from one model chemistry with a geometry optimized using another. If frequency analysis exposes inadequate convergence, the [frequency documentation](https://gaussian.com/freq/) describes `Opt=CalcAll`, which uses exact second derivatives during optimization and performs frequency analysis at the final structure.

## Follow the validated TS in both directions

Only proceed after the TS frequency check. Create `ts-irc.com` from a copy of the supplied TS deck:

1. Replace its molecular coordinates with the final optimized TS coordinates from `ts-optfreq.log`, retaining the atom mapping, charge and multiplicity.
2. Retain its model chemistry and all required basis/ECP input.
3. Replace the optimization/frequency job keywords with `IRC=(CalcFC,MaxPoints=30,Report=Cartesians)`.
4. Use a distinct checkpoint, such as `%Chk=ts-irc.chk`.

For the same illustrative light-element model, the route is:

```text
#p B3LYP/6-31G(d) IRC=(CalcFC,MaxPoints=30,Report=Cartesians)
```

This route belongs in the complete deck with its title and explicit final TS molecule specification; it is not a standalone input file.

```bash
g16 < ts-irc.com > ts-irc.log
```

`CalcFC` computes the initial Hessian at the supplied TS. Both directions are followed by default. `MaxPoints=30` is an example limit **per direction**, not a convergence criterion; the default is 10. `Report=Cartesians` requests coordinates along the path so the endpoint geometries can be recovered.

If reusing the saved frequency Hessian instead, copy `ts-optfreq.chk` to a separate IRC checkpoint, point the IRC deck's `%Chk` at that copy, and replace `CalcFC` with `RCFC`. Keep the explicit input geometry equal to that frequency calculation's final TS. An optimization-only checkpoint does not supply the frequency Hessian required by `RCFC`.

## Establish the connections and retain results

Read `Summary of reaction path following` in the IRC log. Its central TS has zero relative energy and reaction coordinate. Inspect structures on both sides; forward and reverse are defined by the transition vector's phase, not by the names “reactant” and “product.”

Take the final structure from each direction into a separate complete input deck, retaining the same model, and run `Opt Freq` as above. Compare the resulting minima with the independently optimized proposed reactant and product using atom mapping, connectivity and geometry. A path that reaches a different minimum establishes a different connection. If the path stops before the structures can be assigned, report connectivity as unresolved; the documented `IRC=Restart` option can extend a saved path.

Retain the optimized structures, logs and checkpoints. Report the imaginary-mode count and mode identity for each stationary point, the structures reached in each IRC direction, and any unresolved endpoints. IRC energies describe the computed path; they are not automatically activation Gibbs free energies.

An error-terminated job or missing optimization/frequency/path sections is incomplete evidence. Check the actual log: [NIH's error guide](https://helixweb.nih.gov/apps/Gaussian.html) distinguishes syntax, memory, scratch permission and disk-space failures. Use the [Opt reference](https://gaussian.com/opt/) for convergence controls and the [IRC reference](https://gaussian.com/irc/) for restart and path options.
