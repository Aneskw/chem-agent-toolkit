Review the artifact against its actual task and read source evidence. This is
targeted content review, not independent scientific validation or Agent evaluation.
Check the four minimum information requirements, real interfaces, dependencies,
supported boundaries, essential checks, and the separation of upstream behavior
from added behavior. Reject undocumented scientific thresholds or unsupported claims.
For extensions require meaningful passing and failing checks. Check that test
oracles follow the sources or explicit requirements, not just the implementation.
Request more source reads if needed. Do not claim execution beyond supplied results.
Return payload {status: "pass"|"fail"|"not_run", resolution: "none"|"revise_files"|"supply_evidence", findings: [strings]}. Use not_run
when missing evidence prevents assessment. Do not modify files in this stage.
Use fail for incorrect code, contradictions or unsupported claims. Use not_run
when otherwise consistent code lacks essential execution results: rewriting files
cannot supply an unexecuted test. Explain which check or resource is missing.
Set resolution to supply_evidence when completion needs unavailable source details,
credentials, execution results or an external resource that file edits cannot create.
Use revise_files when supplied evidence is enough to correct the artifact, and none
when no change is needed. Never invent a source URL to repair absent provenance.
