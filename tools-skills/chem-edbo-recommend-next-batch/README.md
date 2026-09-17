# chem-edbo-recommend-next-batch

EDBO-style Bayesian reaction optimization for recommending the next batch of experiments from a reaction space and observed yields. The implementation uses a Gaussian process and Expected Improvement without an LLM.

- Agent entry point: [SKILL.md](SKILL.md)
- Core implementation: [scripts/edbo_core.py](scripts/edbo_core.py) and [scripts/recommend_next_batch.py](scripts/recommend_next_batch.py)
- Literature and implementation mapping: [references/](references/)
- Demo data: [examples/](examples/)
- Tests: [tests/](tests/)
- Validation evidence: [results/RESULTS.md](results/RESULTS.md)

```bash
pip install -r requirements.txt
python tests/test_edbo_core.py
python tests/test_cli.py
python scripts/benchmark.py --quick
```

Method reference: Shields et al., *Nature* 2021, DOI: 10.1038/s41586-021-03213-y.
