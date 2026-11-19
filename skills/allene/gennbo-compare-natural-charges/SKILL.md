---
name: gennbo-compare-natural-charges
description: Use GenNBO to extract and compare natural atomic charges at corresponding sites from prepared NBO wavefunction archives (.47), including comparisons of allene carbons.
---

# Compare natural atomic charges with GenNBO

Analyze existing wavefunctions without recomputing them. Start with valid FILE47 archives and a mapping from chemically corresponding sites to each archive's atom numbers. Geometry optimization, wavefunction generation and transition-state calculations are upstream tasks. Natural charges describe charge distribution; they do not establish reaction barriers or selectivity by themselves.

## Setup and inputs

Use **NBO 7.0.10**, including its standalone GenNBO front end. Obtain a licensed distribution through the [official NBO product and ordering page](https://nbo7.chem.wisc.edu/products_css.htm). Follow the installation instructions supplied with the distribution to configure its launcher and executables. Windows distributions include `gennbo.bat`; Unix distributions include `gennbo` and `gennbo.sh`. The examples below use the configured `gennbo` launcher, available on the command search path. The NBO slave executable alone is not this launcher.

| Input | Required preparation |
| --- | --- |
| One `.47` archive per structure | Supply the computed wavefunction, not just coordinates. For ordinary standalone input, FILE47 contains `$GENNBO`, `$COORD`, `$BASIS`, `$DENSITY` and `$OVERLAP` lists. Keep the original archive intact. |
| Site mapping | Identify each requested site by its atom number in that archive. Corresponding sites need not have identical numbers in different structures. |
| Calculation context | Retain the geometry, electronic method, basis, solvent treatment, charge and spin information used upstream so differences in preparation remain visible in the comparison. |

See the [NBO manual](https://nbo7.chem.wisc.edu/nboman.pdf), A.2 for setup and B.7 for FILE47 details if an archive is incomplete. Do not construct missing density or basis data from coordinates.

## Analyze two prepared archives

For example, compare two supplied structures using working copies named `substrate_a.47` and `substrate_b.47` in one working directory. Use a separate directory for a fresh analysis so its output names do not collide with earlier results.

In each working copy, replace the existing `$NBO ... $END` analysis keylist with:

```text
$NBO NPA=ONLY $END
```

If the archive has no `$NBO` keylist, add this one. Preserve the other keylists and numerical data. `NPA=ONLY` requests natural population analysis and suppresses conflicting requests for other analyses; it is not an instruction to regenerate the wavefunction.

From the directory containing those archives, invoke the distribution's launcher with the filename stem, without `.47`:

```text
gennbo substrate_a
gennbo substrate_b
```

Read the resulting `substrate_a.nbo` and `substrate_b.nbo` files in that directory. This stem-to-output convention is documented in the [official FAQ, Q3](https://nbo7.chem.wisc.edu/faq_css.htm).

## Read and compare the results

In each `.nbo` file, locate **Summary of Natural Population Analysis**. Match the requested atom numbers and element symbols, then read the **Natural Charge** column. This is distinct from the per-orbital NAO occupancy table and from the Core, Valence, Rydberg and Total electron-population columns.

Natural charge is nuclear charge minus the summed natural populations on that atom, in units of elementary charge: positive means an electron deficit and negative means an electron excess relative to the nuclear charge. Preserve the upstream treatment of effective core potentials when present; do not edit nuclear charges in the archive.

Return a comparison table with `structure`, `site`, `Atom No` and `Natural Charge (e)`. For an allene comparison, use the supplied mapping to report the internal and terminal carbon sites in each structure. Record differences in upstream calculation settings alongside the table rather than attributing every charge difference to the substituent change.

Check that the charge in the summary's `* Total *` row agrees with the intended molecular charge, allowing for printed rounding. A missing output file, absent summary, or missing requested atom row is an incomplete result, not a zero charge. Inspect the output diagnostics and archive preparation before interpreting it. A reported **population inversion** refers to a disagreement between NAO occupancy and energy ordering; the manual notes that this can occur without being a calculation failure. See manual A.3.2 for the output definitions.

If population components are requested, retain **Core, Valence, Rydberg and Total** electron populations from the same summary row, separately from Natural Charge. Nonphysical-occupancy warnings can indicate an unreliable upstream density; `FIXDM` does not repair a nonconvergent perturbation expansion. Consult the [official FAQ, Q8](https://nbo7.chem.wisc.edu/faq_css.htm) and return that issue to the density-producing calculation.
