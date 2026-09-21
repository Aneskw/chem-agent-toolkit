# Graph2SMILES 操作契约前后对比

日期：2026-09-21

## 对照范围

- 文献：*Permutation Invariant Graph-to-Sequence Model for Template-Free Retrosynthesis and Reaction Prediction*（arXiv:2110.09681）。
- 模型：两次记录均使用 `gpt-6-astra`。
- 旧结果：`skills/generated/graph2smiles-20260920-r01/`。
- 新模型响应：`creation_pipeline/runs/graph2smiles-contract-v1-20260921-r03/responses/source-001-part001.json`。
- 完整重放结果：`creation_pipeline/runs/graph2smiles-contract-v1-20260921-r04/`。

这不是严格的科学 A/B 实验。两次运行存在模型采样差异，而且重新下载和解析后的来源 bundle 哈希与旧记录不同。因此结果只能说明新版流程在这个案例上的表现，不能把所有差异都归因于操作契约。

## 运行结果

新版模型提取产生两个 `method_procedure` 候选：

1. `graph-aware-positional-encoding`
2. `graph2smiles-decode-and-filter`

两者均通过：

- JSON 操作契约结构检查；
- 原文引用和行号检查（其中 2 处仅空白差异被安全修复）；
- method procedure 最低质量门槛；
- `SKILL.md` v0.3 格式检查。

## 结构化结果

| 新候选 | 使用条件 | 前置条件 | 步骤 | 决策点 | 验证检查 | 停止条件 | 未知项 | 已核对引用数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| graph-aware-positional-encoding | 2 | 1 | 3 | 1 | 1 | 0 | 3 | 17 |
| graph2smiles-decode-and-filter | 1 | 1 | 4 | 1 | 1 | 0 | 5 | 16 |

模型没有从来源中找到有充分证据的“不应调用条件”和“停止条件”，所以对应数组为空。它没有为满足格式而编造内容，这是符合契约预期的行为。

## 与旧结果相比

### 明显改善

1. **适用范围变成独立、带引用的字段。**旧版主要把操作名称放进 `Invoke for`；新版分别说明使用条件和前置条件。
2. **隐含判断被写成明确分支。**例如图距离编码现在明确询问两个原子是否属于不同分子，并分别给出 bucket 10 或按距离分桶的动作。
3. **验证动作与普通步骤分开。**例如明确检查 positional information 不应加入 value vectors，以及评估时须经 RDKit canonicalization 后精确匹配。
4. **未知信息更面向实际使用。**新版记录了无效输入、全部候选解析失败、解码终止设置等缺口，并指出 RDKit 可解析不等于反应在化学上可行。
5. **候选边界更集中。**旧版第二个候选同时混合 checkpoint 选择、beam search、过滤和评测；新版聚焦为 decode-and-filter 工作流，更容易被 agent 正确调用。

### 没有改善或有所取舍

1. 新版两个候选仍没有来源支持的 `do_not_invoke_when` 和 `stop_conditions`，所以操作边界仍不完整。
2. 新版第二个候选聚焦后，遗漏了旧版中 checkpoint 每 5,000 步保存、按 validation top-1 选择，以及 top-n 报告等内容。它更清晰，但覆盖范围更窄。
3. 新版第一个候选减少了旧版对完整 attention 结构的描述，重点转向 positional encoding。作为单一 Skill 更集中，但不能替代完整模型实现说明。
4. 本次因 Python 的 arXiv 证书验证问题改用本地 PDF 输入，因此新草稿的 Reference 显示本地规范化文本路径；这属于本次采集方式的显示问题，不是操作契约的提取问题。

## 结论

这个案例支持“操作契约提高了候选的可操作性和结构清晰度”：模型更明确地提取了调用条件、前置条件、分支、验证方式和未知项，而且没有为了填满字段而编造停止条件。

但它还不能证明 agent 使用后的任务成功率提高。新版也出现了“更聚焦但遗漏部分旧信息”的取舍。下一步适合增加一个轻量人工评分表，分别评价完整性、可执行性、边界清晰度、忠实性和粒度；之后再加入真正的 agent 增益测试。

## 本次端到端运行发现的问题

1. Windows 默认 GBK 会在读取 UTF-8 来源 JSON 时失败。
2. PDF 中的 `ﬁ` 等 Unicode 连字会在向 Codex CLI 写入提示词时触发 GBK 编码失败。
3. 运行环境需要同时提供 `pypdf` 和 `PyYAML`；README 以前只明确写了前者。

前两个编码问题已在代码中修复，README 也已补充依赖说明。
