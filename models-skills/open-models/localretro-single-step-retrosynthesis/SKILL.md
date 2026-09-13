---
name: localretro-single-step-retrosynthesis
description: "使用 LocalRetro 将单个目标产物 SMILES 转为带模型分数的单步逆合成反应物候选。适用于候选生成；不提供多步路线或实验条件。"
license: "CC-BY-NC-SA-4.0 (upstream README; see reference)"
allowed-tools: Read, Bash, Write
---

# 使用 LocalRetro 进行单步逆合成

WHAT + WHEN：用 LocalRetro 为乙酰苯胺生成单步反应物候选。

正例提示：用 LocalRetro 为乙酰苯胺生成单步反应物候选。

反例提示：预测反应产物、设计多步路线或给出实验成功概率。

## credibility

文档格式：ChemSkillNet v0.2。family：`single_step_retrosynthesis`；本包为 LocalRetro 的 tool implementation。用于生成候选反应物；不用于正向反应预测、完整合成路线或实验成功率判断。

验证状态：inference_smoke_tested。已在 macOS arm64 / Python 3.11 独立环境完成两个真实 CPU 预测和三个错误输入测试。尚未进行准确率基准评测，也未完成论文全文方法复核。

已测试：官方示例产物得到 10 个有效去重候选，乙酰苯胺得到 9 个；非法 SMILES、top_k=0、单原子输入明确拒绝。上游输入占位行被排除。运行记录见 reports/inference_smoke.json；这是可运行性测试，不是化学正确率或实验可行性验证。 另完成固定 50 条样本的参考比对，结果与边界见项目 evaluation/README.md；该诊断不等同于论文复现。

可查阅 [初次运行记录](../../reports/inference_smoke.json)、[历史五项目重跑报告](../../batch/runs/five-v2/REPORT.md) 和 [参考比对说明](../../evaluation/README.md)。2026-09-13 新一轮两输入真实 CPU 推理通过，分别返回 9 和 10 个候选；尚未验证新版文档能否提高独立 agent 的任务成功率。

本次全新运行记录见 [2026-09-13 汇总](../../batch/runs/format-20260913/summary.json)。状态只覆盖声明的执行检查；未评测独立 agent 使用新版文档的效果。license 字段记录上游许可情况，不替代各组件许可。allowed-tools 是运行时可解释的工具声明，不授予额外权限。

## reference

论文：https://doi.org/10.1021/jacsau.1c00246

仓库版本：`eba83e72efabeb854fec86c865e8743c295a8a1e`。许可记录：README 2026.01 标为 CC BY-NC-SA 4.0；使用和再分发遵守上游许可。

- [Retrosynthesis.py L63–63](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/Retrosynthesis.py#L63-L63)：单产物预测接口及其真实拼写
- [Retrosynthesis.py L74–74](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/Retrosynthesis.py#L74-L74)：结果初始化包含输入产物
- [Retrosynthesis.py L34–34](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/Retrosynthesis.py#L34-L34)：需要数据集模板文件
- [scripts/utils.py L120–120](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/scripts/utils.py#L120-L120)：上游加载模型状态字典
- [data/configs/default_config.json L8–8](https://github.com/kaist-amsg/LocalRetro/blob/eba83e72efabeb854fec86c865e8743c295a8a1e/data/configs/default_config.json#L8-L8)：使用与权重配套的 GELU 配置

## 输入&输出

输入：一个含化学键的连通产物 SMILES、top_k（1–100）；使用固定 USPTO_50K 权重和配套模板。

`--product` 必填，`--top-k` 默认 10。包装器会去除原子映射编号并规范化 SMILES；需要保留映射对应关系的任务不能直接使用这个输出。top_k 控制上游编辑候选请求数，不保证最终返回相同数量的反应物候选。

输出：JSON：规范化产物、非占位且去重的反应物候选、模型分数、局部模板、权重 SHA-256 和耗时；候选数可能小于 top_k。

先检查退出码，再读取 JSON。成功时 `candidate_count` 应与 `candidates` 长度一致且非零。每个候选包含 `rank`、`reactants_smiles`、`model_score`、`local_template`；同时返回规范化的 `product_smiles`、`commit`、`model_sha256`、`device` 和 `elapsed_seconds`。

包装器会剔除不能解析、与产物相同、重复或分数非有限值的候选。报告候选数量、排序、模型版本和输出文件位置；这些候选仍需后续化学评价。分数没有经过实验成功概率校准，也不能直接与其他模型分数比较。SMILES 可解析不代表反应可行。

## 使用步骤

执行方式：本地 CPU CLI。以下操作依赖完整 ChemSkillNet 项目、证据仓库和模型资源；只下载本 SKILL.md 不足以运行。运行前检查 [资源清单](scripts/inference_manifest.json) 和项目 [依赖锁定文件](../../requirements-localretro-lock.txt)。

1. 在包含 PyTorch 2.2.2、DGL 1.1.3、DGLLife 0.3.2 等依赖的独立环境运行；项目 requirements-localretro-lock.txt 保存完整已测试版本。
2. 从本项目根目录执行 ./run_localretro.sh --product "CC(=O)Nc1ccccc1" --top-k 10。该启动器使用本机已配置的独立环境；迁移环境可设置 CHEMSKILLNET_PYTHON。
3. 也可直接运行本技能 scripts/predict_localretro.py --source-root PATH_TO_LOCALRETRO --product "CC(=O)Nc1ccccc1" --top-k 10。脚本按随包清单核对源码、模板和权重 SHA-256，再以 CPU 加载模型。
4. 读取 stdout 的 JSON：ok=true 时使用 candidates；ok=false 或退出码 2 时报告错误。详细依赖和上游输出写入 stderr。不要把模型分数解释为实验成功概率。

从 ChemSkillNet 根目录运行并保留输出：

```bash
./run_localretro.sh --product "CC(=O)Nc1ccccc1" --top-k 10 > localretro-result.json 2> localretro-run.log
```

## 失败与恢复

| 观察到的错误 | 处理 |
| --- | --- |
| 非法 SMILES、不连通产物、无化学键或 top_k 越界 | 修正对应输入；保留原始输入，不静默改变目标化合物 |
| Missing pinned resource / Resource hash mismatch | 按资源清单恢复匹配文件；资源未恢复前记为 blocked_resources，不跳过哈希检查 |
| 依赖导入或模型加载失败 | 对照锁定依赖、Python 环境和配套配置定位；无法确认原因时停止并保留日志 |
| Model produced no valid non-placeholder candidates | 报告此次未得到有效候选；不解释成目标不可合成 |

仅在原因已定位且输入或环境确实改变后重试，记录变更与新结果；相同错误再次出现时停止自动重试。CLI 参数解析错误可能只有 stderr，没有 JSON，不能假定所有失败都有结构化输出。
