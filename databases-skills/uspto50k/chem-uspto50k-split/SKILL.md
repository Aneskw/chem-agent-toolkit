---
name: chem-uspto50k-split
description: Validate local USPTO-50K reaction split files and report schema, row counts, and overlap before model training or evaluation.
license: Dataset terms vary by source
allowed-tools: Bash(python3:*)
---

# USPTO-50K split validation

Use for checking a local, preprocessed USPTO-50K-style dataset before retrosynthesis experiments. This is a data-quality skill, not a downloader and not a license determination. The dataset is not bundled in this repository.

## reference

Project evidence identifies `USPTO50K` as a dataset option with train/valid/test files and model-specific preprocessing. Keep the exact source, preprocessing commit, split convention, and any atom-mapping policy in the run record.

## 输入&输出

输入、输出和错误语义以脚本的 JSON 记录为准。`ok: false` 时不得把部分结果当作成功；模型或数据库结果不等于实验验证。

## 使用步骤

1. 先读 `references/api.md`，确认接口、版本和输入约束。
2. 运行 `scripts/validate_split.py` 或上游 CLI，保存 stdout、stderr 和退出码。
3. 对照 `examples/` 检查字段；缺少依赖、权重或数据时标记为 `blocked_resources`。

## 失败与恢复

- 输入不完整或格式错误：修正输入并保留原始请求。
- 依赖、网络、权重或数据缺失：报告具体缺口，恢复环境后再运行，不伪造结果。
- 相同错误连续出现时停止重试并保留日志。
