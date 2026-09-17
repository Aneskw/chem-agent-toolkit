# chem-edbo-recommend-next-batch

原子级化学 skill：**EDBO 贝叶斯反应优化推荐** —— 给定反应空间与已有产率数据，
推荐下一批最值得做的实验条件（高斯过程 + Expected Improvement，纯数值实现，不调用大模型）。

- 主文档（Agent 入口）：[SKILL.md](SKILL.md)
- 核心实现：[scripts/edbo_core.py](scripts/edbo_core.py)（库）+ [scripts/recommend_next_batch.py](scripts/recommend_next_batch.py)（CLI）
- 文献依据：[references/edbo-literature.md](references/edbo-literature.md)｜[references/implementation-mapping.md](references/implementation-mapping.md)
- 演示数据：[examples/](examples/)
- 测试：[tests/](tests/)

快速验证：

```bash
python tests/test_edbo_core.py      # 9 项单元测试（含 Branin 收敛基准）
python tests/test_cli.py            # 2 项 CLI 端到端测试
```

方法依据：Shields et al., "Bayesian reaction optimization as a tool for chemical synthesis",
*Nature* **2021**, 590, 89–96（DOI: 10.1038/s41586-021-03213-y）。
