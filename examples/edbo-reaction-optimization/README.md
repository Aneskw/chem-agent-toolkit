# EDBO reaction optimization

This example follows a paper and code through resource preparation, candidate discovery, skill
writing, review and publication. The recorded run is from 2026-10-27; `input.json` is a separate
configuration for running the current pipeline with production defaults.

## Resources

The inputs are *Bayesian reaction optimization as a tool for chemical synthesis*
([Nature, 2021](https://doi.org/10.1038/s41586-021-03213-y)) and
[b-shields/edbo at the pinned revision](https://github.com/b-shields/edbo/tree/9b41eac3f6d9e520547702fd5b0c7ef6441625a4).
Both configurations identify the paper by URL/hash and the repository by commit. Full upstream
resources are fetched instead of copied into this example.

The pinned code is an input resource, not a claim that it provides the latest supported interfaces.
Current discovery assesses maintained compatible versions and may supplement related official
resources. The recorded skills target the inspected EDBO snapshot. The DOE workflow comes from
repository example code; it is not presented as a validated protocol from the Nature paper.

## Walk through the recorded run

1. Read [recorded-input.json](recorded-input.json) for the original input selection and effective
   development limits. [sources.json](sources.json) connects the acquired resources to stable file
   locators such as `e224` for `edbo/feature_utils.py` and `e234` for `examples/DOE/DOE.py`.
2. Read [discovery.json](discovery.json). It proposes reaction-space encoding, PCA/DOE initial
   design and iterative Bayesian optimization. Each candidate states its starting inputs, entrypoint,
   intended result and evidence gaps.
3. Follow the accepted package links below. The writing-basis files map their sections to inspected
   source functions and setup instructions. For example, the encoding skill's basis identifies
   `reaction_space`, `encode_component` and the `Data` container rather than relying on the paper
   alone for software usage details.
4. Read each review beside its basis. The encoding review narrows input preparation and setup
   requirements. The DOE review records corrections to component selection and ordering, along
   with a retracted allegation about PCA index alignment. This shows how a finding is checked
   against code and resolved, rather than treating every reviewer statement as correct.
5. Read [skills.json](skills.json) for package links and recorded file fingerprints, then
   [summary.json](summary.json) for the overall result, deferred work, model usage and limits.

| Delivered skill | Task | Writing basis | Final review |
| --- | --- | --- | --- |
| [build-encoded-reaction-space](../../skills/build-encoded-reaction-space/SKILL.md) | Encode supplied reaction components, clean features and expand the Cartesian search space | [basis](records/build-encoded-reaction-space/basis.json) | [review](records/build-encoded-reaction-space/review.json) |
| [pca-doe-initial-batch](../../skills/pca-doe-initial-batch/SKILL.md) | Map an initial design through component PCA coordinates to valid rows of a prepared EDBO reaction space | [basis](records/pca-doe-initial-batch/basis.json) | [review](records/pca-doe-initial-batch/review.json) |

The recorded development run considered three candidates and published two packages. Iterative
Bayesian optimization was deferred under its build limit, rather than rejected as having no
packaging value. The effective limits in `recorded-input.json` match the summary; an earlier
model-call limit was extended during development, as disclosed there. These limits do not apply
to the current production rerun configuration.

The recorded model was `gpt-6-luna`. A developer source audit helped retract the PCA alignment
allegation and remove an unnecessary patch; this was additional work outside the automated stages,
not an autonomous pipeline stage. A supplemental-source registration limitation is also disclosed
in the review. No EDBO installation or execution was performed, and agent benefit was not measured.

## Run with the current configuration

From the repository root:

```text
python -m creation_pipeline build examples/edbo-reaction-optimization/input.json --preflight
python -m creation_pipeline build examples/edbo-reaction-optimization/input.json --no-adopt --state-dir ../chemical_skill/pipeline-state
```

[input.json](input.json) uses the same initial resources with production defaults, your configured
Codex model and scoped supplementary research. It does not prescribe candidates or skill names.
A new build need not reproduce the recorded package count, text or source choices.

Keep `--no-adopt` to inspect a rerun without publishing conflicting names. See the
[workflow guide](../README.md) for prerequisites, the common stage map and record interpretation.
The recorded reviews and fingerprints describe the illustrated publication; subsequent package
maintenance does not retroactively update that evidence.
