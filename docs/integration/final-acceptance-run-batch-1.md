# Batch-1 执行结果（已批准的唯一一批）

提交 `55fceda`，input `validation/final-acceptance-review/input-batch-1.json`，运行目录 `E:\Users\27343\Docker\final-acceptance-20261026T165723Z\`。证据见 `validation/final-acceptance-run/batch-1/`。

## 结论

**未通过，且不是失败。** 正常创建停在**入口选择**：作者同时交付了 `SKILL.md` 内的 python 代码块和 `scripts/terminal_fragments.py`，按你定下的“明确 binding 优先、歧义拒绝”规则，程序拒绝自行选择，记 `entry_ambiguous`（`repair_lane=binding`、`blocker_kind=unresolved_input`），状态 `blocked`。

因此本批**没有** Docker 构建、没有业务验收、没有 accepted 条目、没有安装。门禁未触发（因为没走到规划阶段）。

## 调用账本（上限 8，用完 4）

| 阶段 | 状态 | 用时 |
| --- | --- | ---: |
| discovery | completed | 178.6 秒 |
| author | completed | 189.1 秒 |
| author（修复轮） | completed | 57.8 秒 |
| review | completed | 97.1 秒 |
| 运行时规划/关联 | 0 次 | — |

未触发任何超时或静默超限；`progress_watch=observe` 生效但本批没有静默超过 240 秒的调用。预算未耗尽，无自动续批。

## 固定条件的落地情况

`delivery.inputs.environment.payload.limits` 里持久记录了：`transport=https`、`reasoning_effort=medium`、`service_tier=default`、`progress_watch=observe`、`progress_timeout=240`、`model_timeout=600`、`total_seconds=3600`、单候选、单构建、`repair_rounds=1`。

## 策略核验（都成立）

- 默认查询：`{"skills": []}` —— 候选不出现在默认视图。
- 显式查询：候选可见，`current_execution.status=runtime_blocked`、`business_acceptance=not_run`。
- 安装候选：被拒 —— “Only integrated, frozen and qualified outputs may be installed; legacy approval is not inherited”。

## 过程事实（必须记录）

1. **第一次尝试直接失败**：`Codex CLI is not installed or is not on PATH`，0 次模型调用、0 次 Docker。原因是本机 PATH 不含 Codex 的 bin 目录（`codex_command()` 用 `shutil.which` 解析）。第二次把 `C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009` 加到 PATH 后正常。这属于环境问题，不是代码缺陷，但复现时必须写明。
2. **计划出的 4 条业务用例没有执行**：`documented-terminal-fragments`、`valid-empty-result`、`invalid-smiles`、`blank-input` 均为 `not_run`（deferred to bound Docker execution）。断言文本引自来源行号，不是从实际输出倒推。
3. **已计划的形态**：作者交付 3 个文件（`SKILL.md` 4656B、`scripts/terminal_fragments.py` 1368B、`references/upstream-notices.md` 3285B），内容审阅通过。

## 本批证明了什么

- 固定条件（HTTPS + medium/default）在 4 个阶段都完成调用，无传输错误；
- 账本按 4 条 receipt 记账、上限未被触及（因此未验证耗尽时的停止行为）；
- 歧义拒绝、默认查询隔离、候选安装拒绝三条策略在真实运行中生效；
- 计划用例的来源引用形态（行号 + 引文）符合“不从实际输出倒推”。

## 本批不能证明什么

- 该固定案例**没有**通过：无 Docker 构建、无业务验收、无 accepted、无安装；
- 与历史 600 秒超时根因无关，也没有性能结论，更不能作为“可合并”的依据；
- 当时 agent 阶段未持久化 argv，故“覆盖参数在 agent 路径生效”只能由代码路径与记录的环境载荷推断，不是直接证据（后续提交已补 `command.json` 逐阶段 argv/CLI 路径/有效超时/账本位置）；
- 账本上限未触及，因此本批不能证明“预算耗尽时的停止行为”；
- 观察到一个小缺陷：catalog 条目里 `unverified` 用例重复了两遍（后续已修）。

## 下一步（需要你的决定）

要推进这个固定案例，只有两条路，都要新批一次调用：

1. **显式指定入口**：把 `scripts/terminal_fragments.py` 作为 `spec.binding` 传入（脚本入口），Markdown 块则不被当作入口；
2. **或要求只保留一种入口**：让作者只交付 Markdown 块（当前交付里 SKILL.md 的块与脚本同时存在，是分歧来源）。

我没有自行选择，也没有重跑——按你“仅此一批”的授权到此为止。
