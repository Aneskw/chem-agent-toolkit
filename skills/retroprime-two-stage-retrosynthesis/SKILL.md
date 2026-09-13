---
name: retroprime-two-stage-retrosynthesis
description: "当需要用 RetroPrime 从一个产物经两阶段预测生成反应物候选时使用。CPU 兼容包装器已通过两个真实样例和三个负例测试。"
license: "MIT (upstream code; weights subject to source terms)"
compatibility: "macOS arm64; Python 3.11; PyTorch 2.2.2; torchtext 0.3.1; CPU; two pinned checkpoints"
allowed-tools: Read, Bash, Write
---

# 使用 RetroPrime 进行两阶段单步逆合成

WHAT + WHEN：用 RetroPrime 对一个目标产物生成单步逆合成候选。

正例提示：用 RetroPrime 对一个目标产物生成单步逆合成候选。

反例提示：生成完整多步路线、训练模型或输出校准的成功概率。

## credibility

验证状态：inference_smoke_tested。两个真实 CPU 两阶段样例和三个负例已通过；尚未完成与 LocalRetro 相同 50 条样本的参考比对。当前为 Python 3.11 / PyTorch 2.2.2 的兼容适配运行，不是原 Python 3.6 环境复现。

乙酰苯胺返回 5 个有效去重候选，README 苯甲酸甲酯样例返回 10 个；非法 SMILES、top_k=0、单原子输入均明确拒绝。每个正例均实际经过两次模型推理和中间转换。结果见 reports/retroprime_smoke.json；这些不是预测准确率结论。

本次全新运行记录见 [2026-09-13 汇总](../../batch/runs/format-20260913/summary.json)。状态只覆盖声明的执行检查；未评测独立 agent 使用新版文档的效果。license 字段记录上游许可情况，不替代各组件许可。allowed-tools 是运行时可解释的工具声明，不授予额外权限。

## reference

论文：https://doi.org/10.1016/j.cej.2021.129845

仓库版本：`a765b670b72fbfd512d0d437da8f27a95f9f0554`。许可记录：代码仓库 MIT，许可保存在 evidence/RetroPrime/LICENSE。两份权重来自官方 README 的 Google Drive 压缩包，另记录资源来源、ZIP CRC 和 SHA-256。

- [run_example.sh L21–21](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh#L21-L21)：第一阶段模型路径
- [run_example.sh L22–22](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh#L22-L22)：第二阶段模型路径
- [run_example.sh L48–48](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/run_example.sh#L48-L48)：最终输出路径
- [retroprime/transformer_model/script/smi_tokenizer.py L14–14](https://github.com/wangxr0526/RetroPrime/blob/a765b670b72fbfd512d0d437da8f27a95f9f0554/retroprime/transformer_model/script/smi_tokenizer.py#L14-L14)：SMILES 词法分词子步骤

## 输入&输出

输入：一个含键的连通产物 SMILES，top_k 为 1–10。内部固定 beam size=10，使用官方 USPTO-50K 两阶段权重。

输出：JSON：规范化产物、有效去重的反应物候选、上游混合序列位置、两份权重哈希与各阶段耗时。上游没有在该最终接口提供校准概率，不补造概率。

## 使用步骤

1. 使用项目 requirements-retroprime-lock.txt 中的已测试依赖，或直接使用本机已准备好的启动器。原始权重实际名为 USPTO-50K_pos_pred_model.pt 和 USPTO-50K_S2R_model.pt，不能照搬 run_example.sh 中带 step 后缀的文件名。
2. 在 ChemSkillNet 根目录执行 ./run_retroprime.sh --product "CC(=O)Nc1ccccc1" --top-k 10；直接调用本技能 scripts/predict_retroprime.py 时提供 --source-root PATH_TO_RETROPRIME，并确保旧版 torchtext 0.3.1 可导入。
3. 脚本先校验源码和权重 SHA-256，在临时副本中修复旧版整数除法和改用串行预处理，然后按规范化、P2S、中间转换、S2R、合并顺序执行。原始来源快照不被改写。
4. 读取 stdout 的 JSON；任何阶段失败均返回 ok=false、退出码 2。若要保留所有中间文件，提供 --output-dir NEW_DIRECTORY（目录必须尚不存在）。

从 ChemSkillNet 根目录运行：

```bash
./run_retroprime.sh --product "CC(=O)Nc1ccccc1" --top-k 10 > retroprime-result.json 2> retroprime-run.log
```

## 失败与恢复

非法或不连通 SMILES、无键输入、top_k 越界：修正输入后重试。缺失资源或哈希不符：恢复匹配资源，不绕过校验。依赖或阶段失败：保留 stderr 并定位原因；同一错误重复出现则停止。--output-dir 已存在时使用新目录，不覆盖原结果。无有效候选不代表目标不可合成。CLI 参数解析错误可能仅有 stderr，应先检查退出码。
