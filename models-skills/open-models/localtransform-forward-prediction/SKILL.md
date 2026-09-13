---
name: localtransform-forward-prediction
description: "用于检查 LocalTransform 正向预测工作是否具备打包条件；当前固定版本缺少关键文件，不可用于执行预测。"
license: "Unknown; upstream licensing requires clarification"
allowed-tools: Read, Bash, Write
---

# LocalTransform 正向预测候选技能（阻塞）

WHAT + WHEN：检查 LocalTransform 正向预测所需资源是否齐备。

正例提示：检查 LocalTransform 正向预测所需资源是否齐备。

反例提示：现在直接给出 LocalTransform 的真实产物预测；当前资源不足。

## credibility

验证状态：blocked_upstream_missing_files。当前仓库文件不足；未执行模型。正文方法仍需独立核读。

当前合格行为是明确报告阻塞。不能把 README 中的命令可阅读当作仓库可运行；不能改用另一模型而沿用本技能名称。

本次全新运行记录见 [2026-09-13 汇总](../../batch/runs/format-20260913/summary.json)。状态只覆盖声明的执行检查；未评测独立 agent 使用新版文档的效果。license 字段记录上游许可情况，不替代各组件许可。allowed-tools 是运行时可解释的工具声明，不授予额外权限。

## reference

论文：https://doi.org/10.1038/s42256-022-00526-z

仓库版本：`1b763f20e4d1df560d15aab2a61291fe0c50fae3`。许可记录：当前 GitHub 元数据 license 为 null，README 移除代码声明与旧许可标记不一致，待核实。

- [README.md L6–6](https://github.com/kaist-amsg/LocalTransform/blob/1b763f20e4d1df560d15aab2a61291fe0c50fae3/README.md#L6-L6)：上游变更声明

## 输入&输出

输入：拟使用的反应物 SMILES、模型权重及配套预处理资源。

输出：预期为产物候选；当前版本只能输出缺失资源报告，不能生成模型预测。

## 使用步骤

从 ChemSkillNet 根目录执行文件预检（缺资源时退出码 2）：

```bash
python3 skills/localtransform-forward-prediction/scripts/preflight.py evidence/LocalTransform
```

完整资源阻塞记录由项目 run_batch.command 的 localtransform-forward 任务生成。文件预检通过也不等于模型可运行；当前没有经过验收的推理适配器。

## 失败与恢复

缺少测试/解码脚本、权重或预处理数据时记为 blocked_resources，停止推理。取得完整资源后重新固定版本、核对许可、构造适配器并验收。不得用另一模型输出代替 LocalTransform 结果。预检 observed_commit 可能来自父 Git 仓库，不能替代 evidence/LocalTransform/repo.json 的快照来源记录。
