---
name: graph-aware-molecular-attention
description: >
  Draft procedure for incorporating molecular topology into global attention, with separate distance buckets for nearby atoms, distant atoms, and atoms in different molecules. Invoke for: Assign atom pairs to shortest-path distance buckets, retrieve learned positional embeddings, and incorporate them into global attention over local atom representations. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Graph Aware Molecular Attention

This cited draft describes Assign atom pairs to shortest-path distance buckets, retrieve learned positional embeddings, and incorporate them into global attention over local atom representations. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2110.09681 (source s1; SHA-256 cad00c55652c0c52f2f3a9cbb0848583409b69bd91d351940cf4f6fcd035c1e2)
- paper: https://arxiv.org/pdf/2110.09681 (source s2; SHA-256 cafe83f6e6a481d3ac3a387dacf2e3b4e1c829bee9889921575432e884d45d36)
- paper: https://arxiv.org/pdf/2110.09681 (source s3; SHA-256 e166817e297ab2e64844e8007a5c8b5f73f6b30d5343af264dc225e0f739126c)
- paper: https://arxiv.org/pdf/2110.09681 (source s4; SHA-256 2d322d9f393a176ca0c499ba192ca2f66ce4bf533f1efb0e252284455789300c)
- paper: https://arxiv.org/pdf/2110.09681 (source s5; SHA-256 1b791c271eda4161f8ff12564db3b95f2e23fd3597e2d9acade4cfaddd2e5cc4)
- paper: https://arxiv.org/pdf/2110.09681 (source s6; SHA-256 186f4869d98c097f47fdb23c57296bb5c92168bd3a4ffc24c063cd9c13651f39)
- paper: https://arxiv.org/pdf/2110.09681 (source s7; SHA-256 d4e1dd88c1688b2a21068b40781d658fbca1ca3be90dd3231be8b1c287f7fb26)
- paper: https://arxiv.org/pdf/2110.09681 (source s8; SHA-256 220c15c961193e22632dff1eb5c8e2ea0f16c8eeb1b1da725776f6ab51b1141b)
- paper: https://arxiv.org/pdf/2110.09681 (source s9; SHA-256 ed9e4f80f742ac2cada56b43f710990fc5ef907f0659e330a4507d1b3c1e1eea)
- paper: https://arxiv.org/pdf/2110.09681 (source s10; SHA-256 08a57cccdbaf509d32725176ca604c4cb26f92dca4017e0178815432f946a144)
- paper: https://arxiv.org/pdf/2110.09681 (source s11; SHA-256 a6df459494b09cb0f9fe0d95a54f4bed0044132d0fb157f05cba95ce7b2e1552)
- paper: https://arxiv.org/pdf/2110.09681 (source s12; SHA-256 bf474b593f93fa34a2f147265d5ed84a211b7497f383b0fcebe2e42cde8006b6)
- paper: https://arxiv.org/pdf/2110.09681 (source s13; SHA-256 59b1d7089da8c0402b0f37fee959617834ff661c079497880fafe17b4244975c)
- paper: https://arxiv.org/pdf/2110.09681 (source s14; SHA-256 8014d0cd26236da86d9a38fe50d06d27b93ccc4ee245de3f3f11697225c8964a)
- paper: https://arxiv.org/pdf/2110.09681 (source s15; SHA-256 21e6c053c3e52f9cf57926cb66aa398656d03530977a3e47082ca5c0274a00df)
- paper: https://arxiv.org/pdf/2110.09681 (source s16; SHA-256 5cd2461a6110aa6cb383071313006f596f31d9a804915496d34218658816a41f)

## Input & Output

Inputs:

- Input molecular graphs, potentially containing multiple molecules, with atom and directed-bond features. (s2:L40-L43)
- Atom representations produced by the directed message passing encoder. (s4:L44-L45)

Outputs:

- Atom representations incorporating global interactions and graph-relative positional information. (s3:L118-L120)

## Procedure Guidance

- For global interactions between encoded atoms, use a learned relative positional embedding determined by their shortest-path length. (s4:L62-L63)
- If two atoms belong to different molecules, assign bucket 10. Otherwise, use their distance directly below 8, bucket 8 for distances from 8 through 14, and bucket 9 for distances of at least 15. (s4:L102-L105)
- Use each bucket index to retrieve its positional embedding from the trainable embedding matrix. (s4:L106-L106)
- Compute attention with separate input–input and input–relative-position contributions as in Equation 12; share the learned biases across layers. (s4:L91-L93)
- Complete the global encoder using multiheaded self-attention, layer normalization, and position-wise feed-forward layers, without adding positional information to value vectors. (s4:L107-L109, s4:L108-L109)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/coleygroup/Graph2SMILES — The paper identifies this repository as its reproduction implementation; no implementation files are supplied in the snapshot.

Unknowns and limits:

- No implementation files, repository commit, or callable interface are supplied.
- The shortest-path algorithm and handling of disconnected components within a molecule are unspecified.
- The supplied text does not specify positional-embedding initialization or a numerical verification tolerance.
