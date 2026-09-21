---
name: select-and-evaluate-graph2smiles-predictions
description: >
  Draft procedure for selecting Graph2SMILES checkpoints and evaluating generated reaction or retrosynthesis candidates with explicit validity and exact-match criteria. Invoke for: Select a checkpoint by validation top-1 accuracy, decode with beam search, reject unparsable SMILES, and evaluate the remaining predictions against canonicalized ground truth. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Select And Evaluate Graph2Smiles Predictions

This cited draft describes Select a checkpoint by validation top-1 accuracy, decode with beam search, reject unparsable SMILES, and evaluate the remaining predictions against canonicalized ground truth. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2110.09681 (source s1; SHA-256 cad00c55652c0c52f2f3a9cbb0848583409b69bd91d351940cf4f6fcd035c1e2)
- paper: https://arxiv.org/pdf/2110.09681 (source s2; SHA-256 cafe83f6e6a481d3ac3a387dacf2e3b4e1c829bee9889921575432e884d45d36)
- paper: https://arxiv.org/pdf/2110.09681 (source s3; SHA-256 e166817e297ab2e64844e8007a5c8b5f73f6b30d5343af264dc225e0f739126c)
- paper: https://arxiv.org/pdf/2110.09681 (source s4; SHA-256 2d322d9f393a176ca0c499ba192ca2f66ce4bf533f1efb0e252284455789300c)
- paper: https://arxiv.org/pdf/2110.09681 (source s5; SHA-256 1b791c271eda4161f8ff12564db3b95f2e23fd3597e2d9acade4cfaddd2e5cc4)
- paper: https://arxiv.org/pdf/2110.09681 (source s6; SHA-256 186f4869d98c097f47fdb23c57296bb5c92168bd3a4ffc24c063cd9c13651f39)
- paper: https://arxiv.org/pdf/2110.09681 (source s7; SHA-256 d4e1dd88c1688b2a21068b40781d658fbca1ca3be90dd3231be8b1c287f7fb26)
- paper: https://arxiv.org/pdf/2110.09681 (source s8; SHA-256 220c15c961193e22632dff1eb5c8e2ea0f16c8eeb1b1da725776f6ab51b1141b)
- paper: https://arxiv.org/pdf/2110.09681 (source s9; SHA-256 ed9e4f80f742ac2cada56b43f710990fc5ef907f0659e330a4507d1b3c1e1eea)
- paper: https://arxiv.org/pdf/2110.09681 (source s10; SHA-256 08a57cccdbaf509d32725176ca604c4cb26f92dca4017e0178815432f946a144)
- paper: https://arxiv.org/pdf/2110.09681 (source s11; SHA-256 a6df459494b09cb0f9fe0d95a54f4bed0044132d0fb157f05cba95ce7b2e1552)
- paper: https://arxiv.org/pdf/2110.09681 (source s12; SHA-256 bf474b593f93fa34a2f147265d5ed84a211b7497f383b0fcebe2e42cde8006b6)
- paper: https://arxiv.org/pdf/2110.09681 (source s13; SHA-256 59b1d7089da8c0402b0f37fee959617834ff661c079497880fafe17b4244975c)
- paper: https://arxiv.org/pdf/2110.09681 (source s14; SHA-256 8014d0cd26236da86d9a38fe50d06d27b93ccc4ee245de3f3f11697225c8964a)
- paper: https://arxiv.org/pdf/2110.09681 (source s15; SHA-256 21e6c053c3e52f9cf57926cb66aa398656d03530977a3e47082ca5c0274a00df)
- paper: https://arxiv.org/pdf/2110.09681 (source s16; SHA-256 5cd2461a6110aa6cb383071313006f596f31d9a804915496d34218658816a41f)

## Input & Output

Inputs:

- Model checkpoints and validation and held-out test sets. (s6:L47-L49)
- Reaction outcome prediction or one-step retrosynthesis examples with ground-truth output SMILES. (s6:L27-L28, s6:L32-L35, s6:L34-L35)

Outputs:

- A final list of proposed candidates whose SMILES can be parsed by RDKit. (s6:L50-L51)
- Held-out top-n test accuracies under canonicalized exact matching, retaining stereochemistry and excluding atom mapping. (s6:L25-L26, s6:L34-L35)

## Procedure Guidance

- Save checkpoints every 5,000 training steps and choose the checkpoint with the highest validation top-1 accuracy for held-out evaluation. (s6:L47-L49)
- If a different model improves top-n accuracy while sacrificing top-1 accuracy, retain the highest-validation-top-1 selection rule for reproducing the paper's reporting protocol. (s8:L19-L20, s8:L21-L22)
- Generate output SMILES using beam search with beam size 30. (s6:L49-L50)
- Reject any generated SMILES that RDKit cannot parse; retain the remaining candidates for evaluation. (s6:L50-L51)
- Canonicalize with RDKit and count a prediction as correct only when it exactly matches ground truth, including stereochemistry but excluding atom mapping; report top-n test accuracies. (s6:L34-L35, s6:L25-L26)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/coleygroup/Graph2SMILES — Referenced reproduction implementation, absent from the supplied repository inventory.
- external_asset: RDKit — Required for candidate parsing and canonicalized evaluation.

Unknowns and limits:

- Checkpoint paths, pretrained weights, execution commands, and implementation files are not supplied.
- Checkpoint tie-breaking, candidate deduplication, beam-search length penalties, and decoding termination limits are unspecified.
- The supplied text does not explain how invalid-candidate removal affects rank positions or how cases with no valid candidates are represented.
- No execution or reproduction has been performed.
