---
name: graphretro-beam-search-retrosynthesis
description: >
  Draft procedure for predicting single-step reactants by searching over product edits and component-wise leaving group selections, followed by constrained attachment. Invoke for: Retain the highest-scoring edit and leaving group hypotheses through beam search until every synthon component has a leaving group prediction, then construct candidate reactants. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Graphretro Beam Search Retrosynthesis

This cited draft describes Retain the highest-scoring edit and leaving group hypotheses through beam search until every synthon component has a leaving group prediction, then construct candidate reactants. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

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

- A target product molecular graph. (s4:L22-L23)
- A beam width n and edit scores for the product. (s6:L31-L33)
- A leaving group selection model using product, synthon component, and previous leaving group representations. (s5:L57-L59)

Outputs:

- Candidate reactants obtained by attaching selected leaving groups to their corresponding synthons. (s3:L49-L50)

## Procedure Guidance

- Select the n highest-scoring edits, apply them to the product, and use the resulting synthon hypotheses as beam search nodes. (s6:L32-L33, s6:L33-L33)
- Maintain each node's cumulative score as the sum of edit and predicted leaving group log-likelihoods. (s6:L34-L35)
- For the next connected component of each retained synthon hypothesis, expand with the n highest-likelihood leaving groups and retain the n nodes with the highest cumulative scores. (s6:L35-L37)
- Repeat expansion and pruning until every retained node has a leaving group prediction for every synthon component. (s6:L37-L38)
- Attach marked leaving group atoms to atoms participating in the edit, inferring bond types using valency constraints and preserving stereochemistry. (s6:L24-L27, s6:L26-L28)

## Matters & Troubleshooting

Resources:

- None identified.

Unknowns and limits:

- No implementation files, model checkpoints, executable interface, or asset paths are supplied.
- The detailed attachment procedure is referenced through an unresolved appendix pointer and is absent from the bundle.
- Beam width defaults, tie handling, invalid attachment handling, and duplicate candidate handling are unspecified.
- The multiple-edit prediction procedure is not supplied.
- The formulation assumes equal numbers of synthons and reactants; handling reactions that violate this assumption is not provided.
- An incorrect edit prevents recovery of the true reactants within that hypothesis.
