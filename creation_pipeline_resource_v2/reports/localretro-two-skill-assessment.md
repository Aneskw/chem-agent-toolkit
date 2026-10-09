# LocalRetro two-candidate assessment

Source run: `my-localretro-02` (`2GFR874J`). Both candidates passed source
quotation/location, response schema, and `SKILL.md` format checks. This is
evidence traceability, not a demonstration of task improvement.

| Candidate | Useful content | Current limitation | Executable fixture |
| --- | --- | --- | --- |
| `derive-local-reaction-template-library` | Describes atom-vs-bond template selection, multi-change handling, rejection of failed extraction, and minimum-frequency export. | `raw_train.csv` and optional class labels are absent; README and code disagree on `train_class.csv` vs `class_train.csv`. The cited decoder/helper dependencies are incomplete. | Not applicable: package contains no scripts. |
| `predict-class-conditioned-local-retrosynthesis` | Captures the branch between class-restricted and unrestricted template ranking. | Mostly describes model architecture; the source set does not establish arbitrary-product inference input/output, decoder failure handling, or a complete execution recipe. | Not applicable: package contains no scripts. |

Both remain low-confidence procedural drafts. The first is a stronger
method candidate because it contains actionable branches and failure criteria;
its missing assets prevent direct execution. The second needs clearer
decision points, inputs, and implementation evidence before it can guide an
agent reliably. Neither has been evaluated on held-out chemistry tasks with
and without the skill; agent effectiveness is unknown.
