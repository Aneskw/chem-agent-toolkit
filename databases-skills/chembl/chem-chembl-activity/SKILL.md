---
name: chem-chembl-activity
description: Query ChEMBL activity records for a molecule or target and return reproducible JSON without treating database annotations as experimental confirmation.
license: Apache-2.0
allowed-tools: Bash(python3:*)
---

# ChEMBL activity query

Use for retrieving public bioactivity annotations by ChEMBL molecule or target identifier. Keep the query URL, pagination limit, and returned activity IDs. Do not silently merge assays or interpret heterogeneous measurements as one comparable endpoint.

## reference

API: https://www.ebi.ac.uk/chembl/api/data/docs

The script uses the ChEMBL REST endpoint `/activity.json` with `molecule_chembl_id` or `target_chembl_id`. Results depend on the current public database and should be cached with retrieval time.

## 输入&输出

输入、输出和错误语义以脚本的 JSON 记录为准。`ok: false` 时不得把部分结果当作成功；模型或数据库结果不等于实验验证。

## 使用步骤

1. 先读 `references/api.md`，确认接口、版本和输入约束。
2. 运行 `scripts/query_activity.py` 或上游 CLI，保存 stdout、stderr 和退出码。
3. 对照 `examples/` 检查字段；缺少依赖、权重或数据时标记为 `blocked_resources`。

## 失败与恢复

- 输入不完整或格式错误：修正输入并保留原始请求。
- 依赖、网络、权重或数据缺失：报告具体缺口，恢复环境后再运行，不伪造结果。
- 相同错误连续出现时停止重试并保留日志。
