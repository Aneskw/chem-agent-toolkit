# Why this is a decision-rule candidate

- **Source:** paper catalog ID `LJMZ9IL6`; source text locked in `creation_pipeline/runs/verified20-LJMZ9IL6-resource-label-fix/jobs/LJMZ9IL6/bundle.json`. The successful replay status is `creation_pipeline/results/verified20-LJMZ9IL6-resource-label-fix.json`. The initial model run failed on an unsafe resource label; the successful run reused that saved response after the resource label was corrected. It was not a second independent extraction.
- **Extracted kind:** `method_procedure`, not `tool_usage`, in `checked_responses/LJMZ9IL6.json` from that run.
- **Operational rule:** use top-1 prediction probability and canonicalized output (source `s1p7:L19-L21`); if the score is below a selected threshold, return unknown rather than the product (source `s1p8:L5-L7`); evaluate the accuracy/coverage tradeoff, not only accepted-case accuracy. This changes the *report-or-abstain* choice.
- **Applicability boundary:** a trained prediction model and its output are needed. The published 0.83 threshold is an example from that paper's evaluation, not a universal cutoff. The skill says the implementation/checkpoint and independent threshold-selection protocol are missing.
- **Pilot goal:** test whether an agent follows the report/abstain boundary on new supplied-output scenarios. This cannot establish that the underlying chemistry model predicts correct products.

The four task requests and their expected branches are saved before the agent runs. Each appears in both conditions, with the same model, response schema, and sandbox. The only controlled difference is whether the candidate SKILL.md is included. The rubric checks the selected branch and whether a product was inappropriately reported; explanations remain available for human review.
