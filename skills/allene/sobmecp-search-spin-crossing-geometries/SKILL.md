---
name: sobmecp-search-spin-crossing-geometries
description: Search minimum-energy crossing geometries between two electronic spin states with sobMECP and Gaussian, starting from a crossing-region geometry and specified electronic states.
---

# Search spin-state crossing geometries with sobMECP

Use an informed starting geometry, two state definitions, and an electronic-structure method to locate a local minimum-energy crossing point (MECP). The initial geometry determines which crossing region is reached. This workflow does not discover a reaction network or compute spin-transition probabilities.

## Obtain and prepare the tools

Use Linux with **Gaussian 16 revision C.02**, licensed and configured so `g16` works in the working shell. Obtain Gaussian through [Gaussian, Inc.](https://gaussian.com/) or an institutional license; use the official [installation instructions](https://gaussian.com/techsupport#install) and [platform requirements](https://gaussian.com/g16/g16_plat.pdf) to select a compatible build. The C.02 AMD/Intel Linux binary requires AVX2. Configure the Gaussian environment and writable scratch using the installation instructions or the site's module setup.

Download [sobMECP.zip](https://sobereva.com/soft/sobMECP.zip) from the [official guide](https://sobereva.com/286). This skill targets the archive with SHA256:

```text
c74f6a68abb6e199eccd028df12fbcbc5e577f96cb5ee9d6f4f2ce785bd36409
```

Check the downloaded archive with `sha256sum sobMECP.zip`; if the digest differs, inspect the updated guide and scripts before using this interface. Extract a fresh copy for each search, and work inside its `sobMECP` directory. Required command-line tools are `gfortran`, `/bin/csh`, and the ordinary Linux shell utilities used by the scripts (`awk`, `sed`, `grep`, `wc`). GNU Fortran is available through the Linux distribution or [GCC's official Fortran project](https://gcc.gnu.org/fortran/). `prepare.sh` compiles the optimizer; no prebuilt optimizer is needed.

**Use a dedicated working directory.** `prepare.sh` removes `*.chk`, `*.gjf`, `*.log`, `ab_initio`, `ReportFile`, `traj.xyz`, and the entire `JOBS` directory, and resets optimizer progress. Copy anything needed from a previous search elsewhere first.

## Prepare the two states and geometry

Required files are relative to the working directory:

| File | Contract |
| --- | --- |
| `Input_Header_A`, `Input_Header_B` | Gaussian input before the coordinates: resource directives, a distinct `%chk` for each state, `#n` route, title, charge and multiplicity. Include `force guess(read)`. End with a newline after charge/multiplicity, without a trailing blank line. |
| `geom` | One `atomic_number x y z` row per atom, Cartesian coordinates in angstroms; same atom order for both states. No XYZ count or comment lines. End with a blank line. |
| `Input_Tail` | Empty for a built-in basis; for `gen`/`genECP`, supply normal Gaussian basis/ECP definitions and required blank separators after the geometry. |
| `extract_energy` | The supplied default extracts HF/DFT SCF energies. Match this parser to the method before running. |

Here is the official guide's small CH2 singlet/triplet example, adapted into file-writing commands. It illustrates the complete path; replace its geometry, method, charge, multiplicities, and resources with those chosen for the actual system. The supplied archive's root example headers have different settings, so overwrite them explicitly.

Run these commands from the extracted working directory in Bash:

```bash
cat > Input_Header_A <<'EOF'
%mem=6GB
%nproc=4
%chk=singlet.chk
#n B3LYP/6-311G** force guess(read)

First State

0 1
EOF
cat > Input_Header_B <<'EOF'
%mem=6GB
%nproc=4
%chk=triplet.chk
#n B3LYP/6-311G** force guess(read)

Second State

0 3
EOF
cat > geom <<'EOF'
6   0.00000000   0.00000000   0.13397933
1   0.00000000  -0.92611695  -0.40193800
1  -0.00000000   0.92611695  -0.40193800

EOF
: > Input_Tail
cp temp/extract_energy_SCF extract_energy
cp geom geom_initial
```

For another supported method, use the corresponding `temp/extract_energy_MP2`, `extract_energy_CIS`, or `extract_energy_TD` as `extract_energy`. If the methods differ between states, provide a second parser named `extract_energy2` for B; otherwise B reuses A's parser. Remove any stale `extract_energy2` when both states should use the same parser. Excited-state definitions and state tracking require the method-specific choices described in guide sections 2.2 and 3.4; the example above uses ground-state DFT calculations for each multiplicity.

## Initialize and search

```bash
chmod +x prepare.sh runfirst.sh sub_script temp/runMECP.sh
./prepare.sh
# Confirm MECP.x was created successfully before proceeding.
./runfirst.sh
# Inspect Job0_A.log and Job0_B.log for successful Gaussian termination.
# Confirm singlet.chk and triplet.chk exist for the example above.
./runMECP.sh
```

`runfirst.sh` builds the two initial Gaussian jobs and strips `guess(read)` from these first jobs to create the checkpoints. Subsequent steps retain `guess(read)` to reuse each state's wavefunction. Check initial logs before iteration: shell completion alone does not establish that Gaussian succeeded.

The optimizer updates `geom`, `ab_initio`, and `ProgFile` during the search. Inspect the results with ordinary file tools:

```bash
tail -n 60 ReportFile
cat ab_initio
cat geom
ls JOBS
```

| Output | Use |
| --- | --- |
| `ReportFile` | Step energies, convergence checks, geometry and effective/difference/parallel gradients; require the final `CONVERGED` message and all five checks marked `YES`. |
| `geom` | Current coordinates; the converged crossing geometry only after successful convergence. Copy it to a separately named result file. |
| `ab_initio` | Most recently extracted A/B energies in hartree and Gaussian forces in hartree/bohr under labels saying `Gradient`. The optimizer internally reverses the force sign and converts to hartree/angstrom. |
| `ProgFile` | Optimizer progress and history state, rather than the human-readable convergence report. |
| `traj.xyz` | Search geometries, beginning with the initial geometry; inspect structural changes over the search. |
| `JOBS/JobN_A.gjf`, `JOBS/JobN_B.gjf`, and matching `.log` files | Per-step inputs/outputs, including step 0 after iteration starts; inspect SCF convergence, spin and intended electronic states. |

The pinned optimizer's default criteria are:

| Check | Strict upper threshold |
| --- | --- |
| Absolute A/B energy gap | `5e-5` hartree |
| Maximum / RMS displacement | `4e-3` / `2.5e-3` angstrom |
| Maximum / RMS effective gradient | `7e-4` / `5e-4` hartree/angstrom |

A small energy gap alone is insufficient: the effective-gradient and displacement tests must also pass. Interpret the result as a local crossing geometry on the chosen electronic surfaces. It does not establish a global minimum on the crossing seam. Ordinary Gaussian `freq=projected` is not a generally valid route to MECP free energies; the guide's section 4 explains that boundary.

## Failure and restart

`runMECP.sh` defaults to 100 iterations. Reaching that limit without `CONVERGED` leaves an unconverged geometry. Messages such as `First Input Missing`, `ProgFile missing`, `ERROR`, `Problem with Fortran program`, or Gaussian convergence failures require inspection of the affected job logs and input/parser choices. The wrapper explicitly catches some failures, but its exit status alone does not certify success.

For an interrupted search, preserve the current `geom` and any wanted diagnostics outside the working directory, then rerun `prepare.sh`, `runfirst.sh`, and `runMECP.sh` in order. This restarts from the last saved geometry with fresh initialization; it does not preserve the previous optimizer history.

If needed, edit convergence thresholds in `temp/MECP.f` (`TestConvergence`, `PARAMETER`), or the iteration limit in `temp/runMECP.sh`, then rerun preparation. Record such changes with the result. For oscillation, first inspect the geometry and electronic-state behavior; guide section 2.2 discusses the `STPMX` step-size control as an optional, not established universal, remedy. Nearly parallel surfaces can defeat this optimizer, as illustrated in guide section 3.2; failure to converge does not prove absence of a crossing.
