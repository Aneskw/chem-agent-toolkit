# Source and interpretation

Grounded in RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`:

- [Recap.py original source](https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py)
- [Repository license](https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/license.txt)

The implementation link identifies the acquisition location for the exact source; use the existing RDKit installation at runtime, not a downloaded standalone module. No RDKit release number is inferred from the commit.

Inspected passages in Recap.py:

- Lines 31-56: module overview cites Lewell et al., JCICS 38, 511-522 (1998). Its example shows four immediate children, five descendants and three terminal leaves; each leaf exposes `.mol`. The paper itself was not inspected.
- Lines 97-118, 134-138: nodes store children in dictionaries. `GetLeaves` starts from children and recursively includes terminal descendants, never the root itself. Dictionary keys establish uniqueness, not occurrence counts.
- Lines 146-169, 197-213: `RecapDecompose` accepts a molecule, serializes it with `Chem.MolToSmiles`, and iteratively applies reactions. An optional shared `allNodes` dictionary can return a pre-existing root early; fresh default state avoids that interaction.
- Lines 180-195: the default filter rejects a product sequence if a product SMILES, after removing dummy markers and empty branches, equals empty, C, CC or CCC. Positive `minFragmentSize` uses an alternative filter counting explicit atoms minus dummy atoms. It is not simply an extra restriction layered over the defaults.
- Tests `test1` (223-229), `test2` (231-235) and `testMinFragmentSize` (279-302): the overview example has three terminal leaves; `CCCOCCC` has no children by default but yields unique `*CCC` with `minFragmentSize=3`. The shipped entry deliberately keeps defaults.
- Lines 66-86: reaction SMARTS produce dummy attachment atoms. Lines 81-82 explicitly identify the aromatic nitrogen/aromatic carbon rule as outside the standard RECAP set.

The wrapper adds only nonempty-input guards and sorted JSON serialization. Parser rejection is not a chemical validity test. No published algorithm changes, chemical thresholds, standardization or automatic reaction customization are added. The tests proposed in delivery metadata were not executed during authoring.

BSD redistribution terms appear both in the module header (lines 1-29) and the repository license. They are retained in [LICENSE.txt](LICENSE.txt).
