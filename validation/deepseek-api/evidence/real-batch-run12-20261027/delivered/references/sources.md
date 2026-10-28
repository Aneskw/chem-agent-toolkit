# Source and attribution

The adapter directly invokes installed RDKit; it does not contain a reimplementation of RECAP. Its input checks and JSON output are mechanical glue.

Inspected implementation: `rdkit/Chem/Recap.py`, RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`.

Original source (download/read when auditing the implementation; this single module is not a standalone RDKit installation):
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py

SHA-256: `d4f9b96945c2c92c095d758a7f460360dc1a73fb75831bfdb8482f8f9aaec3fc`.

Relevant passages in that source:

- Lines 31-56: module overview attributes the algorithm to Lewell et al., JCICS 38, 511-522 (1998), and demonstrates parsing, decomposition, immediate children, all descendants, terminal leaves, and `leaf.mol`. The three-leaf example in SKILL.md comes from this passage.
- Lines 66-86: reaction SMARTS introduce dummy atoms at cleavage points. Lines 81-82 mark aromatic nitrogen-aromatic carbon cleavage as outside the standard RECAP set.
- Lines 102-118 and 134-138: `GetAllChildren` and `GetLeaves` traversal. Leaves are SMILES-keyed terminal descendants; a root without children yields an empty dictionary.
- Lines 146-158 and 197-213: input molecule conversion and SMILES-keyed node reuse. Omitting `allNodes` gives a fresh dictionary.
- Lines 180-195: product sanitization and filtering. At the default size setting, removing `*` and empty branches from a product SMILES leads to rejection if the result is empty, C, CC, or CCC. A positive minimum size instead counts explicit atoms minus dummy atoms; it is not merely an additional filter layered on the defaults.
- Lines 223-235: tests confirm the overview counts and the empty children of `CCCOCCC`. Lines 279-302 show size-dependent outcomes, including one unique `*CCC` leaf for `CCCOCCC` when `minFragmentSize=3`.

The original paper has not been inspected here. The behavior described is the supplied RDKit implementation, not an independently verified reproduction of the publication.

License source:
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/license.txt

SHA-256: `daeb8d194502cbcf34c05c39541a0d02be65bc9bada5b891c1974cd24e9fca30`.

The repository BSD 3-Clause license and the module's Novartis notice are retained in LICENSE.txt.
