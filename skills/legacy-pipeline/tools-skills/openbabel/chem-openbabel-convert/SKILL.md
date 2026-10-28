---
name: chem-openbabel-convert
description: "Convert a molecular file with explicit Open Babel formats, preserving the input and inspecting output diagnostics."
license: GPL-2.0-or-later
---


# Convert a molecular file

Install [Open Babel](https://openbabel.org/docs/Installation/install.html), expose `obabel` on PATH and record `obabel -V`. The wrapper needs Python 3.10+ but no Python Open Babel binding.

```bash
python <skill-dir>/scripts/convert_molecule.py --input molecules.sdf   --input-format sdf --output-format mol2 --output converted.mol2
```

Choose a destination different from the input; use a new filename to preserve any existing output. Format IDs follow `obabel -L formats`. The direct equivalent is `obabel -isdf molecules.sdf -omol2 -O converted.mol2`.

Require exit **0**, `ok:true` and the requested nonempty file. Read `stderr` even on success: individual molecules or properties may be skipped or changed. Compare record counts and the stereo/charge/coordinate fields required downstream; a conversion success is not structure repair. Exit **2** reports input, executable or conversion failure.

This wrapper performs format conversion only: it does not generate 3D coordinates, add missing chemistry or guarantee every format preserves every property. Use documented upstream options explicitly if those operations are required.

[Official CLI reference](https://openbabel.org/docs/Command-line_tools/babel.html).

The wrapper requires a new output path and refuses to overwrite an existing file.
