# 任务二执行矩阵（修订版，待最终开跑批准）

本次**不运行**。以下为单一案例正常 build 的完整条件、台账规则与产物清单；经批准后按此执行。

基线：`integration/planner-timeout`；本轮修复与选项提交见文末。全量回归 **309 项、3 跳过、全绿**（本文件定稿前实测）。

## 1. 实际 input.json（将使用这一份，不临场改）

文件：`validation/final-acceptance-review/input-batch-1.json`，`build --preflight` 已通过（`configuration_valid`，0 次模型调用）。要点与固定值：

| 字段 | 值 | 说明 |
| --- | --- | --- |
| `sources[recap]` | `raw.githubusercontent.com/rdkit/rdkit/237a1d9027c8…/rdkit/Chem/Recap.py`，`sha256 d4f9b969…c3fc` | 上游版本固定到 commit |
| `sources[license]` | 同 commit `license.txt`，`sha256 daeb8d19…fca30` | BSD-3-Clause |
| `model.name` | `gpt-6-astra` | 与历史一致 |
| `model.transport` | `https` | **所有模型阶段统一**：发现/编写/审阅（`backend.stage`）、入口关联（`entry.associate`）、关联后的独立审阅（`review_snapshot`）、环境规划与契约诊断都收同一组覆盖参数 |
| `model.reasoning_effort` | `medium` | 同上，全阶段统一，不再继承用户全局 `low` |
| `model.service_tier` | `default` | 同上，全阶段统一，不再继承用户全局 `priority` |
| `execution.profile` | `production` | 不新增隐含配额 |
| `execution.stop_on_runtime_failure` | **`true`** | 首次 Docker 构建/业务验收失败即停：不进入契约修正、不做第二次构建 |
| `execution.progress_watch` | **`observe`** | 经正常 build 传进 planner/关联（`runtime.options.progress_watch`）；agent 侧固定 240 秒观测窗口 |
| `limits.model_calls` | **8** | 整批宿主模型调用总账上限 |
| `limits.model_timeout` | **600** | 单次硬上限 |
| `limits.total_seconds` | **3600** | **整批总时限**（60 分钟），到点不再发起新调用 |
| `limits.agent_progress_timeout` | `null` | agent 阶段只观测（240 秒窗口），不终止 |
| `limits.max_candidates` / `max_builds` | `1` / `1` | **最多一个候选、一次构建** |
| `limits.repair_rounds` | `1` | 修复轮上限，不自动续批 |
| `batch.label` | `acceptance-batch-1-normal-create` | 便于在 catalog 与日志里定位 |

### 参数传递路径（已用真实入口测试覆盖）

| 阶段 | 传递路径 | 测试 |
| --- | --- | --- |
| 发现 / 编写 / 审阅 | `config.model` → `backend.NativeSession.stage` → `model_args()` | `test_native`、`test_batch_conditions` |
| 入口关联 | `runtime.options` → `entry.associate` → `model_call.call(transport=…, reasoning=…, tier=…, progress_watch=…)` | `AssociationPropagationTests`（真实 `associate` 调用） |
| 关联后的独立审阅 | 同上 → `review_snapshot` 写入自己的子进程配置 | `ReviewTurnConfigTests`（真实 `review_snapshot`，检查它写出的 config） |
| 环境规划 / 契约诊断 | `runtime.options` → `planner.options` → `model_call.call` | `NormalBuildPlannerSettingsTests`（真实 build 配置 → `planner.plan`） |
| 契约修正审阅 | `spec.options` → `review_snapshot` | `test_markdown_entry` / `test_runtime_build`（修正路径本轮不触发） |

`prompt` 与历史 `markdown-entry/input.json` 完全一致（RECAP 终端分子片段，`RecapDecompose`/`GetLeaves`，终端 vs 完整层级、合法空结果、非法输入边界，禁止宿主执行）。**历史 SKILL.md 不作为输入。**

## 2. 台账：一个总账，8 次封顶

已核对实现（`pipeline.py:431-439`）：运行时规划/关联/修复的调用前守卫读取**同一个** `config["limits"]["model_calls"]`，并在调用前把一条 `phase="runtime_planning"` 的 receipt 追加进 `session.receipts`；agent 阶段（发现/编写/审阅）的每次 `stage()` 也各追加一条。因此：

| 计入同一总账 | 机制 |
| --- | --- |
| 独立审阅（review 阶段） | `NativeSession.stage` → 一条 receipt |
| 修复轮（作者/审阅重跑） | 同上，`repair_rounds` 另有限制 |
| 运行时规划、入口关联、契约修复 | `runtime_call_guard` 在调用**前**记账，失败也计数 |
| **失败的尝试** | 守卫先记账再调用，因此超时/失败同样消耗额度 |
| 发现阶段 | 一条 receipt |

台账耗尽 → 守卫抛 `RuntimeBlocked("explicit_budget")`，本轮结束并报 `partial`。**不自动续批**：`extra_turns`/`budget_extension` 只有显式调用才会增加，本批不调用。

## 3. 时间上限

