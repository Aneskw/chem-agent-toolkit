---
name: augment-and-rank-retrosynthesis-predictions
description: >
  Draft procedure for producing diverse reactant candidates through randomized product SMILES and two-stage sampling, followed by validity filtering and frequency ranking. Invoke for: When structured-output beam search yields limited answer diversity, sample reasoning trajectories and conditional reactant answers separately; canonicalize, filter, merge, and rank the resulting predictions. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Augment And Rank Retrosynthesis Predictions

This cited draft describes When structured-output beam search yields limited answer diversity, sample reasoning trajectories and conditional reactant answers separately; canonicalize, filter, merge, and rank the resulting predictions. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2507.17448 (source s1p1; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p2; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p3; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p4; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p5; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p6; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p7; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p8; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p9; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p10; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p11; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p12; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p13; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p14; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p15; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p16; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p17; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p18; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p19; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p20; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p21; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p22; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p23; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p24; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p25; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p26; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p27; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)

## Input & Output

Inputs:

- A target product represented as SMILES. (s1p5:L6-L7)
- Augmentation counts ka, ks, and kb; the reported full setting is (20, 10, 10). (s1p23:L22-L23)

Outputs:

- Top-k unique canonical reactant sets ranked by descending occurrence frequency after invalid predictions are removed. (s1p23:L12-L14, s1p23:L21-L22)

## Procedure Guidance

- Use two-stage sampling to address cases where full-response beam search produces differing intermediate text but identical reactant predictions. (s1p22:L51-L53, s1p22:L54-L55)
- Generate ka distinct product SMILES by varying the root atom and traversal order. (s1p23:L9-L11)
- For each input representation, generate ks reasoning trajectories. Condition on each trajectory and sample kb reactant predictions beginning at the <answer> tag, with answer-generation temperature set to the reported experimental value of 1.4. (s1p22:L56-L57, s1p23:L1-L1, s1p23:L3-L5)
- Canonicalize all generated reactant SMILES, discard invalid strings, and merge duplicate predictions. (s1p23:L12-L13)
- Count occurrences of each unique canonical reactant set across augmented predictions, rank by descending count, and select the top-k candidates. (s1p23:L13-L15, s1p23:L21-L22)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/OpenDFM/RetroDFM-R — The paper identifies this location for the model checkpoint and source code; neither is included in the bundle.

Unknowns and limits:

- Reasoning-stage sampling temperature, token limits, and other decoding settings are unspecified in the supplied text.
- Tie-breaking, handling of fewer than k valid unique predictions, and exact reactant-set canonicalization conventions are unspecified.
- No inference implementation files or callable interfaces are supplied.
