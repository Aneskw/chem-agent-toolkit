---
name: parent-standardized-lead-triage
description: >-
  Screen oral-lead candidates on comparable parent structures. Invoke for: descriptor-based triage of salts and prodrugs; not for declaring clinical developability from rule-of-five filters.
license: MIT
compatibility: RDKit with MolStandardize and supplied descriptor thresholds
allowed-tools: Read, Bash
---

# Parent-Standardized Lead Triage

## Applicability

Use for comparing physicochemical descriptors across a heterogeneous hit list. Preserve original records so the selected parent can be traced back to its formulation.

## Credibility

**low confidence (Highly flexible).** The workflow is adapted from a benchmark task; clinical relevance and decision gain are untested.

## Reference

[ADMET lead triage task](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/admet-lead-triage/instruction.md) and [test contract](https://github.com/learningmatter-mit/AtomisticSkillsBenchmark/blob/db6116c1833f30cccb65ff78cda175510c3107b6/tasks/drug-discovery/admet-lead-triage/tests/test_outputs.py).

## Input & Output

Input: compound IDs and structures, standardization policy, descriptor definitions, and thresholds. Output: parent structure mapping, descriptors, per-rule pass/fail, ranked candidates, and uncertainty.

## Procedure Guidance

Clean structures, select the relevant parent fragment, and apply a stated neutralization policy before descriptors. If neutralization changes the intended active microstate or covalent prodrug, retain both forms and flag the decision. Compute all rule counts independently over the full list; do not turn sequential screen survivors into denominators. For Lipinski's rule of five, distinguish a violation count from pass/fail; for Veber, distinguish TPSA and HBD+HBA alternatives. Rank only after thresholds and tie breakers are declared.

## Success Criteria

Every input has a traceable standardized parent, independent rule outcomes, and a reproducible final ordering.

## Matters & Troubleshooting

These filters are heuristics, not potency, toxicity, bioavailability, or synthesis evidence.
