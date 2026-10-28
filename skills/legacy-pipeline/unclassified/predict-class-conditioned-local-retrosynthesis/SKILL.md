---
name: predict-class-conditioned-local-retrosynthesis
description: "Run LocalRetro test-set decoding with or without known reaction classes; use the class-filtered output only when matching test labels and template-class tables exist."
license: undetermined
---


# Class-conditioned LocalRetro decoding

This is the **dataset test/decoding workflow**, not an arbitrary-product Python API. Use the full LocalRetro source at `eba83e72efabeb854fec86c865e8743c295a8a1e`, matching trained model, templates and preprocessed test split. Follow the [upstream setup and model instructions](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md).

```bash
cd /path/to/LocalRetro/scripts
python Test.py -d USPTO_50K
python Decode_predictions.py -d USPTO_50K
```

The first command writes `outputs/raw_prediction/LocalRetro_USPTO_50K.txt`; decoding writes `outputs/decoded_prediction/LocalRetro_USPTO_50K.txt` and `outputs/decoded_prediction_class/LocalRetro_USPTO_50K.txt`, relative to the repository root.

The [pinned decoder](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/scripts/Decode_predictions.py) enables class filtering when `data/USPTO_50K/class_test.csv` exists. It reads its `class` column and `template_rxnclass.csv`, retaining decoded templates allowed for that reaction class. These labels must correspond to the exact test-row order. A class file is not automatically available at deployment; do not use ground-truth classes in an untyped evaluation.

With no class file, use the unrestricted decoded output; the class output may contain only test IDs. Parse ranked candidate/score records without treating scores as probabilities. Keep raw and decoded files together and preserve test IDs. Do not substitute a test-set command for an arbitrary user's product without preparing the expected upstream dataset interface.

Use the decoder's default top-k unless its untyped `-k` CLI option is repaired and separately checked; passing a string override can break integer comparisons. Report failures/empty decoded candidates rather than claiming a target is unsynthesizable.

Decoded rows are tab-separated test IDs followed by Python tuple literals `(reactant_smiles, score)`, not JSON objects. If parsing them, use `ast.literal_eval` on each tuple field rather than `eval`; retain row IDs and missing predictions.
