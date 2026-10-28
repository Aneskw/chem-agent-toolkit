# Source and provenance

The wrapper directly calls RDKit; it does not copy or modify reaction definitions.

Source baseline: RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8`.
Acquire or inspect the original module at this fixed address:
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py

Module SHA-256: `d4f9b96945c2c92c095d758a7f460360dc1a73fb75831bfdb8482f8f9aaec3fc`.
The source calls the method an implementation of Lewell et al., JCICS 38, 511-522 (1998). The original paper was not inspected, and no claim of paper-level validation is made.

Relevant inspected passages in that module:

- Lines 31-56: overview and example, with four immediate children, five descendants, three terminal SMILES, and access through leaf.mol.
- Lines 63-86: required RDKit modules and reactions, including the explicitly nonstandard aromatic nitrogen-aromatic carbon rule.
- Lines 102-138: GetAllChildren, GetLeaves and recursive traversal. SMILES keys deduplicate nodes; GetLeaves does not include the root.
- Lines 146-213: RecapDecompose, independent default node dictionary, SMILES-based reuse, product processing and fragment filters.
- Lines 223-235: test1 and test2 assert hierarchy counts and a valid empty children dictionary for CCCOCCC.
- Lines 279-293: size-filter examples distinguish default behavior from positive minFragmentSize. Defaults are retained by this package.

The installed version is reported by the CLI. No supported release range has been experimentally established. Match the source-derived examples in the actual runtime before relying on compatibility. The checks establish software behavior only, not chemical adequacy.

License source:
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/license.txt

License SHA-256: `daeb8d194502cbcf34c05c39541a0d02be65bc9bada5b891c1974cd24e9fca30`.
The adjacent LICENSE.txt retains both the module notice and the repository BSD license.