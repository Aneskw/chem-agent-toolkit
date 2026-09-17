---
name: chem-openbabel-convert
description: Convert chemical structure files between formats with Open Babel while preserving a machine-readable audit record.
license: GPL-2.0-or-later
allowed-tools: Bash(obabel:*)
---

# Open Babel format conversion

Use for deterministic conversion between supported molecular file formats (for example SDF, MOL2, PDB, XYZ, and SMILES). This skill does not validate a structure's experimental meaning or repair a chemically invalid file.

The packaged preflight wrapper calls the local `obabel` executable and returns JSON. It intentionally does not download software or silently change stereochemistry/aromaticity options; record any conversion flags.

## reference

Upstream: https://github.com/openbabel/openbabel

The command-line interface is `obabel`; input and output formats are selected with `-i` and `-o`. Conversion can change representation details, so retain the original file and inspect warnings.

## 输入&输出

输入、输出和错误语义以脚本的 JSON 记录为准。`ok: false` 时不得把部分结果当作成功；模型或数据库结果不等于实验验证。

## 使用步骤

1. 先读 `references/api.md`，确认接口、版本和输入约束。
2. 运行 `scripts/convert_molecule.py` 或上游 CLI，保存 stdout、stderr 和退出码。
3. 对照 `examples/` 检查字段；缺少依赖、权重或数据时标记为 `blocked_resources`。

## 失败与恢复

- 输入不完整或格式错误：修正输入并保留原始请求。
- 依赖、网络、权重或数据缺失：报告具体缺口，恢复环境后再运行，不伪造结果。
- 相同错误连续出现时停止重试并保留日志。
