# Source and interpretation

The reference implementation is RDKit `rdkit/Chem/Recap.py` at commit
`237a1d9027c800784afed8788540f38a3aa595f8`:
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py

Its SHA-256 is `d4f9b96945c2c92c095d758a7f460360dc1a73fb75831bfdb8482f8f9aaec3fc`.
The module identifies the method as Lewell et al., JCICS 38, 511-522 (1998).
This package wraps installed RDKit; it does not vendor or reimplement that module.

Inspected source passages supporting the workflow:

- Lines 31-56: overview and worked example; the normal example has three terminal SMILES, four immediate children and five total descendants. Each leaf exposes `.mol`.
- Lines 97-118 and 134-138: `GetLeaves()` constructs a SMILES-keyed dictionary from terminal descendants. It excludes the root itself; no children means an empty dictionary.
- Lines 146-169 and 197-213: `RecapDecompose` accepts a molecule, initializes a root and processes reactions recursively. Default `allNodes=None` creates fresh state. Supplying shared state can return a cached root before processing current options.
- Lines 174-195: product size is based on explicit atoms; a positive `minFragmentSize` subtracts dummy atoms. The default branch rejects products whose SMILES reduce to empty, C, CC or CCC after marker and empty-branch removal. Failure of this size filter rejects the product sequence.
- Lines 223-235: `test1` repeats the hierarchy counts; `test2` confirms `CCCOCCC` has no children under defaults.
- Lines 279-293: `testMinFragmentSize` shows `CCCOCCC` yields one unique `*CCC` leaf with minimum 3; this illustrates altered semantics, not a recommended tuning step.
- Lines 66-86: reaction definitions generate dummy attachment markers; lines 81-82 explicitly label the aromatic nitrogen-aromatic carbon cleavage as outside the standard RECAP set.

The script's trimming, blank-input/zero-atom guards, JSON format, error labels and sorting are transparent adapter choices. Upstream does not define this CLI contract or comprehensive malformed-input handling. Input parsing follows the module's `Chem.MolFromSmiles` examples. No broader normalization or scientific validation is added.

The reference license is at:
https://raw.githubusercontent.com/rdkit/rdkit/237a1d9027c800784afed8788540f38a3aa595f8/license.txt

Both its BSD-3-Clause text and the module's Novartis notice are retained in
[LICENSE.txt](LICENSE.txt) for the adapted usage examples.
