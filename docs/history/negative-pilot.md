# Earlier Agent evaluation: no demonstrated gain

Baseline: commit `6bb535a`. Historical raw traces, tasks and protocols remain in Git at `evaluation/`; use that commit to reproduce the old runners. They are not part of the new build pipeline.

The isolated, reviewed four-task pilot scored 3/4 both with and without the skill. Output tokens were 510 without versus 615 with; input tokens were 51,557 versus 57,021. This small pilot did not show a quality or token advantage. A separate easy benchmark hit a ceiling. Neither result establishes general effectiveness.

Future evaluation needs independently frozen tasks, comparable tool access, multiple runs and quality/cost reporting. Generated examples alone are not an efficacy benchmark.