| 层级 | 上限 | 执行方式 |
| --- | --- | --- |
| 单次模型调用 | **600 秒**（硬） | `limits.model_timeout=600` → `model_call.run(timeout=…)`；agent 轮次同样取 `min(剩余, model_timeout)` |
| 进度检测 | **240 秒，仅观测** | 本批 `progress_watch="observe"`（planner/关联）与 agent 侧 `PROGRESS_OBSERVE_SECONDS=240`：超过 240 秒静默只在 `process.json` / receipt `progress_observation` 记 `progress_limit_exceeded` 与实测静默秒数，**不终止** |
| **整批总时限** | **3600 秒（60 分钟）** | `limits.total_seconds=3600` → `executor.deadline` 与 planner `deadline`；`runtime_call_guard` 在每次运行时调用前检查，到点即 `explicit_budget` |
| Docker 构建+验收 | `build_seconds`/`test_seconds` 既有默认（600/60 秒每步） | 超时即 `build_failed`/`execution_failed`，不重试加时 |

### 失败门禁（本批生效）

`execution.stop_on_runtime_failure=true`，实现为 `pipeline.runtime_gate_stops`：`runtime_receipt.status` 为 `build_failed` 或 `execution_failed` 时立即 `break`，写 `entity_record.runtime_failure_gate`（含真实状态与原因）与 `stopped_reason`，**不调用 `automatic_correction`、不做第二次构建**。作者阶段的 `repair_rounds` 不受影响。

已知风险：本批把 agent 阶段也钉到 `https`。若自定义 provider 在 `--ignore-user-config` 的 agent 路径上表现不同（例如鉴权解析差异），失败会发生在发现阶段并以传输类错误呈现；届时按 §6 停批报告，改用 `default` 需要新批准，不在本批内自行切换。

**HTTPS 鉴权是本批的受控验证项**：`planner_https` 只复用 `requires_openai_auth=true` 与内建 provider 相同的 endpoint 解析，历史上只在规划路径用过一次（`call-20261026T150937Z-https` 成功）。本批把它推到全部阶段，属于**有意验证**；不做自动回退、不做运行时降级，失败即停批并如实报告。

## 4. 本批只做五件事（其余另批）

1. 正常创建：来源准备 → 发现 → 编写 → 独立审阅 → 入口关联 → 环境规划（`transport=https`）。
2. 一次 `docker build`（Linux amd64、CPU、公开依赖），记录镜像 Id/RepoDigests、基础镜像引用与依赖版本。
3. 完整业务验收：计划锁定的全部用例（预计 6–11 条）逐条 `docker run`，覆盖 `RecapDecompose`/`GetLeaves`、终端 vs 层级、合法空结果、声明范围内非法输入、真实交付入口与支持文件。
4. `library` 默认查询（确认只返回合格项；若 accepted 存在则继续第 5 步）。
5. `install` 到新的隔离路径并核对内容；不核验异路径运行资格。

**明确不在本批**：跨路径迁移（`runtime-relocate`）、删除/篡改镜像标签的破坏性场景、任何恢复路径、任何手工补料。这些按你要求另批申请。

## 5. 固定并记录的条件

| 条件 | 固定方式 | 记录位置 |
| --- | --- | --- |
| 模型 | `model.name=gpt-6-astra` | `request.json`、receipt `model` |
| 传输 | `model.transport=https`（子进程 `-c model_provider=planner_https` 等 9 个覆盖） | `request.json.command` 与新增 `transport` 字段 |
| reasoning / service tier | **不改**用户全局配置；实际生效值随 `inherited_model_settings` 记录（当前 `low` / `priority`） | `request.json.inherited_model_settings` |
| 代理 | 不设代理环境变量；依赖本机透明路由。开跑前记录 `codex doctor` 的 `network.env`（`respect system proxy`=disabled）与两项可达性 | 预检日志 |
| CLI | 二进制 SHA-256 `1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`、版本 `0.164.0-alpha.11.1` | 预检日志 |
| Docker | 引擎版本、平台、基础镜像引用 | attempt receipt |

## 6. 中止与再申请

- 300 秒/600 秒超时或静默超限：保留 `stall.json`（若有）、`process.json`（含 `process_counters` 时间线与 `progress_observed_silence_seconds`）、投影后的 stderr、`model_metrics.receipts`；停止本批，报告后等新批准。
- 台账耗尽（`explicit_budget`）：如实报 `partial`，不续批。
- 计划语义被拒（如 `Outcome assertion role must match…`）：属模型产出问题，不是传输问题；计入台账，按 `repair_rounds=1` 允许一轮修复，再失败即停。
- 网络不可达（`model_unavailable`/`model_transport`）：先查 `codex doctor`，网络问题不计入代码结论，也不消耗“成功”判定。

## 7. 开跑前必须全绿

`python -m unittest discover -s tests -t .`（当前 **317 项、3 跳过**，本文件编写前通过）与 `python -m creation_pipeline build validation/final-acceptance-review/input-batch-1.json --preflight`（已通过）。

## 8. 产出与证据位置

`validation/final-acceptance-run/batch-1/`：预检日志、`summary.json`、`model_metrics`、attempt receipt、`locked-tests.json`、业务验收逐例输出、`library` 查询与安装日志、镜像身份。目录在仓库内，运行 state/library 在仓库外 `E:\Users\27343\Docker\final-acceptance-<UTCts>\`。
