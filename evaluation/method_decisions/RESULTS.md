# Initial non-LocalRetro decision pilot

Source candidate: `predict-reaction-products-with-confidence-abstention` from paper `LJMZ9IL6`. The citation-checked extraction replay completed with `method_drafts_created`; the candidate itself remains `draft_unexecuted` because the paper's trained model and checkpoint were not supplied. The agent test asks whether the *textual decision rule* helps it decide when to report a supplied prediction.

The integrated creation replay `creation_pipeline/results/decision-pilot-with-task-drafts-20260920.json` also completed: two `method_procedure` drafts, both format-valid, and two four-case task-draft files (`2 apply + 2 do_not_apply` each). This replay reused a previously saved extraction response; task drafting made new model calls. It demonstrates the optional creation-to-task-draft stage, not independent re-extraction or automatically verified benchmark labels.

Model: `gpt-5.6-luna` via authenticated Codex CLI. Four scenario cards were fixed before the run (two where the reporting rule applies, one where a high score lacks validation, one where no model exists). Eight isolated calls, paired by task; seed 17 randomized their order. Raw responses and token counts are in `results/pilot.jsonl`.

| Task | Expected substantive action | No skill | With skill |
|---|---|---|---|
| Validated score 0.94 vs cutoff 0.86 | Report canonical product | Reported product | Reported product |
| Validated score 0.48 vs cutoff 0.86 | Abstain | Abstained | Abstained |
| Score 0.96 without validation or cutoff | Withhold reliability claim; request validation | Withheld claim | Withheld claim |
| No trained model or prediction | Do not invent a product; identify missing model | Did not invent one | Did not invent one |

Both conditions made the intended substantive decision on all four tasks. The strict enum scorer in `summary.json` records 2/4 per condition because its gold labels `insufficient_evidence` and `cannot_infer` were more specific than the synonymous withholding labels used in the answers. This is an **exploratory interpretation after inspecting the responses**, not a changed preregistered score. No conclusion changes: the conditions tie either way.

Output tokens: no skill 511 total; with skill 607 total. Input tokens: 51,800 versus 57,252 (the CLI includes substantial fixed context, and the skill itself adds input). This pilot does not show a token reduction or a quality gain. It verifies the end-to-end experimental wiring and exposes two issues before formal evaluation: overly easy, explicit threshold tasks cause a ceiling effect, and the rubric needs semantically non-overlapping action labels. A stronger test should use more specialized decision rules, preregister its rubric, and use multiple unseen tasks and repeats.

## Reviewed auto-drafted scenarios

`draft_tasks.py` produced four new proposed scenarios, two apply and two do not apply. Before running the agent, we checked that the molecule strings and chosen probabilities were absent as literal examples from the locked source bundle. RDKit confirmed that `CC(=O)OCC` and `CCOC(C)=O` canonicalize to the same SMILES, while `C1(CC` is invalid. We then froze `reviewed_tasks.json` and `reviewed_oracle.json` (including synonymous withholding labels) before running `results/reviewed.jsonl`.

The second paired run again made eight successful calls. Both conditions scored **3/4** on the frozen exact-output rubric. Each got the high/low threshold and applicability branches right, and each failed to put the *canonical* SMILES in `product_smiles` for the equivalent-representation case, although both explanations recognized the equivalence. Output tokens: no skill 525, with skill 694; input tokens: 51,692 versus 57,247. The skill did not improve the measured decision score or reduce tokens on this small set. It remains a source-supported **candidate**, not a proven useful skill.

## Final isolation check

The runner was then moved to fresh temporary working directories outside the repository, and it rejected attempts with tool events. `results/reviewed-isolated.jsonl` has eight successful calls and **zero tool events**. Scores stayed at **3/4 without skill and 3/4 with skill**. Output tokens were 510 without versus 615 with; input tokens were 51,557 versus 57,021. The earlier score conclusion is unchanged, and the stricter isolation is the version to use for future experiments.
