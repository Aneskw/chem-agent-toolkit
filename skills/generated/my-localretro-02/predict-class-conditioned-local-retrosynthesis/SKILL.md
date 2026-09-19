---
name: predict-class-conditioned-local-retrosynthesis
description: >-
  Draft procedure for ranking local template applications at product atoms and bonds, with an optional reaction-class restriction, and decoding them into precursor suggestions. Invoke for: Encode product structure with local message passing and global attention, score template/site combinations, restrict templates when a reaction class is supplied, and apply ranked templates to obtain reactants. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Predict Class Conditioned Local Retrosynthesis

This cited draft describes Encode product structure with local message passing and global attention, score template/site combinations, restrict templates when a reaction class is supplied, and apply ranked templates to obtain reactants. Applicable only when the listed inputs and resources exist; it is not a verified executable package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8549044/fullTextXML (source s1; SHA-256 0bb218ba3f78a0ee0bafe9ab9b8ab2523147819a3deee7a9a6991cfa4e34bcb5)
- repo_doc: https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md (source s2; SHA-256 f8d7644b3d864f1af6bafa4c7107468e9c1051254af11909a1c365d2caba3190)
- repo_code: https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/LocalTemplate/template_extractor.py (source s3; SHA-256 31749a76084707bed5f6a363fdd83d4f8032126888560fb3b31cf31e267d66ee)
- repo_code: https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/preprocessing/Extract_from_train_data.py (source s4; SHA-256 7c476b821247f22026875560f81e970df9df8461c541f0d53118b074b3b5c58b)

## Input & Output

Inputs:

- A target product molecule represented as a graph of atoms and bonds. (s1:L119-L121)
- A trained LocalRetro model, local template library, and optionally a known reaction class. (s1:L152-L153, s1:L163-L165)

Outputs:

- Reactant suggestions ranked by predicted template-application scores. (s1:L138-L139)
- For the documented test-set workflow, raw predictions and decoded reactant files under outputs/raw_prediction, outputs/decoded_prediction, and outputs/decoded_prediction_class. (s2:L108-L108, s2:L113-L115)

## Procedure Guidance

- Initialize atom and bond features from molecular properties and update local atomic environments using message passing; encode bonds from their endpoint atom features. (s1:L120-L123, s1:L127-L128)
- Apply global multihead self-attention across atoms and bonds to account for remote chemical environments before classifying local template applications. (s1:L143-L146, s1:L146-L146)
- Rank predicted template/site combinations by score. When the reaction class is given, apply only templates associated with that class; otherwise use the unrestricted predicted template set. (s1:L162-L165, s1:L163-L165)
- Apply the selected templates at their predicted atoms or bonds to obtain ranked reactant suggestions. For the documented USPTO_50K test workflow, run Test.py and then Decode_predictions.py with -d USPTO_50K. (s1:L138-L139, s2:L106-L106, s2:L109-L111)

## Matters & Troubleshooting

Resources:

- repo_file: models/LocalRetro_USPTO_50K.pth — Documented model artifact for the USPTO_50K workflow.
- repo_file: scripts/Test.py — Documented test-set prediction entry point.
- repo_file: scripts/Decode_predictions.py — Documented entry point for decoding raw predictions into reactants.

Unknowns and limits:

- The model, test, and decoder implementation bodies are not supplied, so tensor schemas, class-filter plumbing, and decoding failure handling cannot be verified.
- The source does not specify a stopping threshold or a complete automatic multistep search policy.
- The documented commands target a dataset test set; an arbitrary-product inference API is not established by the supplied text.
- Exact runtime asset paths beyond the documented model artifact are not established here.
- The README reports changes to templates and activation functions after publication; exact equivalence between the snapshot and the published model is not established.
- No prediction or decoding was executed.
