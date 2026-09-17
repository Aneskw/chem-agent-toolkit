---
name: chem-openmm-md
description: Prepare and preflight OpenMM molecular simulation inputs and report available platforms without claiming a completed simulation.
license: MIT
allowed-tools: Bash(python3:*)
---

# OpenMM simulation preflight

Use before molecular dynamics or energy minimization. The current package performs a dependency/platform preflight only; it does not invent a topology, force field, trajectory, or scientific result. A real run must supply a system XML or a separately documented modeller workflow.

## reference

Upstream: https://github.com/openmm/openmm

OpenMM exposes platforms such as Reference, CPU, CUDA, and OpenCL depending on the installation. Record OpenMM version and the selected platform in any run report.

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
