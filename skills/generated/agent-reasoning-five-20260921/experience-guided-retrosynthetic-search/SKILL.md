---
name: experience-guided-retrosynthetic-search
description: >
  Draft procedure for planning a retrosynthetic route with an experience-guided AND-OR tree search, propagating success and failure, and extracting a route to available building blocks. Invoke for: Alternate selection, expansion, and upward updates under a search budget, then traverse successful reaction branches to construct a reaction list. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Experience Guided Retrosynthetic Search

This cited draft describes Alternate selection, expansion, and upward updates under a search budget, then traverse successful reaction branches to construct a reaction list. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p1; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p2; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p3; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p4; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p5; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p6; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p7; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p8; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p9; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p10; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p11; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p12; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p13; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)
- paper: https://www.nature.com/articles/s42004-023-00911-8.pdf (source s1p14; SHA-256 a8695033ce441badf047c23dad0fec3fd1cdc882f0a12fae57ceeb1367b302ab)

## Input & Output

Inputs:

- A target molecule, building-block set B, and single-step retrosynthetic model that predicts top-k reaction templates and their probabilities. (s1p3:L3-L8, s1p3:L7-L8)
- A trained Experience Guidance Network (EGN) and a search-cost budget. (s1p3:L42-L45, s1p3:L57-L58)

Outputs:

- An AND-OR search tree with molecules as OR nodes and reaction templates as AND nodes. (s1p9:L17-L18)
- A reaction list describing a route to building blocks, or an empty list if route extraction encounters an unresolved non-building-block molecule. (s1p12:L45-L49, s1p12:L50-L51)

## Procedure Guidance

- Represent the search as an AND-OR tree. Mark a molecule successful if it belongs to B or has a successful reaction child; mark it unsuccessful if every reaction child fails or no template applies. A reaction succeeds only when every reactant succeeds and fails when any reactant fails. (s1p9:L24-L27, s1p9:L28-L30, s1p9:L24-L25)
- Select reaction children of molecule nodes using the paper's PUCT policy. At reaction nodes, randomly prioritize unexpanded molecule children; otherwise randomly choose a child not yet proven successful. Repeat until reaching a molecule leaf. (s1p9:L32-L36, s1p9:L35-L36, s1p9:L52-L55)
- Expand the selected molecule with the single-step model. If it returns no templates, mark the molecule unsuccessful. Otherwise add each template as a reaction child, initialize its score from EGN, apply it, and add its reactants as molecule children. (s1p10:L1-L4, s1p10:L5-L7, s1p10:L6-L9)
- Update upward from the selected molecule. Check molecule success or failure; for a molecule not proven unsuccessful, set its value to the highest average reaction score among its children. (s1p10:L10-L12, s1p11:L1-L2)
- At each reaction node, increment its update count. Assign reward z > 1 for proven success, −z for failure, or the mean value of its molecule children otherwise. Average recorded rewards together with the initial EGN score. (s1p11:L6-L11, s1p11:L6-L7, s1p11:L14-L18)
- Continue upward updates until the tree remains unchanged. Repeat selection, expansion, and update until the search budget is exhausted. (s1p4:L67-L69, s1p4:L78-L79)
- Extract a route by initializing a queue with the root and an empty reaction list. Pop molecules in queue order. For each molecule outside B, choose a successful reaction child, enqueue all its reactants, and append the reaction. If no successful child exists, fail and clear the list; otherwise return the list when the queue empties. (s1p12:L38-L41, s1p12:L41-L45, s1p12:L45-L49)

## Matters & Troubleshooting

Resources:

- external_asset: https://github.com/jjljkjljk/EG-MCTS — The paper identifies this repository as its implementation source; implementation files are absent from the supplied snapshot.

Unknowns and limits:

- No implementation files, callable interface, checkpoint paths, or dependency versions are supplied.
- The extracted PUCT equation has damaged mathematical formatting; exact implementation, root handling, and zero-count handling cannot be verified.
- The value of k, cycle handling, and the choice among multiple successful reaction children are not specified in the supplied procedural text.
- Search success establishes a route within the model; reaction conditions, yields, and laboratory feasibility are not established.
