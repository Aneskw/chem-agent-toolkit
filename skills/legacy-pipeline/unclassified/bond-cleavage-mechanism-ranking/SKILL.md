---
name: bond-cleavage-mechanism-ranking
description: "Compare candidate bond cleavage under radical and ionic mechanisms. Invoke for: ranking weak bonds when the cleavage mechanism matters; not for predicting rates from bond energies alone."
license: MIT
---

# Bond Cleavage Mechanism Ranking

## Applicability

Use for ranking specified single bonds by homolytic or heterolytic dissociation energy. Do not equate a low dissociation energy with the dominant experimental pathway without accounting for environment and barriers.

## Input & Output

Input: molecular graph, eligible bonds, cleavage mechanism, environment, and energy method. Output: separate homolytic and heterolytic rankings, fragment charge/spin assignments, units, and excluded bonds with reasons.

## Procedure Guidance

Enumerate bonds on a hydrogen-complete graph when X-H cleavage is in scope. For homolysis, compare spin-consistent radical fragments conserving the parent charge with the intact molecule on one energy scale. For heterolysis, evaluate both charge polarities; retain the lower valid energy and do not invent an unsupported isolated-ion reference. If a fragment type is outside the method's domain, mark that bond unresolved rather than transferring its homolytic score. Keep atom indices stable across fragmentation and verify every eligible bond appears once.

## Success Criteria

Each requested ranking covers exactly its eligible bonds, with internally consistent energy references and an explicit weakest bond for each mechanism.

## Matters & Troubleshooting

Solvent, counterions, spin contamination, and geometry relaxation can reverse rankings. Report these assumptions before interpreting a ranking as reactivity.
