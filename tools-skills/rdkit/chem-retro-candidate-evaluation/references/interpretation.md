# Interpretation boundary

The LocalRetro paper defines exact matching to the recorded reactants and
round-trip correctness through a pretrained Molecular Transformer. This
package implements a transparent, interoperable input/output contract for
those two checks. It does **not** bundle the Molecular Transformer or claim
bit-for-bit reproduction of the paper's preprocessing. A forward result is
accepted only when supplied in the input JSONL with its own provenance.

To compare against published top-k results, verify the same reaction split,
canonicalization, stereochemistry policy, deduplication, number of retained
predictions, and forward-model checkpoint. Source:
https://doi.org/10.1021/jacsau.1c00246.
