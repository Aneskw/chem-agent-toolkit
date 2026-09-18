---
name: localretro-extract-local-template
description: >-
  Invoke for: converting an atom-mapped reaction into a LocalRetro-style local reaction SMARTS template and edit metadata. Do not use for retrosynthesis prediction.
license: CC-BY-NC-SA-4.0 (upstream README; see references)
allowed-tools: Read, Bash, Write
---

# LocalRetro local-template extraction

Use the pinned LocalTemplate implementation to convert one atom-mapped reaction into a structured local retrosynthesis template. The template is not a complete synthesis plan and must retain its edit, hydrogen, charge, and stereo metadata.

## Input and output

Input is `reactants>>products` with unique atom-map identifiers preserved on corresponding atoms. Output is JSON with `reaction_smarts`, edit metadata, settings, and an explicit `ok` value.

## Procedure

1. Restore the pinned LocalRetro source and RDKit environment.
2. Run `scripts/extract_template.py --source-root PATH_TO_LOCALRETRO --reaction 'MAPPED_REACTION'`.
3. Require `ok: true`, parse the reaction SMARTS with RDKit, and retain the full JSON result.

## Fixed cases

Use [examples/cases.json](examples/cases.json) for two positive and two negative cases. Expected checks cover a parseable reaction SMARTS, edit metadata, and rejection of missing or duplicate atom maps.

## Failure and recovery

Reject unmapped, duplicate-map, empty, or invalid reactions. Preserve the original input and error. Do not interpret a template as a complete synthesis route or claim broad extraction accuracy from the smoke cases.

## Reference

- Paper: https://doi.org/10.1021/jacsau.1c00246
- Upstream implementation: https://github.com/kaist-amsg/LocalRetro
