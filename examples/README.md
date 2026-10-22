# Examples

Configurations provide resources, not expected candidate names or hand-written tasks.

## Installed RDKit modules

With RDKit already available:

```text
python examples/prepare_rdkit_sources.py
python -m creation_pipeline discover .pipeline/example-configs/rdkit-sources.json
python -m creation_pipeline build --plan .pipeline/outputs/<id>/plan.json --execute-generated-checks
```

The helper only points to installed BRICS and RECAP implementation files, including upstream examples/tests. It does not write skills, select capabilities or prescribe expected outputs.

## Paper and code

`builds/paper-code.json` uses the public Dimorphite-DL paper and a tagged implementation. Git retrieval records the actual commit. The paper describes an earlier software version; the model must distinguish paper claims from the inspected implementation. Runtime dependencies remain external.

```text
python -m creation_pipeline discover examples/builds/paper-code.json
```

`builds/minimal.json` is a template: replace its source path. `verify_python_example.py` is an optional helper for checking a Python block; it is not automatically run for every skill.
