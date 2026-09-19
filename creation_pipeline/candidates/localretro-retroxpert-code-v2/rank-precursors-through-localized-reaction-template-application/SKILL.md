---
name: rank-precursors-through-localized-reaction-template-application
description: >-
  Choose candidate reaction sites and applicable local transformations using molecular context, then rank the precursor sets produced by applying those transformations. Invoke for: choosing a paper-backed procedure when task evidence or constraints change; do not treat this draft as experimentally validated.
license: undetermined
compatibility: Research draft; inspect source-specific dependencies and data before use
allowed-tools: Read
---

# Rank Precursors Through Localized Reaction Template Application

Choose candidate reaction sites and applicable local transformations using molecular context, then rank the precursor sets produced by applying those transformations. Use only for the task settings supported by the cited papers and pinned implementations. Do not use it as a generic reaction predictor or assume a successful agent effect.

## Credibility

**Low confidence (Highly flexible)** as an abstracted agent procedure: source locations were checked, while semantic merging and agent utility require human review. Research state: `procedural_skill_candidate`.

## Reference

- `2GFR874J/predict-retrosynthesis-with-local-and-global-reactivity`: Deep Retrosynthetic Reaction Prediction using Local Reactivity and Global Attention (https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8549044/fullTextXML); implementation https://github.com/kaist-amsg/LocalRetro at `eba83e72efabeb854fec86c865e8743c295a8a1e`. Validated source locations: s1:L119-L120, s1:L120-L121, s1:L122-L123, s1:L127-L128, s1:L138-L139, s1:L144-L146, s1:L146-L146, s1:L152-L153, s1:L158-L160, s1:L162-L163, s1:L163-L165, s1:L92-L95.

## Input & Output

Inputs depend on the chosen variant:

- A local reaction-template library derived by comparing atoms and bonds in atom-mapped products and reactants.
- A target product represented as a molecular graph with atoms as vertices and bonds as edges.
- Trained atom and bond template classifiers and, optionally, a known reaction class.

Expected outputs:

- Reactant proposals obtained by applying predicted templates at predicted atoms and bonds, ranked by model scores.

## Procedure Guidance

- **When** A target product, local template library, and trained classifiers are available for template-based single-step prediction. **Do** Score atom and bond template-center combinations using local environments and global reactivity context, rank them, and apply the selected templates to obtain precursor proposals. **Avoid** Treat template extraction or resource preflight as precursor prediction, or interpret ranking scores as experimental success probabilities. (supported by 2GFR874J/predict-retrosynthesis-with-local-and-global-reactivity).
- **When** The reaction class is supplied. **Do** Restrict template application to templates associated with that class. **Avoid** Assume a known class for an untyped input. (supported by 2GFR874J/predict-retrosynthesis-with-local-and-global-reactivity).

Deduplication recommendation: `review_duplicate`; The task and mechanism substantially overlap with localretro-single-step-retrosynthesis. This is a proposed catalog duplicate requiring inspection of package behavior. Shared single-step retrosynthesis goals do not justify merging template application with bond-disconnection or sequence-generation mechanisms.

## Matters & Troubleshooting

- No implementation or execution is established.
- Usable trained parameters, implementation settings, and template-application failure, deduplication, and tie handling are not established.
- The supplied summary distinguishes the published method from later repository changes; equivalence requires review.
- Catalog overlap note for localretro-single-step-retrosynthesis: substantial task and mechanism overlap; proposed duplicate.
- Catalog overlap note for localretro-extract-local-template: upstream template construction, a separate capability.
- Catalog overlap note for localretro-template-library-preflight: upstream readiness checks, a separate capability.
- Catalog overlap note for retroprime-two-stage-retrosynthesis: shared prediction goal with a different mechanism; retain separately.
- Catalog comparisons use supplied package descriptions only; full package behavior must be inspected before any duplicate or variant consolidation.
- All deduplication actions are proposals for human review, not authorization for automatic semantic merging.
- Evidence is limited to supplied summaries and evidence identifiers; unavailable source text was not inspected.
- Do not count this candidate as an executable or agent-validated skill.
