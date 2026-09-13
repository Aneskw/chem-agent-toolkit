---
name: retroxpert-evaluate-bond-disconnection
description: >
  检查 RetroXpert EGAT 断键评估的资源条件，并在具备权重及数据后安排评估。当前资源阻塞，不可提供真实断键准确率。
license: MIT (upstream code)
allowed-tools: Read, Bash, Write
---

# RetroXpert 断键评估（资源阻塞）

WHAT + WHEN：目标操作为测试集上的 EGAT 断键预测评估；当前可执行范围仅为资源检查。

正例提示：检查是否具备 RetroXpert typed 断键评估的必要资源。

反例提示：为一个产物立即生成完整逆合成路线。该目标不属于此评估技能，当前也未具备推理条件。

## credibility

2026-09-13 重新检查为 blocked_resources：缺少 checkpoints/USPTO50K_typed_checkpoint.pt。没有执行推理，没有准确率结果。完整预处理数据与环境尚未验收。抽取为 codex_assisted_import，仅有仓库证据，未核读论文全文。

## reference

- [固定来源记录](../../evidence/RetroXpert/repo.json)：commit `321cc3daf2f3a7ac9ab5b37dde5b666b338e1ed5`，上游 MIT。
- [测试入口](../../evidence/RetroXpert/train.py)及[README](../../evidence/RetroXpert/readme.md)。README 信息泄漏说明需要在未来科学评测前核读。
- [本次阻塞结果](../../batch/runs/format-20260913/retroxpert-evaluate/result.json)。

## 输入&输出

目标输入为配套预处理 USPTO50K 数据、typed EGAT 权重及测试配置；目标输出为断键评估指标。当前预检只返回检查点路径和是否存在，不产生预测或指标。文件存在也不代表内容、依赖和科学评测条件合格。

## 使用步骤

从 ChemSkillNet 根目录执行最小阻塞检查：

```bash
python3 -c 'from pathlib import Path; import json,sys; p=Path("evidence/RetroXpert/checkpoints/USPTO50K_typed_checkpoint.pt"); ready=p.is_file(); print(json.dumps({"checkpoint":str(p),"present":ready,"scope":"checkpoint presence only"})); sys.exit(0 if ready else 2)'
```

完整历史来源与资源检查见上述批处理结果。若资源补齐，需要进一步检查数据、环境、权重对应关系，实现并验收 EGAT 适配器，才能执行模型评估；当前不提供未经验证的推理命令。

## 失败与恢复

检查点不存在时预检退出码 2，报告 blocked_resources 并停止。找到资源后固定来源、校验完整性并重新检查，不修改路径绕过缺失项，不用其他模型代替。持续缺资源时不要重试推理。allowed-tools 只声明可用工具，不授予额外权限。
