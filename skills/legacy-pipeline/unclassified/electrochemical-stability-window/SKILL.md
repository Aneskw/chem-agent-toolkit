---
name: electrochemical-stability-window
description: "Derive intrinsic reduction and oxidation limits against a declared electrode reference. Invoke for: solid-electrolyte stability-window estimates; not for inferring interfacial passivation behavior from intrinsic energies alone."
license: MIT
---



# Electrochemical Stability Window

## Applicability

Use for thermodynamic decomposition limits under changing lithium chemical potential. Distinguish intrinsic bulk stability from kinetic or passivation-controlled operating windows.


## Reference

[Electrochemical-window task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/electrochemical-window/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/materials-science/electrochemical-window/tests/test_outputs.py).

## Input & Output

Input: electrolyte composition/structure, compatible competing-phase energies, Li reference and voltage convention. Output: reduction limit, oxidation limit, window width, decomposition products and assumptions.

## Procedure Guidance

Construct competing reaction products on the same energy scale as the target. Sweep Li chemical potential or use a grand-potential phase diagram to identify the first favorable reduction and oxidation decompositions. Convert chemical-potential thresholds to voltage relative to the stated Li/Li+ reference with a checked sign convention. If the calculated oxidation limit falls below the reduction limit, report no intrinsic stability window instead of a negative width disguised as stable. Keep interface reactions and passivation as separate questions.

## Success Criteria

Both limits derive from identified reactions and one reference scale; window width and stable flag follow the reported limits.

## Matters & Troubleshooting

An incomplete phase diagram, inconsistent elemental reference, or model error can shift the apparent window markedly.


## Required calculation and voltage convention

Use an existing compatible phase-diagram/grand-potential calculator, or supplied transition chemical potentials and their decomposition reactions. This Skill guides the analysis; it does not supply a phase-energy database or sweep implementation. Freeze phase coverage and energy normalization before interpreting thresholds.

For Li chemical potentials in eV per Li atom, use `V_vs_Li = mu_Li_metal - mu_Li` numerically in volts. Increasing voltage lowers the Li chemical potential. Convert the two transitions first, then identify the lower reduction and upper oxidation voltage from their reactions. Window width is `V_oxidation - V_reduction` only when that interval is thermodynamically stable. For other charge carriers, account for their electron stoichiometry instead of reusing the Li formula.

Source for available phase-diagram operations: [pymatgen phase diagrams](https://pymatgen.org/pymatgen.analysis).
