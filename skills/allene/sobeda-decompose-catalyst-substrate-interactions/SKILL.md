---
name: sobeda-decompose-catalyst-substrate-interactions
description: Use sobEDA with Gaussian and Multiwfn to decompose fixed-geometry catalyst–substrate interaction energies and combine them with separately prepared distortion energies for activation-strain comparisons.
---

# Fragment interaction and distortion energies with sobEDA

## Obtain the tools

Use Linux (including WSL), licensed **Gaussian 16 C.02**, **Multiwfn 2026.11.10**, and **dos2unix**. Gaussian's `g16`, `formchk`, and `unfchk` must resolve in the job environment. Obtain Gaussian through [Gaussian's official site](https://gaussian.com/) and its [C.02 platform list](https://gaussian.com/g16/g16_plat.pdf). Obtain the Linux noGUI Multiwfn build from the [official download page](https://sobereva.com/multiwfn/download.html) and follow the [Linux setup instructions](https://sobereva.com/688). The script also calls standard shell utilities and `bc`.

Download and unpack the [official sobEDA tutorial archive](https://sobereva.com/soft/sobEDA_tutorial.zip), linked by the [usage guide](https://sobereva.com/685). Use **the root `sobEDA_tutorial/sobEDA.sh`, updated 2026-Aug-26**, rather than the older script copies in example directories. Its SHA256 is:
```text
4097eaf0a708388844ba07c54d8f533b6deaf6812020f8fb7b8136334c2c9f78
```

## Prepare the calculation

Start with the complex geometry, an explicit fragment partition and electronic states, and a chosen DFT functional/basis. Geometry optimization and optimized isolated-fragment reference energies are external preparation. sobEDA evaluates vacuum electronic interaction energy at the supplied geometry; distortion, solvent and thermal/free-energy corrections require separate calculations.

Use sobEDA (`sobEDAw=0`) for chemical bonding or mixed strong/weak interactions. This Gaussian implementation excludes range-separated functionals and double hybrids. Do not put solvent keywords, `scf=QC`, `scf=XQC`, or an overriding guess such as `guess=AM1` in the template.

Keep each calculation in its own directory: generated files have fixed names and rerunning overwrites them.

| File | Required content |
|---|---|
| `system.xyz` | Full complex: atom count, comment line, then element and Cartesian coordinates, as in the tutorial XYZ files. Preserve atom order. |
| `fragment.txt` | First line: fragment count. For each fragment, two lines: charge and multiplicity, then a comma-separated atom list supporting ranges such as `1-3,7,10-12`. Indices start at 1 for the first atom, excluding XYZ header lines. Assign all atoms to the intended fragments without overlap. |
| `template.gjf` | Gaussian single-point template with literal `[geometry]`, whole-complex charge/multiplicity, `#p`, `nosymm`, `ExtraLinks=L608`, and the functional-specific trailing Link 608 input. Fragment states come from `fragment.txt`. |

A negative multiplicity in `fragment.txt` requests beta unpaired electrons for that fragment (e.g. `0 -3` for a neutral triplet with flipped spin). Choose spin flips so the sums of fragment alpha and beta electron counts match the whole complex. The script uses unrestricted calculations when any fragment is open-shell.

Edit the copied root script's settings:

| Setting | Meaning |
|---|---|
| `gau="g16"`, `mwfn="Multiwfn_noGUI"` | Actual commands available on the machine; change if needed. |
| `sobEDAw=0` | Report sobEDA; no fitted sobEDAw parameters are needed. |
| `iCP=0` | Default: fragments use their own basis. Appropriate normal path for the bonded example below. `1` uses the complete complex basis for fragments, giving counterpoise-corrected results; the guide recommends it for weak interactions. Record this choice. |
| `irun=1` | Perform Gaussian calculations. `0` only processes existing calculation files; it is not a fresh run. |
| `idetail=0` | Normal summary. `1` adds a separate frozen-state calculation and stage-by-stage details. |

## Run a complete example

This example uses the archive's prepared (CO)5Cr=CH2 geometry, with neutral singlet Cr(CO)5 and CH2 fragments. These are tutorial choices; for another catalyst–substrate complex, replace the geometry, partition, states and electronic-structure specification together.

From the directory containing the unpacked `sobEDA_tutorial` folder:

```bash
mkdir cr-ch2-eda
cp sobEDA_tutorial/sobEDA.sh cr-ch2-eda/
cp 'sobEDA_tutorial/(CO)5CrCH2/system.xyz' cr-ch2-eda/
cd cr-ch2-eda
cat > fragment.txt <<'EOF'
2
0 1
1-11
0 1
12-14
EOF
```

Create `template.gjf` as below. The resource choices (8 cores, 8 GB) are illustrative; adjust to the allocation. Preserve blank lines, the element-prefixed minus signs in the mixed basis/ECP specification, and the trailing `-35 5`. TPSSh-D3(BJ) requires these explicit dispersion parameters in Gaussian C.02.

```text
%nprocshared=8
%mem=8GB
#p TPSSh/genecp em=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) ExtraLinks=L608 nosymm

Cr carbene interaction

0 1
[geometry]

-Cr
SDD
****
-C -H -O
6-311G*
****

-Cr
SDD

-35 5


```

End the file with two blank lines. `-35` identifies TPSSh for Link 608; `5` requests the ultrafine integration grid used by Gaussian 16's default SCF. If changing the functional, also change its Link 608 identifier and any explicit dispersion parameters. Use the archive's `templates/` examples and guide §3.6; do not keep TPSSh's numbers for a different functional.

After editing the script settings above, launch in Bash:

```bash
dos2unix sobEDA.sh template.gjf fragment.txt system.xyz
chmod +x sobEDA.sh
set -o pipefail
./sobEDA.sh 2>&1 | tee result.txt
```

Read the final summary and inspect the retained Gaussian files:

```bash
sed -n '/Final results/,$p' result.txt
tail -n 20 final.out
```

## Read and retain the results

The `Final results` block reports interaction energy and components in **kcal/mol**; earlier absolute energies are in **Hartree**. The script uses 627.51 kcal/mol per Hartree. Negative interaction energy means stabilization relative to the chosen fragments at the complex geometry.

Use one nonredundant sum:
```text
E_int = E_els + E_x + E_rep + E_orb + E_DFTc + E_dc
      = E_els + E_xrep + E_orb + E_c
E_xrep = E_x + E_rep
E_c    = E_DFTc + E_dc
```

Do not add the combined rows again to their constituents. Without an explicit dispersion correction, `E_dc` is zero. With TPSSh-D3(BJ), retain `E_dc` separately from DFT correlation; the correction alone is not a universal measure of all dispersion attraction.

Archive the input files, configured script and `result.txt`, together with `fragmentN.gjf/out/fch`, `promol.gjf/out/chk/fch`, and `final.gjf/out/chk` (plus frozen-state files when requested). Fragment binary `.chk` files are converted to `.fch` and deleted by the script. The retained wavefunctions and energies permit checking the electronic states actually obtained.

A missing final block, empty/nonnumeric components, conversion failure, or Gaussian error is a failed decomposition. Inspect the named `.out` file and the stage reported in `result.txt`. Fragment and final-state calculations require SCF convergence; the promolecular calculation intentionally suppresses SCF iteration. Gaussian failures cause the script to exit, but not every intermediate utility failure is checked, so exit status alone is insufficient. For conversion-memory failures, the script's `GAUSS_MEMDEF=4GB` may need increasing. For total-energy discrepancies, compare geometry, states, functional/basis, grid, dispersion and counterpoise settings, then check whether the same wavefunctions were reached.

## Add separately calculated distortion energies

For each fragment i, obtain an optimized isolated reference energy E_i(opt) and a single-point energy E_i(deformed) at its geometry extracted unchanged from the complex. Use consistent charge, spin, functional, basis/ECP, dispersion and integration settings. The own-basis fragment energies in an `iCP=0` run can supply the deformed energies when their states and settings match those references; they are not optimized fragment energies.

```text
E_distort,i = E_i(deformed) - E_i(opt)
E_distort   = sum_i E_distort,i
Delta E    = E_distort + E_int
```

Convert Hartree differences to the same units before adding the terms. For a transition-state complex and its optimized reactants, this gives the electronic activation-strain comparison. Counterpoise changes the reference convention: do not substitute complex-basis fragment energies from `iCP=1` for own-basis distortion energies and claim an uncorrected electronic barrier. Keep the chosen convention explicit.

Report the geometry, fragment definitions/states, computational level, counterpoise choice, components and distortion references. Free-energy barriers need separate thermochemical and solvent contributions. For method details and publication attribution, use the [sobEDA guide and original-method reference](https://sobereva.com/685) and [Multiwfn citation requirements](https://sobereva.com/multiwfn/download.html).
