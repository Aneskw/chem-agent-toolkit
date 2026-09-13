# Model interface

The wrapper accepts one product SMILES and `--top-k`. It loads the pinned LocalRetro manifest and emits normalized, deduplicated reactant candidates. Model scores are ranking signals, not calibrated probabilities.
