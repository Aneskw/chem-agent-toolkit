# P2 integration inputs

`skill-a.json` and `skill-b.json` are ordinary public CLI configurations. Their
tool requirements are identical; the final prose audience and batch labels differ.
They contain neither an acceptance plan nor an artifact selection or qualification.
Set the two shared registry environment variables to the same explicit directories
for both invocations. Source paths in these local configurations must point to this
checkout; changing source identity can intentionally change the exact request.

`source/` is a new integration assembly, not an untouched historical Skill.
`scripts/calc_descriptors.py` and `requirements.txt` preserve the original read-only
RDKit descriptor sample bytes. The new `scripts/triage.py` calls that module and
reads the declared `scripts/data/rules.json` relative to its own module location.
The 50.0 threshold is an operational example, not a scientific or safety standard.
Keep raw fixture bytes: declarations identify raw SHA256, including line endings.

`phase3/` and `protocol-source/` preserve an intermediate experiment that manually
supplied layout protocol facts. They are historical evidence, not required setup.
The final ordinary configurations above rely on the automatically supplied host
execution layout for both author and independent reviewer.

See [the report](../../../docs/integration/bundled-json-tool-20261101.md) for exact
commands, independent run directories, failures, successful evidence and limits.
