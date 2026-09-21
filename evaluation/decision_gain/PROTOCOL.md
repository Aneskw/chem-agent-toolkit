# 三臂化学决策 Skill 评测流程

这个流程回答两个不同问题：

1. 生成的 Skill 是否比不给资料的 agent 更容易作出正确化学工作流决策？
2. Skill 是否比直接提供同一批论文／代码原文更有效，而不只是增加了信息？

它不评价隐藏思维链，也不把模型答案当作实验产率、分子预测精度或湿实验验证。

## 三种条件

每道题使用同一模型、同一基础 prompt、同一选项顺序和独立临时目录。唯一差异是参考材料：

| 条件 | 提供内容 | 解释 |
| --- | --- | --- |
| `no-skill` | 题目，无额外资料 | 裸模型基线 |
| `source-text` | 题目 + 抽取时使用的完整 PDF 文本和固定 commit 代码文本 | 直接访问原始信息的基线 |
| `with-skill` | 题目 + 对应生成 Skill 的 `SKILL.md` | 检验压缩后的决策指导 |

`with-skill > no-skill` 只能说明 Skill 相对裸模型有帮助；只有
`with-skill > source-text` 才支持“抽象后的 Skill 比直接给来源更有决策价值”。

## 1. 独立、盲化并冻结任务

任务作者只看原始 PDF／固定 commit 代码，不看待测 Skill。最强的设计是在生成 Skill
之前完成出题；也可以先生成 Skill，再由与抽取流程隔离且无法看到 Skill 的独立评审者
出题。关键是不允许根据 Skill 的措辞或已知强项反向定制评测题。为每个来源族编写至少 12 道
三选一决策题；题目应要求选择可观察的下一步动作，而不是复述术语。覆盖：

- 正向适用题：条件满足时是否选择来源支持的方法；
- 错路辨别题：常见但有诱惑力的错误动作；
- 范围负例：条件不满足、证据不足或目标发生变化时应拒绝套用 Skill；
- 恢复／停止题：失败后何时停止、回退或请求额外证据。

`tasks.json` 中每题包含 `id`、`family`、`request`、三个互异的
`options`；范围负例另加 `"tags": ["scope-negative"]`。`oracle.json`
只保存题号到正确选项的映射。答案应由独立化学审核者确认；模型自产答案不能当金标准。

冻结模型、重复次数、随机种子、任务、答案、协议和判分器哈希：

```bash
python3 evaluation/decision_gain/run.py freeze \
  --tasks /path/to/tasks.json \
  --oracle /path/to/oracle.json \
  --protocol evaluation/decision_gain/PROTOCOL.md \
  --lock /path/to/preregistration.json \
  --model gpt-5.6-sol --repeats 1 --seed 193
```

冻结后不要修改题目、答案、门槛或判分器来挽救不利结果。任何修改都应创建新版本和新锁。
Skill 抽取进程不得读取任务、答案或后续作答。由 Skill 自动起草的题只能作为开发回归题，
不能作为该 Skill 自身有效性的正式证据。

## 2. 生成 Skill 并绑定材料

先运行 PDF／代码仓库到 Skill 的创建流程。评测材料清单按 `family` 对应题目：

```json
{
  "paper-a": {
    "bundle": "../../creation_pipeline/runs/paper-a/jobs/paper-a/bundle.json",
    "skills": "../../creation_pipeline/runs/paper-a/drafts-v03"
  }
}
```

路径相对于材料清单。每个 `bundle.json` 必须是生成这些 Skill 时实际使用的完整来源包；
`skills` 目录下每个一级子目录包含一个 `SKILL.md`。运行清单记录来源文本、Skill 文本
以及各文件哈希和字符数，便于发现材料变化与上下文量差异。

## 3. 先做不调用模型的计划检查

```bash
python3 evaluation/decision_gain/run.py plan \
  --tasks /path/to/tasks.json --oracle /path/to/oracle.json \
  --lock /path/to/preregistration.json \
  --materials /path/to/materials.json \
  --model gpt-5.6-sol --repeats 1 \
  --out /path/to/evaluation-plan
```

`plan` 校验冻结哈希、family 完整对应、来源包和 Skill 是否存在，随后确定性打乱选项与
三臂调度，写出 `manifest.json` 和每个 prompt 的哈希。它不会调用模型。本仓库的自动
测试使用临时合成来源和 Skill 验证到这一步，不构成任何真实 Skill 的效果结果。

## 4. 可选的正式运行

只有在需要真实效果数据时才执行：

```bash
python3 evaluation/decision_gain/run.py run \
  --tasks /path/to/tasks.json --oracle /path/to/oracle.json \
  --lock /path/to/preregistration.json \
  --materials /path/to/materials.json \
  --model gpt-5.6-sol --repeats 1 \
  --out /path/to/evaluation-results
```

每次调用在新的临时目录中运行，不允许工具调用，且只看到一题和该条件对应的材料。
无效响应、超时和工具事件记为失败尝试，不能静默删除。输出保留完整
`attempts.jsonl`、材料／prompt 哈希、token 数与 `summary.json`。

## 判分与结论

主指标是同题配对的选项准确率差。重复运行先在题内取平均，不能把重复次数伪装成新增
独立题。报告任务级 bootstrap 95% 区间以及基于胜负题的双侧精确符号检验。

默认效果门槛同时要求：

- 所有计划调用都有有效结果；
- 至少 12 道独立任务；
- 配对平均增益为正且 bootstrap 95% 下界大于 0；
- 双侧精确检验 `p < 0.05`；
- `with-skill` 在 `scope-negative` 题上不低于对照组。

分别对 `no-skill` 和 `source-text` 应用门槛。未通过时写“未证明优势”，不能写
“Skill 无效”；通过也只支持被测来源、题型和模型范围。token 或延迟降低不能抵消准确率
下降。查看结果后设计的新任务属于后续确认实验，必须另行冻结并保留原有负结果。
