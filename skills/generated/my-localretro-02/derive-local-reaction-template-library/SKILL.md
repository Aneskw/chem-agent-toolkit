---
name: derive-local-reaction-template-library
description: >-
  Draft procedure for deriving atom and bond reaction templates from mapped training reactions, retaining multiple changes and optionally associating templates with reaction classes. Invoke for: Compare mapped reactants and products, extract and validate local transformations, classify their edit sites, and export a template library. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Derive Local Reaction Template Library

This cited draft describes Compare mapped reactants and products, extract and validate local transformations, classify their edit sites, and export a template library. Applicable only when the listed inputs and resources exist; it is not a verified executable package.

## Credibility

**Low confidence (Highly flexible)**. State: `blocked_resources`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8549044/fullTextXML (source s1; SHA-256 0bb218ba3f78a0ee0bafe9ab9b8ab2523147819a3deee7a9a6991cfa4e34bcb5)
- repo_doc: https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/README.md (source s2; SHA-256 f8d7644b3d864f1af6bafa4c7107468e9c1051254af11909a1c365d2caba3190)
- repo_code: https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/LocalTemplate/template_extractor.py (source s3; SHA-256 31749a76084707bed5f6a363fdd83d4f8032126888560fb3b31cf31e267d66ee)
- repo_code: https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/preprocessing/Extract_from_train_data.py (source s4; SHA-256 7c476b821247f22026875560f81e970df9df8461c541f0d53118b074b3b5c58b)

## Input & Output

Inputs:

- Atom-mapped reactant/product reactions from a training dataset. (s1:L92-L95)
- For the supplied training extractor, data/<dataset>/raw_train.csv with the column reactants>reagents>production; optional class_train.csv with a class column. (s4:L49-L54, s4:L51-L54)

Outputs:

- Atom and bond template CSV files, template metadata, and a reaction-class association file when class labels are available. (s2:L74-L78, s4:L132-L136)

## Procedure Guidance

- Run the documented training-set extraction entry point from the preprocessing directory with the selected dataset. (s2:L65-L72)
- Identify changes by comparing corresponding mapped atoms and bonds. Derive an atom template when no bond changes or disconnections occur; otherwise derive a bond template. Mark a template as both when atom and bond changes coexist. (s1:L112-L115, s1:L114-L115, s3:L82-L88)
- Include all changed atoms and bonds for reactions with multiple products or multiple changes, and construct fragments around the changed atoms on both reaction sides. (s1:L102-L104, s3:L572-L573)
- Stop extraction for a reaction when no changed atoms are found. Canonicalize the transformation, orient it product-to-reactants for retrosynthesis, and reject templates with reaction-validation errors. (s3:L565-L569, s3:L585-L585, s3:L596-L599, s3:L602-L604, s3:L609-L609)
- Skip unsuccessful extraction results; count retained templates, associate them with supplied reaction classes, and export template classes meeting the configured minimum frequency. (s4:L72-L74, s4:L91-L91, s1:L108-L110, s4:L149-L153)

## Matters & Troubleshooting

Resources:

- repo_file: preprocessing/Extract_from_train_data.py — Documented entry point for deriving the training template library.
- repo_file: LocalTemplate/template_extractor.py — Provides the extraction function imported by the training script.
- repo_file: LocalTemplate/template_extract_utils.py — Supplies helper functions imported by the extractor.
- repo_file: data/USPTO_50K/raw_train.csv — Required input for the documented USPTO_50K invocation; absent from the recorded inventory.
- repo_file: data/USPTO_50K/class_train.csv — Optional input needed for class associations in the implementation; absent from the recorded inventory.

Unknowns and limits:

- The README names train_class.csv, while the implementation reads class_train.csv.
- The supplied implementation imports edit-label helpers whose contents are not supplied; the detailed correspondence between edit codes and the paper's atom/bond categories cannot be fully checked.
- The CLI and direct extraction function use different stereo and atom-symbol defaults; they should not be treated as interchangeable configurations.
- Raw training data and optional class labels are absent from the recorded snapshot. No extraction was executed.
