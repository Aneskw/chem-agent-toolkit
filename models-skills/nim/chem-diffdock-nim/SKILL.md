---
name: chem-diffdock-nim
description: Prepare a DiffDock protein-ligand docking request through a configured NVIDIA NIM endpoint and preserve the request and response metadata.
license: Upstream license applies
allowed-tools: Bash(python3:*)
---

# DiffDock NIM docking

Use for protein-ligand pose generation when a reachable DiffDock NIM endpoint and valid receptor/ligand files are available. This skill does not interpret a pose as a binding affinity or experimental validation. The wrapper checks inputs and endpoint configuration; it does not send a request unless explicitly extended with the endpoint contract.

## reference

Reference implementation: https://github.com/gcorso/DiffDock
NVIDIA BioNeMo skill format reference: https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit/tree/main/nim-skills/diffdock-nim

Record receptor path, ligand representation, endpoint URL, model/version, seed, and output pose files.

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
