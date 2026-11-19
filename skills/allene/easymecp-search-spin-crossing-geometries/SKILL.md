---
name: easymecp-search-spin-crossing-geometries
description: Locate a minimum-energy crossing between two selected spin states using EasyMECP and Gaussian, starting from a crossing-region geometry; inspect convergence and restart an unfinished search.
---

# Spin-surface crossing searches with EasyMECP

EasyMECP couples Harvey's Fortran optimizer to repeated Gaussian energy/force calculations on two electronic states. Supply the states and a chemically selected starting geometry near the crossing region. The result is a local crossing-search outcome under the supplied electronic-structure model; this workflow does not select states or calculate hopping probabilities, rates, or validated crossing-point thermochemistry.

## Prepare the software and working directory

Use **EasyMECP v0.3.2**, commit `be02e0557a27b3178479c3ade1f110e7e96b24cf`. Download the self-contained [easymecp.py](https://raw.githubusercontent.com/jaimergp/easymecp/v0.3.2/easymecp/easymecp.py); no package installation is needed. The [tagged README](https://github.com/jaimergp/easymecp/blob/v0.3.2/README.md) documents additional modes.

Provide:

- **Python 3.11**, obtainable from [Python's source releases](https://www.python.org/downloads/source/). The script imports `distutils`, which Python 3.12 removed; use a 3.11 interpreter that includes it. In commands below, `python3.11` denotes that interpreter.
- **gfortran**, available through [GNU Fortran](https://gcc.gnu.org/fortran/), on `PATH`. EasyMECP compiles its embedded Fortran for each calculation. Defaults are `FC=gfortran` and `FFLAGS='-O -ffixed-line-length-none'`, with environment overrides; `--FC` and `--FFLAGS` can specify alternatives.
- **Licensed Gaussian 16 Rev. C.02**, obtained through [Gaussian](https://gaussian.com/) or an authorized institutional installation, with the site's Gaussian runtime and scratch environment initialized. Use a platform in the [official C.02 platform table](https://gaussian.com/g16/g16_plat.pdf), for example a supported AVX2 Linux system. The wrapper must be able to call `g16 input.gjf` and find the sibling `input.log`. `--gaussian_exe` accepts an executable name or absolute path.

Work in a dedicated writable calculation directory containing the downloaded script and input. Files are created relative to the current directory. Each run creates `JOBS` (or `JOBS1`, `JOBS2`, ...), but overwrites working files including `ReportFile`, `ProgFile`, and generated fragments. Archive an earlier run before restarting.

## Prepare the two-state input

The normal path uses one Gaussian deck, `system.gjf`, with shared Cartesian coordinates in angstroms and a shared model chemistry. Supply the molecular charge, two multiplicities, and any required basis/ECP/solvent sections. Preserve ordinary Gaussian blank-line section boundaries and a terminating blank line. Use one `{A,B}` pair per differing header line, with no spaces inside the pair; the first entry always maps to state A.

| Field | Required treatment |
| --- | --- |
| `%chk={singlet,triplet}.chk` | Separate checkpoints for the two surfaces; names are labels, not state validation. |
| Route | Include `force` on the `#` route line. The example uses the default `dft` energy parser, which reads `SCF Done:` energies. |
| Charge/multiplicity | Example `1 {1,3}` means charge +1, A singlet and B triplet. Adapt to the selected system. |
| Geometry | Element symbol or atomic number followed by x, y, z; same atom order for both states. No XYZ atom-count/comment lines. |
| Footer | Place basis/ECP or other required trailing sections after the geometry's blank line. |
| `guess(read)` | Reuses existing state checkpoints. At step zero the wrapper removes the read option if the named checkpoint is absent; a required electronic guess must therefore be supplied explicitly as an external input. |

The following complete deck is adapted from the upstream phenyl-cation example. It illustrates the format and resource choices, not a validated crossing or a model for another molecule. For a real search replace its coordinates, charge/multiplicities, route and footer with the prepared crossing-region inputs.

```text
! easymecp: max_steps=100
%mem=6GB
%nproc=4
%chk={singlet,triplet}.chk
#n B3LYP/6-31G** force guess(read)

{Singlet,Triplet} State

1 {1,3}
C    0.00000000    1.29390795    0.00000000
C    1.26894294    0.69491769    0.00000000
C    1.25319073   -0.68704191    0.00000000
C    0.00000000   -1.37652121    0.00000000
C   -1.25319073   -0.68704191    0.00000000
C   -1.26894294    0.69491769    0.00000000
H    2.18616903    1.27569862    0.00000000
H    2.18025862   -1.25246238    0.00000000
H    0.00000000   -2.46323577    0.00000000
H   -2.18025862   -1.25246238    0.00000000
H   -2.18616903    1.27569862    0.00000000

```
## Run and inspect the result

From the calculation directory, run:

```bash
python3.11 easymecp.py -f system.gjf --gaussian_exe g16 > search.out 2>&1
```

The single-file parser writes `_header_a`, `_header_b`, `_initial_geom`, `_footer` when nonempty, and `system.conf`. It then compiles `MECP.x` and alternates two Gaussian force jobs with optimizer updates. The example raises the default step limit of 50 to 100; it does not change convergence tolerances.

| Criterion | v0.3.2 default | Meaning/units |
| --- | --- | --- |
| `TDE` | `5.d-5` | Absolute difference of the state energies, Hartree |
| `TDXMax`, `TDXRMS` | `4.d-3`, `2.5d-3` | Maximum and RMS Cartesian displacement, angstrom |
| `TGMax`, `TGRMS` | `7.d-4`, `5.d-4` | Maximum and RMS overall effective gradient, Hartree/angstrom |

All five criteria must pass; a small energy gap alone is insufficient. If deliberately changing tolerances, use Fortran double notation, e.g. `! easymecp: TDE=5.d-5` in the deck. These are optimizer thresholds, distinct from Gaussian SCF convergence.

Inspect these files together:

- **`search.out` and `ReportFile`:** success prints `Success! Check ReportFile for results.` and the report contains `The MECP Optimization has CONVERGED at that geometry !!!`. Read both state energies and the five actual-value/threshold/status entries. Energies are electronic energies in Hartree.
- **`JOBS/JobN_A.gjf`, `JobN_B.gjf`, and matching `.log` files:** N is the zero-based step. The final evaluated pair identifies the geometry associated with the final reported energies and allows inspection of each electronic calculation. Successful Gaussian jobs are moved into the run's `JOBS*` folder, including the final pair. Failed jobs can remain in the working directory.
- **`JOBS/trajectory.xyz`:** view the evolving geometry with an XYZ-capable viewer. It includes the initial geometry and optimizer updates; use the final evaluated Gaussian inputs to associate a structure with energies, rather than assuming every trajectory frame has been evaluated.
- **`geom`:** optimizer-generated coordinates, useful for restarting after an unconverged step. At a step-limit stop this can be the next proposed geometry, not the last geometry with calculated energies. Immediate convergence at step zero need not create it.

`Calculation did not converge after ... steps...` is an unfinished search, not a crossing result. `Something failed...`, `ERROR`, SCF `Convergence failure`, missing energies/forces, or missing logs require inspection of both Gaussian outputs and `ReportFile`. For compiler failures also inspect `_fortran_compilation` and terminal output. Do not use the process exit status alone as a success test: the CLI prints failure/nonconvergence messages without consistently returning a nonzero exit code.

Check that each calculation represents the intended electronic state before interpreting the crossing. Optimizer convergence establishes its numerical criteria for those surfaces; it does not establish a unique/global crossing or experimental spin kinetics. Return the geometry from the converged evaluated pair, state definitions/model chemistry, both energies and their gap, convergence status/criteria, and paths to the report, logs and trajectory. If unfinished, return that status and restart geometry instead of labeling it an MECP.

## Restart an unfinished search

Archive the working directory's records, especially `ReportFile`, generated fragments/configuration, checkpoints, and `geom`. Restarting initializes a new optimization from a geometry; it does not resume the previous inverse-Hessian history in `ProgFile`.

Either replace the geometry in `system.gjf` and rerun the normal command, or reuse the actual fragments created by single-file mode:

```bash
python3.11 easymecp.py --a_header _header_a --b_header _header_b --footer _footer --geom geom --max_steps 100 --gaussian_exe g16 > restart.out 2>&1
```

Use that command only when `geom` exists and is the intended restart geometry. If there was no footer, omit `--footer _footer`. Keep the same state/checkpoint mapping. The new calculation writes into the next unused `JOBS*` directory, while replacing `ReportFile`. Diagnose calculation failures or an unsuitable starting structure before simply extending the step count.

If an `ExtraOverlays` section is required before the title, the single-file parser is unsuitable. Use the [documented fragmented-input mode](https://github.com/jaimergp/easymecp/blob/v0.3.2/README.md#backward-compatibility-with-old-mecp-workflow): supply separate state headers through `--a_header`/`--b_header`, a coordinate-only `--geom`, and an optional `--footer`.
