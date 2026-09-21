---
name: generate-and-filter-chemical-reasoning-examples
description: >
  Draft procedure for constructing chemical reasoning examples with task-specific analyzer inputs, summarization, and quality-based retention. Invoke for: Choose inputs and model roles by reasoning task, generate and summarize a rationale, and retain it only when its assessment score is at least four out of five. Do not use as evidence of successful execution.
license: undetermined
compatibility: Unverified draft; inspect requirements and source license before use
allowed-tools: Read
---

# Generate And Filter Chemical Reasoning Examples

This cited draft describes Choose inputs and model roles by reasoning task, generate and summarize a rationale, and retain it only when its assessment score is at least four out of five. Applicable only when the listed inputs and resources exist. It is a `source_validated_candidate`, not an execution-validated package.

## Credibility

**Low confidence (Highly flexible)**. State: `draft_unexecuted`. Source-line citations were checked, but semantic completeness, dependencies and execution have not been verified.

## Reference

- paper: https://arxiv.org/pdf/2507.17448 (source s1p1; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p2; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p3; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p4; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p5; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p6; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p7; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p8; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p9; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p10; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p11; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p12; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p13; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p14; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p15; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p16; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p17; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p18; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p19; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p20; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p21; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p22; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p23; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p24; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p25; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p26; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)
- paper: https://arxiv.org/pdf/2507.17448 (source s1p27; SHA-256 969d1069e17245e7ed942e72c9ceeb2e2c7da44d71d847f4b958f6c4f4ddfc8d)

## Input & Output

Inputs:

- A selected task with its corresponding evidence: molecular SMILES and IUPAC name for structure analysis; reaction SMILES for reaction analysis; or product SMILES, IUPAC name, and ground-truth reactants for retrosynthesis analysis. (s1p19:L30-L31, s1p19:L33-L35, s1p19:L36-L37)

Outputs:

- Concise chemical reasoning examples passing an overall assessment threshold of at least four on a five-level scale. (s1p19:L27-L29)

## Procedure Guidance

- For molecular-structure analysis, ask the Analyzer to identify functional groups and molecular connectivity. For reaction analysis, request functional-group transformations and bond changes. For retrosynthesis analysis, request product-structure analysis, reaction-site identification, and the proposed transformation. (s1p19:L31-L32, s1p19:L34-L35, s1p19:L37-L38)
- Use Qwen3-235B-A22B-Instruct for both Analyzer and Summarizer on molecular and reaction reasoning. For retrosynthesis reasoning, use DeepSeek-R1 as Analyzer and DeepSeek-V3 as Summarizer. Use MiniMax-M2.7 for assessment. (s1p19:L43-L43, s1p19:L43-L43, s1p20:L1-L1)
- Generate a detailed analysis, then have the Summarizer refine it into a concise, coherent rationale. (s1p19:L25-L27, s1p19:L26-L27)
- Assess chemical correctness and logical consistency on a five-level scale; retain scores of at least four and exclude lower-scoring examples. (s1p19:L28-L29)

## Matters & Troubleshooting

Resources:

- external_asset: Qwen3-235B-A22B-Instruct — Analyzer and Summarizer for molecular and reaction reasoning.
- external_asset: DeepSeek-R1 — Analyzer for retrosynthesis reasoning.
- external_asset: DeepSeek-V3 — Summarizer for retrosynthesis reasoning.
- external_asset: MiniMax-M2.7 — Assessment model used to filter reasoning examples.

Unknowns and limits:

- Exact generation prompts, scoring rubric, and model configurations are referred to Supplementary Section F, which is not supplied.
- No retry or revision policy for rejected examples is specified.
- No implementation files or model invocation interfaces are supplied.
