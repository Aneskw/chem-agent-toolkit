---
name: derive-local-reaction-template-library
description: "Build a LocalRetro training template library from mapped reaction CSV rows, retaining edit metadata and the pinned extractor conventions."
license: undetermined
---


# Build a LocalRetro template library

Requires a full [LocalRetro checkout](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md) at `eba83e72efabeb854fec86c865e8743c295a8a1e` with RDKit, pandas and its documented dependencies. Use your own mapped training data; no pretrained model is needed for extraction.

Place `raw_train.csv` under `LocalRetro/data/<dataset>/`. Its required column is literally `reactants>reagents>production`; each value is the mapped reaction string expected by the extractor. Optional `class_train.csv` contains a `class` column aligned to training rows.

```bash
cd /path/to/LocalRetro/preprocessing
python Extract_from_train_data.py -d USPTO_50K
```

Read the generated `../data/USPTO_50K/atom_templates.csv`, `bond_templates.csv` and `template_infos.csv`. Optional class information produces `template_rxnclass.csv`. Preserve the associated hydrogen/charge/stereo edit metadata; SMARTS text alone is not the whole decoding contract. Existing output names may be replaced, so work in the intended dataset directory.

The pinned script uses minimum frequency 1 by default; `-min N` changes the exported class vocabulary and must match later preprocessing/model training. Do not pass the string `False` to its untyped boolean options expecting normal boolean parsing. CLI defaults and direct extraction-function settings are not interchangeable.

The extractor compares mapped reactants/products, handles atom and bond changes, skips unsuccessful extractions and exports counted templates. Check retained counts and parsing failures before training; successful CSV creation does not prove complete chemical coverage. To assign the library back to dataset rows, run upstream `Run_preprocessing.py -d USPTO_50K` from the same directory.

[Inspected implementation](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/preprocessing/Extract_from_train_data.py); [method paper](https://doi.org/10.1021/jacsau.1c00246). Data/license terms and mapped-reaction quality remain input requirements.
