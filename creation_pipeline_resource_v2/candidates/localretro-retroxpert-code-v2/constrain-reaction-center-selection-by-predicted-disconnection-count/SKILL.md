---
name: constrain-reaction-center-selection-by-predicted-disconnection-count
description: >-
  Use a graph-level estimate of how many bonds change to constrain bond-level reaction-center selection, construct synthons, and separately assess center and synthon agreement when labels exist. Invoke for: choosing a paper-backed procedure when task evidence or constraints change; do not treat this draft as experimentally validated.
license: undetermined
compatibility: Research draft; inspect source-specific dependencies and data before use
allowed-tools: Read
---

# Constrain Reaction Center Selection By Predicted Disconnection Count

Use a graph-level estimate of how many bonds change to constrain bond-level reaction-center selection, construct synthons, and separately assess center and synthon agreement when labels exist. Use only for the task settings supported by the cited papers and pinned implementations. Do not use it as a generic reaction predictor or assume a successful agent effect.

## Credibility

**Low confidence (Highly flexible)** as an abstracted agent procedure: source locations were checked, while semantic merging and agent utility require human review. Research state: `procedural_skill_candidate`.

## Reference

- `74LHJIVM/auxiliary-guided-reaction-center-identification`: RetroXpert: Decompose Retrosynthesis Prediction like a Chemist (https://arxiv.org/pdf/2011.02893v1); implementation https://github.com/uta-smile/RetroXpert at `321cc3daf2f3a7ac9ab5b37dde5b666b338e1ed5`. Validated source locations: s1p3:L68-L69, s1p5:L23-L24, s1p5:L6-L7, s1p7:L19-L20, s1p7:L29-L32, s5:L122-L123, s5:L142-L143, s5:L88-L92, s7:L100-L101, s7:L109-L112, s7:L116-L118, s7:L121-L121, s7:L137-L138, s7:L148-L149, s7:L162-L164, s7:L170-L170, s7:L60-L65, s7:L69-L69, s7:L73-L73, s7:L77-L79, s7:L91-L91.

## Input & Output

Inputs depend on the chosen variant:

- For the repository postprocessor, EGAT test prediction logs and preprocessed test reaction pickles.
- Product molecular graphs with atom and bond features; reaction-type indicators are conditional on whether the type is supplied.

Expected outputs:

- Predicted synthons serialized into src-test-prediction.txt in the selected OpenNMT dataset directory.
- When ground truth is available, guided bond-disconnection accuracy and a separate synthon-set accuracy check.

## Procedure Guidance

- **When** Reaction types are supplied. **Do** Use the typed branch with reaction-class features; otherwise use the untyped branch. **Avoid** Apply typed evaluation assumptions to inputs lacking reaction types. (supported by 74LHJIVM/auxiliary-guided-reaction-center-identification).
- **When** Auxiliary disconnection-count predictions are available. **Do** Select the predicted number of most probable disconnections. In the described repository postprocessor, average paired directed-edge retained-edge probabilities, double the undirected count, and select the lowest-scoring directed entries; select none for a zero count. **Avoid** Reverse the retained-edge score convention or replace count guidance with the 0.5 threshold except for the stated main-task-only ablation. (supported by 74LHJIVM/auxiliary-guided-reaction-center-identification).
- **When** Selected disconnections are converted into synthons and reference labels are available. **Do** Remove selected bonds, serialize synthons, verify matching dataset and prediction lengths, and compare disconnection sets and synthon sets independently. **Avoid** Treat synthon construction as completed reactant generation or use one agreement check as a substitute for the other. (supported by 74LHJIVM/auxiliary-guided-reaction-center-identification).

Deduplication recommendation: `merge_as_variants`; A proposed variant group with retroxpert-evaluate-bond-disconnection has a useful shared decision: count-guided selection and assessment of disconnections. The catalog describes typed evaluation, while this candidate includes conditional typed or untyped handling and synthon construction. Preserve those scope distinctions pending human review.

## Matters & Troubleshooting

- The repository reports an information leak and revised results; original paper accuracy is not verified performance.
- No execution or checkpoint validation is established.
- The described postprocessor requires labeled benchmark artifacts; arbitrary unlabeled-product support is not established.
- Tie handling, self-loops, and inconsistent directed-edge selections remain unresolved.
- Catalog overlap note for retroxpert-evaluate-bond-disconnection: proposed shared capability group with typed evaluation and broader conditional center-selection variants.
- Catalog comparisons use supplied package descriptions only; full package behavior must be inspected before any duplicate or variant consolidation.
- All deduplication actions are proposals for human review, not authorization for automatic semantic merging.
- Evidence is limited to supplied summaries and evidence identifiers; unavailable source text was not inspected.
- Do not count this candidate as an executable or agent-validated skill.
