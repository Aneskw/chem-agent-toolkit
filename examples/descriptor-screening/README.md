# Portable descriptor screening example

This example uses the unchanged original files tracked in `validation/sibling-json/source`.
Its relative source path resolves against input.json, independently of the checkout's drive,
directory name or current user. Historical acceptance configurations are not rewritten.
Copy/clone the complete repository, not this configuration alone.

Follow [new-machine setup](../../docs/pipeline/new-machine-setup.md). Initialize your own model:

```text
python -m creation_pipeline init --model YOUR_ACCESSIBLE_CODEX_MODEL --output .pipeline/configs/descriptor.json
python -m creation_pipeline doctor .pipeline/configs/descriptor.json
```

Use the virtual environment's Python. `init` chooses Codex for both native and structured stages,
preserving the original 16-stage, 600/3600/2400-second budgets, interface, implementation, exact
layout and current business obligations. No acceptance_plan, artifact reference or passed marker
is supplied. The model identifier is your own choice; diagnostics cannot establish entitlement.

Only after online doctor reports ready, start a paid generation:

```text
python -m creation_pipeline build .pipeline/configs/descriptor.json --state-dir .pipeline/state --library-dir .pipeline/library --keep-debug
```

The first local request builds its own checked environment/tool; later exact local matches can reuse
the concrete tool while compiling current acceptance independently. Docker image and daemon identity
from someone else's machine is not reused. Refer to the new generation's output/summary and current
qualification, never the old experiment's passed flags. This operational threshold example is not an
independent scientific validation.
