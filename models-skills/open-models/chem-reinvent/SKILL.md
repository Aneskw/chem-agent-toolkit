---
name: chem-reinvent
description: Use the REINVENT4 molecular design CLI for configured de novo generation or optimization while preserving the configuration and generated SMILES for audit.
license: Apache-2.0
allowed-tools: Bash(reinvent:*)
---

# REINVENT4 molecule generation

Use when a user has a REINVENT4 installation and a TOML configuration for de novo design, scaffold hopping, R-group replacement, linker design, or optimization. This package provides a preflight wrapper only; it does not download checkpoints or claim generated molecules are synthesizable.

## reference

Repository: https://github.com/MolecularAI/REINVENT4

The upstream CLI is configuration-driven. Pin the repository revision, configuration file, scoring components, random seed, and output directory.

## 输入&输出

输入、输出和错误语义以脚本的 JSON 记录为准。`ok: false` 时不得把部分结果当作成功；模型或数据库结果不等于实验验证。

## 使用步骤

1. 先读 `references/api.md`，确认接口、版本和输入约束。
2. 运行 `scripts/preflight.py` 或上游 CLI，保存 stdout、stderr 和退出码。
3. 对照 `examples/` 检查字段；缺少依赖、权重或数据时标记为 `blocked_resources`。

## 失败与恢复

- 输入不完整或格式错误：修正输入并保留原始请求。
- 依赖、网络、权重或数据缺失：报告具体缺口，恢复环境后再运行，不伪造结果。
- 相同错误连续出现时停止重试并保留日志。
