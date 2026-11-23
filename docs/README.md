# Documentation

## Using the pipeline

| Document | Content |
| --- | --- |
| [First run](../README.md) | Installation, accounts, minimal input and commands |
| [Configuration](pipeline/configuration.md) | Resource groups, models, libraries and execution settings |
| [Workflow](pipeline/shared-creation.md) | Stage responsibilities, Docker and delivery requirements |
| [Resources](pipeline/resources.md) | Source acquisition, research and cross-group sharing |
| [Readiness](pipeline/readiness.md) | Configuration, infrastructure and model permission checks |
| [Outputs](pipeline/outputs.md) | Skill packages, runtime.json and internal records |
| [Operations](pipeline/batch-operations.md) | Resume, installation, manual validation and cleanup |
| [Examples](../examples/README.md) | Complete construction examples |

## Development and interfaces

- [Code organization and state invariants](pipeline/code-organization.md)
- [Model call accounting](pipeline/model-call-accounting.md)
- [Developer verification](../validation/README.md)
- [Runtime interfaces](runtime/README.md)
- [Skill content](skills/docker-minimum.md), [packaging](skills/docker-packaging.md) and [runtime section template](skills/runtime-template.md)

The program reads `docs/skills/` specifications directly. Changes affect authoring, review and whether existing batches can resume.
