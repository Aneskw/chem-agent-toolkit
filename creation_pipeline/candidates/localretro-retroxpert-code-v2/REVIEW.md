# Candidate review: LocalRetro and RetroXpert

These four documents were abstracted from method candidates with cited paper
text and pinned repository material. They are **procedural skill candidates**,
not installed or agent-validated skills. The model's grouping and raw
deduplication proposals are recorded in
`creation_pipeline/results/localretro-retroxpert-code-v2-abstraction.json`.
The notes below are an agent review of overlap, not a final researcher decision.

| Candidate | Source | Overlap decision | Reason |
| --- | --- | --- | --- |
| `rank-precursors-through-localized-reaction-template-application` | LocalRetro | Do not create a second prediction package | The existing `localretro-single-step-retrosynthesis` wrapper already performs the same model task. The extracted decision rules may improve its guidance, but no new task capability is established. |
| `judge-precursor-proposals-by-reference-agreement-and-forward-consistency` | LocalRetro | Retain as a procedural candidate using the existing scorer | The current `chem-retro-candidate-evaluation` package computes the scores. The candidate adds a choice of metric and a stop condition when the required forward model is unavailable; that guidance remains untested with an agent. |
| `constrain-reaction-center-selection-by-predicted-disconnection-count` | RetroXpert | Retain separately | The existing `retroxpert-evaluate-bond-disconnection` package only checks resources. It does not encode the paper-and-code decision of selecting cuts using the predicted disconnection count. The model suggested `merge_as_variants`; this review does **not** accept that semantic merge. |
| `train-downstream-precursor-generation-on-upstream-prediction-errors` | RetroXpert | Retain separately | The conditional training augmentation and end-to-end evaluation policy differ from the existing preflight and scoring packages. Required dataset and training artifacts are not bundled. |

The RetroXpert repository README reports an information-leak correction after
the paper. The extracted `canonicalize-and-remap-reaction-csv` operation is
recorded in the source run as `tool_usage`; it is not promoted into these
paper-method candidates. Before adopting either RetroXpert procedure, review
the corrected preprocessing branch and whether its result is comparable with
the paper's original metrics.

No held-out agent comparison, token measurement, or chemistry-result quality
test was run for these candidates. Source citation and abstraction do not
prove usefulness.
