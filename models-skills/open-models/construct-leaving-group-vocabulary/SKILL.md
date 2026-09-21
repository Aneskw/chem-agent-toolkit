---
name: construct-leaving-group-vocabulary
description: >
  Draft preprocessing procedure for deriving leaving group classes and attachment markers from atom-mapped synthon–reactant pairs. Invoke for: Extract edits from mapped reactions, align resulting synthons with reactant components, and collect unique residual subgraphs with tokens for completion control and batching. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Construct Leaving Group Vocabulary

This cited draft describes Extract edits from mapped reactions, align resulting synthons with reactant components, and collect unique residual subgraphs with tokens for completion control and batching. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p1-c1.txt (source s1; SHA-256 20bdc06e6548603fae9b302f207c83955104b74c3667905145d10ad8114e2acb)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p2-c1.txt (source s2; SHA-256 d16d81aef678813f9be7489f4329338ea01057303d70a3f4a13522a34d093d6f)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p3-c1.txt (source s3; SHA-256 0cda0f5ffc4169bc30c1ef95ce9d4c856452e745e2992cb56351483e657935e1)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p4-c1.txt (source s4; SHA-256 9d0f51245e82c2aaf97be3791bf4a2ef87ce0763be922cdf5dc6f67da912ef39)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p5-c1.txt (source s5; SHA-256 9b9fa2faf0273389abe016a72fe28a280aadbe58e5a6d129de390592b5ac3697)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p6-c1.txt (source s6; SHA-256 b61c43d1d0e53dfb18c2ca6cf314b9e233026dd12986eca4421014b2931fb3fd)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p7-c1.txt (source s7; SHA-256 94ebfa6289aa7158ae3152eea2fc59d9339200a2bc2daa4ba430d423680cde93)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p8-c1.txt (source s8; SHA-256 f06c9bdf4e4e20b6528487f4c8439a6da5642529562bd34e2ec8ce1fa3283c06)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p9-c1.txt (source s9; SHA-256 5115572d9c03be56b27812aaab80796acf9b81bcb08011519433613399828122)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p10-c1.txt (source s10; SHA-256 fb1efa6b61c71b36a778ff32bd8555bacf543af4406f1756f1a0aaf811d11029)
- paper: /Users/xllin/Documents/Codex/2026-09-06/w/outputs/chem-agent-toolkit/creation_pipeline/intakes/graphretro-manual-01/normalized/source-001-s1-p11-c1.txt (source s11; SHA-256 50f2a0673046ba8125b62bbd37ca27482393319054518230e3d55515995e726d)

## Input & Output

Inputs:

- Atom-mapped product–reactant training pairs. (s4:L11-L13)

Outputs:

- A vocabulary of unique leaving group subgraphs with marked attachment atoms and START, END, and PAD tokens. (s5:L42-L43, s5:L53-L55)

## Procedure Guidance

- Compare mapped product atoms and atom pairs with their reactant counterparts to identify changes in bond type and attached hydrogen count. (s4:L9-L11, s4:L12-L13)
- Apply the identified edits to the product graph to obtain synthons. (s4:L14-L15)
- Align connected components of the synthon and reactant graphs by comparing their atom mapping overlaps. (s5:L49-L50)
- For each aligned pair, extract the leaving group subgraph whose atoms occur in the reactant but not the synthon, and mark the atoms that attach to the synthon. (s5:L51-L53)
- Collect unique leaving groups and add START for beginning completion, END when no leaving group is needed, and PAD for variable component counts in minibatches. (s5:L43-L43, s5:L53-L55)

## Matters & Troubleshooting

Resources:

- None identified.

Unknowns and limits:

- No preprocessing implementation or dataset file paths are supplied.
- The exact attachment-marker encoding and graph deduplication algorithm are unspecified.
- Tie resolution for component alignment and handling of inconsistent atom mappings are unspecified.
- The source assumes the same number of connected components for synthons, leaving groups, and reactants; an alternative procedure for violations is not supplied.
