---
name: reaction-center-guided-retrosynthesis
description: >
  Draft procedure for selecting reaction centers from predicted atom and bond reactivities and generating ranked reactants with Retroformer. Invoke for: Choose naive reaction-center thresholding during training or inference, or recursively search diverse connected reaction centers during inference; condition reactant generation on the selected centers. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Reaction Center Guided Retrosynthesis

This cited draft describes Choose naive reaction-center thresholding during training or inference, or recursively search diverse connected reaction centers during inference; condition reactant generation on the selected centers. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p1; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p2; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p3; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p4; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p5; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p6; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p7; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p8; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p9; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p10; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p11; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p12; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p13; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p14; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p15; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)
- paper: https://proceedings.mlr.press/v162/wan22a/wan22a.pdf (source s1p16; SHA-256 1c353380b883803c52f0e26cfc8b8c64daeeb8cd9dac90dde2fb00ab2b83db41)

## Input & Output

Inputs:

- Product SMILES and its aligned SMILES graph, including adjacency and bond features. (s1p4:L3-L6)
- Predicted atom and bond reactive probabilities, graph, pruning thresholds, and beta. (s1p16:L3-L3)
- Requested total number of reactant predictions k and maximum number of selected reaction centers n. (s1p4:L107-L110)

Outputs:

- Candidate reaction-center subgraphs with reactive scores. (s1p16:L18-L18)
- Reactant predictions ranked by the sum of their reaction-center and generative scores. (s1p4:L110-L113)

## Procedure Guidance

- For the naive strategy, mark an atom token reactive only when its own probability exceeds 0.5 and it belongs to an edge whose probability exceeds 0.5. Keep special tokens non-reactive. This branch applies during training and inference. (s1p4:L94-L98, s1p4:L97-L98)
- Use the search branch only during inference. For the reported experimental settings, use at most three centers and temperature 10; set atom/bond percentile thresholds to 40/40 when reaction class is unknown and 40/55 when it is known. (s1p4:L112-L113, s1p15:L32-L33, s1p15:L34-L38, s1p15:L37-L38)
- Remove nodes and edges below their respective thresholds, then retrieve connected components from the remaining graph. (s1p16:L4-L6)
- For each component, use maximum root size 25 and maximum branching factor 5. Set the minimum leaf size to the count of component atoms whose reactive probability exceeds beta; the reported beta is 0.5. If the component exceeds the root-size limit, remove the lowest-probability nodes until the limit is met. (s1p16:L8-L13, s1p15:L39-L39)
- Recursively prune border nodes while preserving connectivity. Rank pruning candidates by atom reactive probability and retain at most maxBranch candidates for branching. Stop each recursion when the component reaches minLeafSize. (s1p15:L24-L25, s1p15:L27-L28)
- Score each candidate by its summed atom and bond log probabilities multiplied by (1 + phi(|V|; mu, sigma squared))/(|V| + |E|). The reported normal-density parameters are mu = 5.55 and sigma = 1.2. (s1p16:L19-L28, s1p16:L29-L30)
- Rank subgraphs within each root component and apply the prose diversity rule: retain its top-ranked subgraph and remove other subgraphs sharing at least two nodes with it. Pool remaining subgraphs across components and select the top n by reactive score. Resolve the conflicting overlap threshold in Algorithm 3 before implementation. (s1p15:L29-L30, s1p15:L30-L31, s1p16:L16-L16)
- Condition the decoder on each selected reaction center and encoder outputs. Generate k/n reactant predictions per center and rank the combined predictions using reaction-center plus generative scores. (s1p4:L115-L117, s1p4:L109-L112)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/yuewan2/Retroformer — The paper identifies this implementation repository; its files and trained model assets are not supplied in the snapshot.

Unknowns and limits:

- No implementation files, checkpoint paths, invocation interface, or dependency versions are supplied.
- The prose removes competing subgraphs sharing at least two nodes; Algorithm 3 says more than two and does not explicitly exempt the top-ranked subgraph.
- The pruning-candidate ranking direction, tie handling, and duplicate-subgraph handling are not explicitly specified.
- Handling of empty graphs, zero minimum leaf size, disconnected roots after initial truncation, and fewer than n available centers is unspecified.
- The allocation of predictions when k/n is nonintegral and the exact generative-score normalization are unspecified.
- The exact temperature transformation of reactive probabilities is not provided.
