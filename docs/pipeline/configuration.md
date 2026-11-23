# Configuration

Inputs use JSON or YAML. Paths are relative to the configuration file. Unknown fields are rejected.

## Main fields

| Field | Default | Meaning |
| --- | --- | --- |
| workflow | shared-environments | Shared tool environment workflow |
| resource_groups | Required, or use sources | Groups of related sources |
| sources | Alternative to resource_groups | Single-group shorthand |
| prompt / notes | Empty strings | Task direction and additional requirements |
| constraints | {} | Task constraints passed to the model |
| model | backend=codex_cli | Model selection and CLI settings |
| research_access | supplement | supplement permits targeted research; known_only limits access to supplied sources and known addresses |
| network | true | Source acquisition and Agent network access |
| environments | See below | Tool library, publication and Docker settings |
| execution.profile | production | production or development |
| limits | Mostly null | Explicit resource and call budgets |
| adoption.enabled | true | Add eligible Skills to the delivery library |

## Resource groups

```json
{
  "resource_groups": [
    {
      "id": "method-a",
      "sources": [
        {"id": "code", "path": "inputs/method-a/code"},
        {"id": "paper", "path": "inputs/method-a/paper.pdf", "related_to": ["code"]}
      ]
    }
  ]
}
```

Each group needs a unique id and nonempty sources. Source IDs are unique within a group; related_to refers only to that group's input IDs. Groups run serially in input order.

Each source uses exactly one of path, url, repo, paper or table. A repo can use ref to pin a revision. The default storage=copy creates a snapshot. A large individual file can use storage=reference; the operator must retain the original. See [resources](resources.md).

## Models

```json
{"model": {"backend": "codex_cli", "name": "YOUR_MODEL"}}
```

name is optional. transport accepts default or https; set reasoning_effort and service_tier only to values supported by the client. The account must have access to the selected model. The shared workflow requires native CLI resource tools.

## Tool environments

| Field | Default | Meaning |
| --- | --- | --- |
| root | tools beside the configuration file | Shared index, descriptions and build materials |
| repository | ghcr.io/jinselw/chem-tools | Publishing target; requires upload rights, so other users normally supply their own |
| publish | true | Upload and verify anonymous access; false performs local validation only |
| source_url | Empty string | Optional source repository metadata label |
| operation_timeout | null | Optional timeout for one Docker build, publication or validation operation, in seconds |

repository has no tag; the program allocates version tags. source_url is independent of the publishing account. Configurations must point to the same root to share environments.

With operation_timeout set to null, Docker operations have no time budget. Registry requests and cleanup retain short timeouts.

## Budgets

production has no default candidate, build, repair, model-turn or total-time cap. Common limits:

Startup Agent smoke checks use the configured model_timeout and total_seconds settings. CLI, Docker connectivity and registry checks retain short transport deadlines.

| Field | Purpose |
| --- | --- |
| max_candidates | Candidates discovered per group |
| max_builds | Candidate builds started during this invocation |
| model_calls / candidate_calls | Agent turn budgets for a session and candidate |
| model_timeout / total_seconds / discovery_seconds | Model operation, run and discovery time budgets |
| repair_rounds | Explicit repair budget |
| source_bytes / source_total_bytes / source_files | Source size and file-count budgets |
| package_bytes | Package size budget |
| network_requests / network_timeout | Acquisition request count and timeout |

null disables a limit. development sets model_calls=8, max_candidates=3, max_builds=1 and repair_rounds=2; limits can override these values. Budgets apply at their session and scheduling checkpoints. Agent turns do not measure underlying request counts or fees.
