---
name: wln-build-molecular-graph
description: >
  将 SMILES 转为 WLN 原子/键特征和邻接数组。用于 WLN 图预处理、检查图表示；不运行完整反应预测模型。
license: MIT (upstream code)
allowed-tools: Read, Bash, Write
---

# WLN 分子图构建

WHAT + WHEN：从分子 SMILES 构造 WLN 特定表示，供下游模型使用。family 为分子图特征构造。

正例提示：把乙醇 CCO 转为 WLN 图特征并检查邻接数组。

反例提示：用完整 WLN 模型预测反应产物。此包只有预处理能力。

## credibility

2026-09-13 全新批处理：原始 Python 2 模块首次失败；应用已有 print/map/xrange 兼容规则后，乙醇、苯、批处理 mask、非法输入和打包 CLI 共五项检查通过。没有模型权重推理或准确率评测。抽取仍为 codex_assisted_import。

脚本使用本次修订后的工作副本，原始证据源码未改。allowed-tools 仅为工具声明，不扩大执行权限。

## reference

- [固定来源记录](../../evidence/WLN/repo.json)：commit `fb7dea369b0721b88cd0133a7d66348d244f65d3`，上游 MIT。
- [源码](../../evidence/WLN/USPTO-15K/core-wln-global/mol_graph.py)：smiles2graph、smiles2graph_list。
- [本次验收](../../batch/runs/format-20260913/wln-graph/attempt-1/revision-1/acceptance.json)和[修订差异](../../batch/runs/format-20260913/wln-graph/attempt-1/revision-1/repair.diff)。

## 输入&输出

CLI 必填 `--smiles`：单个 SMILES。输出 JSON 的 `ok`、`input_smiles`、`output`；output 含 atom_features、bond_features、atom_neighbors、bond_neighbors、neighbor_counts 数组。批处理接口 smiles2graph_list 另提供填充和 mask，但当前 CLI 仅接收一个分子。

图特征遵循该 WLN 实现，不能假定可直接输入其他模型；生成图不证明任何反应可行。

## 使用步骤

从 ChemSkillNet 根目录使用已有 Python 环境：

```bash
../../work/localretro/venv/bin/python batch/runs/format-20260913/wln-graph/attempt-1/revision-1/package/run.py --smiles CCO > wln-result.json
```

迁移机器时以具有 RDKit 和 NumPy 的 Python 3.11 替换解释器路径。此技能依赖项目中链接的已修订包，不能只复制 SKILL.md。检查退出码 0、ok=true，核对数组维度和邻接关系后交给下游。

## 失败与恢复

非法 SMILES：退出码 2、ok=false，返回 error.type 和 error.message，修正输入再运行。依赖缺失：恢复 RDKit/NumPy 环境。若运行原始源码遇到 Python 2 SyntaxError，使用上述已修订副本；不改来源文件。对未覆盖分子发生异常时记录输入并停止，不能静默丢弃分子。相同错误重复出现时停止自动重试。
