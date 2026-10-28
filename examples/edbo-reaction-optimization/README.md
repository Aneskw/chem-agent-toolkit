# EDBO reaction-space and initial-design batch

Original resources: Shields et al., Nature (2021), DOI [10.1038/s41586-021-03213-y](https://doi.org/10.1038/s41586-021-03213-y), and [b-shields/edbo](https://github.com/b-shields/edbo/tree/9b41eac3f6d9e520547702fd5b0c7ef6441625a4). The PDF URL/hash and code commit are fixed in input.json. Full paper/repository contents are acquired rather than copied into this example. The DOE method is packaged from repository example code; it is not claimed to be a validated protocol from the Nature paper.

For the shared file-by-file reading guide and reproduction procedure see [Examples](../README.md). No batch-specific preparation is required beyond the common pipeline prerequisites and network access.

## Actual outcome

| Accepted Skill | Scope |
| --- | --- |
| [build-encoded-reaction-space](../../skills/build-encoded-reaction-space/SKILL.md) | The user supplies the reaction components and, when needed, SMILES strings, compound names that can be resolved, or prepared descriptor matrices. The function performs component encoding, feature cleanup, Cartesian expansion, and optional min–max scaling; resolving invalid or unavailable structures remains input preparation. |
| [pca-doe-initial-batch](../../skills/pca-doe-initial-batch/SKILL.md) | The user supplies a prepared EDBO reaction-space object. Supply component keys from reaction.descriptors in the same builder order as reaction.index_headers, with each key matching its descriptor columns and generated index header. Use every indexed component to retrieve encoded rows. |

Discovery considered 3 candidates; 2 packages were accepted and adopted. Effective development limits are recorded in input.json; the initial 12-call stage budget was extended to 14 for targeted development corrections, as recorded in summary.json. Deferred candidates are listed there too. The source model was gpt-6-luna. No tool installation or EDBO execution was performed. Content review is not an Agent-benefit measurement.

The records/<skill-name>/ folders contain final writing basis and independent review, including important repair history. This development batch also received a developer source audit: an earlier PCA alignment allegation was challenged against the exact ndarray insertion and scaler implementation, and unnecessary upstream overrides were removed before final publication. This extra intervention is not an autonomous pipeline stage or a claim of perfect review reliability. Skills are linked to their single authoritative packages in the project skills/ directory; this example adds no README or build record inside those packages.

## Reproduce this batch

From the repository root:

```text
python -m creation_pipeline build examples/edbo-reaction-optimization/input.json --no-adopt
```

The common README explains configuration-only preflight, real connection checks, output locations and non-determinism. Keep --no-adopt for a rerun to avoid conflicts with the already published names. Source revisions and published package hashes are preserved; byte-identical model output is not promised.
