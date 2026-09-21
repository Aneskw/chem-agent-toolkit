# Chemical Skill Extraction Contract v1

## Purpose

This contract is the model-facing intermediate representation used by the
current creation pipeline:

```text
source bundle -> extraction contract -> citation validation -> SKILL.md draft
```

Its sole purpose is to improve source-grounded Skill extraction. It is not a
skill-tree record, evaluation record, deduplication decision, or admission
decision.

## Extraction rules

1. Extract reusable procedures, not paper summaries.
2. Give every source-derived claim exact source-line citations.
3. Prefer information that changes agent behavior: applicability, branches,
   checks, stop conditions, and fallback behavior.
4. Do not invent environments, commands, parameter defaults, scripts, tests,
   or troubleshooting advice.
5. Put important missing information in `unknowns`.
6. Distinguish a conditional `method_procedure` from an atomic `tool_usage`
   operation.
7. Return no candidate when the supplied sources do not support a useful
   procedure.

## Canonical response

`contract_version` identifies this operational contract; it is not a Skill
version. `schema_version` is the machine-readable JSON layout version. The
model returns zero to four candidates.

For readability, `citations: []` below is only a placeholder. In a real model
response, every claim object that is present must contain at least one
`Citation` object in the format shown under **Evidence claims**.

```yaml
contract_version: "1.0"
schema_version: 2
paper_id: "<pipeline job id>"

candidates:
  - name: "lowercase-kebab-case"
    description: "One-sentence capability description."
    kind: method_procedure
    # method_procedure | tool_usage
    operation: "The concrete task this candidate performs."

    invoke_when:
      - text: "A positive task condition that should trigger this Skill."
        citations: []

    do_not_invoke_when:
      - text: "A nearby but unsupported or inappropriate task."
        citations: []

    preconditions:
      - text: "A condition or resource that must exist before starting."
        citations: []

    inputs:
      - text: "Required input, format, unit, or state."
        citations: []

    outputs:
      - text: "Expected output, format, unit, or blocked/error state."
        citations: []

    steps:
      - text: "An ordered procedural action."
        citations: []

    decision_points:
      - condition:
          text: "Evidence or state that selects a branch."
          citations: []
        if_true:
          text: "Action when the condition holds."
          citations: []
        if_false:
          text: "Alternative, fallback, or abstention."
          citations: []

    verification_checks:
      - text: "How an intermediate or final result should be checked."
        citations: []

    stop_conditions:
      - text: "When to stop, abstain, or request another resource."
        citations: []

    requirements:
      - kind: external_asset
        # repo_file | external_asset
        path: "https://example.org/resource"
        reason:
          text: "Why the requirement is necessary."
          citations: []

    unknowns:
      - "Important information absent from the supplied sources."

no_skill_reason: "Required when candidates is empty; otherwise empty."
```

`do_not_invoke_when`, `preconditions`, `decision_points`,
`verification_checks`, `stop_conditions`, `requirements`, and `unknowns` may
be empty. The model must not fabricate content merely to populate them.

The implementation uses JSON schema version `2` for this contract. Saved
schema version `1` responses are upgraded during replay with empty new fields;
they are not misrepresented as fresh contract-guided extractions.

## Evidence claims

Every `text` object is an evidence claim. Citations use the existing pipeline
format:

```yaml
text: "Generate output SMILES using beam search with beam size 30."
citations:
  - source_id: s6
    start: 49
    end: 50
    quote: "Beam search with a beam size of 30 ..."
```

The validator requires a known source, valid 1-based lines, a narrow span, and
an exact short quote within that span. Unsupported claims belong in
`unknowns`, not in procedural fields.

## Candidate quality gates

### `method_procedure`

A fresh method candidate must contain:

- at least one cited positive trigger;
- at least one cited input and output;
- at least two cited ordered steps;
- at least one cited decision point, verification check, or stop condition;
- a procedural claim cited to the source type's primary document;
- unknowns for important missing implementation details.

### `tool_usage`

An atomic resource candidate states its operation, inputs, outputs, required
resource, and any documented error behavior. It includes an invocation only
when supplied documentation or pinned code supports it. A single invocation
is not promoted to a research-level procedural Skill.

### No candidate

Return no candidate when only metadata, abstract, or marketing text is
available; useful details would need to be invented; or the candidate merely
renames an existing command without reusable guidance.

## Mapping to `SKILL.md` v0.3

The renderer compiles the validated contract deterministically:

| Contract fields | `SKILL.md` destination |
| --- | --- |
| `name`, `description`, `invoke_when`, `do_not_invoke_when` | frontmatter and opening applicability |
| pipeline validation state | `## Credibility` |
| source bundle and claim citations | `## Reference` |
| `inputs`, `outputs` | `## Input & Output` |
| `steps`, `decision_points`, `verification_checks`, `stop_conditions` | `## Procedure Guidance` |
| `preconditions`, `requirements`, `unknowns` | scope and `## Matters & Troubleshooting` |

The renderer, not the extraction model, assigns the draft label and confidence
floor. A source-cited but unexecuted candidate remains low confidence and must
not claim successful execution or agent benefit.

## Implementation files

- `core/creation_schema.py`: JSON schema, legacy upgrade, quality gates, and
  citation validation.
- `core/creation.py`: extraction prompt and model response handling.
- `repair_citation_spans.py`: bounded citation-span repair for all contract
  claims.
- `render_drafts_v03.py`: deterministic contract-to-`SKILL.md` compilation.
- `tests/test_creation_contract.py`: contract validation, quality-gate,
  rendering, and legacy replay tests.
