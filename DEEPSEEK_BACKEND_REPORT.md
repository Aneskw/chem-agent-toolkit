# DeepSeek 结构化模型后端迁移报告

副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
分支：`integration/deepseek-api-backend`（独立 Git 历史）
报告时间：2026-10-27

---

## 0. 结论速览

| 项目 | 结果 |
| --- | --- |
| 隔离 | 副本独立 Git 历史；源目录 `78003de` 提交、`git status` 干净，全程未被修改 |
| 迁移范围 | **3 个结构化调用点**：入口关联、运行时规划（含 plan patch）、契约诊断 |
| 未迁移 | 发现、编写、独立审阅（`NativeSession` / Codex CLI）——按要求未重写 Agent 框架 |
| 后端选择 | 显式 `runtime.<candidate>.options.backend=deepseek_api`，默认 `codex_cli`，**无自动回退** |
| 契约 | 保持 `model_call.call(...) -> (answer, receipt)`；Codex 路径逐字节未改 |
| 结构化输出 | DeepSeek 只有 `response_format=json_object`（无 caller JSON Schema），故**强制本地 jsonschema 校验** |
| 硬期限 | DNS/连接/TLS/发送/等响应头/流读取/重试**各自按剩余预算重新计算**，共用一个总期限 |
| 离线测试 | 新增 **54** 个后端用例全通过；完整回归 **386 个测试 OK，3 个跳过**（仅 POSIX 用例） |
| 在线验证 | **真实请求 1 次**（原案例回放）：HTTP 200、158.5 s、request id `c6842ac2…`，返回 schema 合法的完整计划，但**未通过未改动的验收夹具门禁**（1 个负向用例用了不支持的字段）。 |
| 准确状态 | **适配器在线可用**（传输、完成标记、本地 schema 均通过），但**计划语义未通过**，因此唯一一批未启动。 |
| 第二阶段完整验收 | **未启动**。前批门禁未通过即停止（见 §7），0 次构建、0 条业务用例、0 次查询/安装。 |

提交历史（本副本）：

```
58917da  baseline: import of chem-agent-toolkit-integration at 78003de
43a69ce  feat(model-call): opt-in DeepSeek API backend for structured ...
8d6bc7b  docs: migration report, frozen-prompt check output and blocked-run evidence
d61362f  fix(model-call): harden the total deadline; restore the explicit binding;
         add the saved original-case replay
```

---

## 1. 隔离与记录

### 1.1 源目录状态（只读检查）

```
路径      E:\Users\27343\Docker\chem-agent-toolkit-integration
提交      78003de47c8bee93c705cd3a2098ee1f90646aae
分支      integration/planner-timeout
标题      P2: one fixed planner request timed out silently and emits no request id
未提交改动 无（git status --porcelain 为空）
```

仓库内没有 `AGENTS.md`（`E:\Users\27343\Docker` 子树内 glob 无结果），没有额外的项目级代理约定。

### 1.2 复制范围

已复制：`creation_pipeline/`、`tests/`、`docs/`、`examples/`、`skills/`、`evaluation/`、`README.md`、`LICENSE`、`.gitattributes`、`.gitignore`。

已排除：`.git/`（改为独立历史）、`.pipeline/`（13.1 MB 运行状态）、`__pycache__/`、`*.pyc`、`.pytest_cache/`、`.venv*/`、`evaluation/**/{cache,runs,results}/`。

`validation/` 原始 64.7 MB 历史运行产物，只保留：

* **既有回归必需的夹具**（约 0.9 MB）：`final-acceptance-review/input-batch-1.json`、`planner-frame-gate/source-excerpts.json`、`final-acceptance-run/batch-2/agent-turn-001-events.jsonl`、`planner-schema-isolation/before/*`、`stage3/rdkit-library/**`（87 文件），以及三个导入用辅助模块。
* **原案例回放材料**（约 250 KB，见 §5.2）：保存的 45 KB 原始 planner 请求及其 handoff/binding/锁定用例。

### 1.3 凭据处理

* `E:\Users\27343\Docker\.env` **不存在**（工作区深度 3 内也无任何 `.env*`），也无法从 `~/.codex/.env` 取得（该文件只有代理设置）。
* 副本新增 `.env.example`（仅变量名与说明）与 `.gitignore` 规则（`.env`、`.env.*`、`!.env.example`、`validation/**/runs/`、`validation/**/real/`）。已验证 `git check-ignore -v .env` 命中。
* 凭据只从进程环境或 `.env` 读取；写盘前用解析出的密钥值 + 现有 `redact()` 双重脱敏。离线测试用假值验证“磁盘上任何文件都不含该值”。

---

## 2. 实际切换范围

结构化接口 `model_call.call(prompt, schema, model, ...)` 只有三个生产调用点。

| 阶段 | 代码路径 | 改前 | 改后 | 迁移 |
| --- | --- | --- | --- | --- |
| 发现 / 编写（`NativeSession.stage`） | `agent/backend.py` | Codex CLI | Codex CLI | 否 |
| 独立审阅快照（`review_snapshot`） | `runtime/review.py` | Codex CLI | Codex CLI | 否 |
| 入口关联（`entry.associate`） | `runtime/entry.py` | Codex CLI | **DeepSeek API** | 是 |
| 运行时规划 / plan patch（`planner.plan`） | `runtime/planner.py` | Codex CLI | **DeepSeek API** | 是 |
| 契约诊断（`diagnosis.diagnose`） | `runtime/diagnosis.py` | Codex CLI | **DeepSeek API** | 是 |

`model.backend` 仍必须是 `codex_cli`（原生阶段需要）；选择结构化后端的位置是 `runtime.<candidate>.options.backend`。这不是“全部模型阶段迁移”。

`api_model` 与 `model` 是**两个提供方的两个身份**：Codex 模型名（如 `gpt-6-astra`）绝不会发给 DeepSeek，离线测试对此有断言。

---

## 3. DeepSeek 官方接口事实（2026-10-27 读取 api-docs.deepseek.com）

| 项 | 值 |
| --- | --- |
| OpenAI 兼容 base URL | `https://api.deepseek.com` |
| Anthropic 兼容 base URL | `https://api.deepseek.com/anthropic` |
| 端点 | `POST /chat/completions`，`Authorization: Bearer <key>` |
| 模型标识 | 文档为 `deepseek-flash`、`deepseek-v4-pro`（`deepseek-v4-flash` 为旧别名） |
| 结构化输出 | 仅 `response_format: {"type":"json_object"}`，**无 caller JSON Schema**；文档明确可能返回空内容、`length` 会截断 |
| 流 | SSE，终止符 `data: [DONE]`；usage 在最后一个 chunk（无新增内容、带非空 `finish_reason`） |
| 完成标记 | `finish_reason ∈ {stop, length, content_filter, tool_calls, insufficient_system_resource, aborted}`，仅 `stop` 算完成 |
| 心跳 | 流式 `: keep-alive`；非流式空行；10 分钟未开始推理由服务端断开 |
| 错误码 | 400/422、401、402、429、500/503 |
| 思考与 effort | 默认开启、默认 high；`reasoning_effort` 接受 `none/low/high/max`，`minimal→low`、`medium/xhigh→high` |

不猜测：endpoint 默认官方主机；模型名必须来自 `api_model`/`DEEPSEEK_MODEL`，缺失即拒且不发请求；非官方主机除非显式声明 `DEEPSEEK_ALLOW_CUSTOM_ENDPOINT` 否则拒绝并记为 `endpoint.kind=custom`。

---

## 4. 实现要点

### 4.1 契约与本地 schema 校验

`json.loads` → 必须是 JSON object → `jsonschema.validate(answer, schema)`。不满足即 `model_schema_mismatch`，绝不交给上层当计划。上层原有语义门禁（`planner.validate_plan`、`preparation.validate`、`entry.associate` 的引用校验）全部保留。

### 4.2 成功判据与失败分类

成功需**同时**满足：HTTP 200 + `finish_reason=stop` + `data: [DONE]` + 非空 content + JSON 解析成功 + 本地 schema 通过。心跳/`: keep-alive`/重连提示只记为存活。

| 现象 | 错误码 |
| --- | --- |
| `finish_reason=length` | `model_output_truncated` |
| 缺 `[DONE]`/缺 `finish_reason`/帧损坏/连接中断/`insufficient_system_resource`/`aborted`/流内错误 | `model_stream_interrupted` |
| 空 content | `model_output_empty` |
| 非 JSON / 非 object / schema 不符 | `model_output_invalid` / `model_schema_mismatch` |
| tool_calls | `model_output_invalid` |
| 401 / 402 / 429 / 5xx | `model_auth_failed` / `model_insufficient_balance` / `model_rate_limited` / `model_server_error` |
| 连接失败 | `model_connection_failed` |
| 总期限到期 | `model_timeout` |

验证脚本据此给出**互不混淆**的结论：`blocked_config_invalid`、`blocked_model_unavailable`、`blocked_model_output_invalid`、`plan_rejected`、`no_plan_in_one_call`、`plan_accepted`。

### 4.3 总期限（本轮修正项）

`timeout` 是一个应用层总期限，**每个阻塞阶段都按剩余预算重新计算**，不再沿用连接时设定的旧超时：

| 阶段 | 约束 |
| --- | --- |
| DNS 解析 | 放进守护线程，用剩余预算 `join`；超时即 `model_timeout`（`detail.phase=dns`），不静默超期 |
| TCP 连接 | 用剩余预算设定 socket 超时，逐地址重算 |
| TLS 握手 | TCP 连接成功后立刻用剩余预算重新设定 |
| 发送（请求行/头/体） | 发送前重新设定 |
| 等待响应头 | `getresponse()` 前重新设定，不继承连接时的值 |
| 流/正文读取 | 5 秒切片，每次读前复核墙钟期限 |
| 重试间隔 | 截断到剩余预算 |

因预算耗尽而触发的 socket 超时被判定为 `model_timeout`（不是 `model_connection_failed`）。到期或取消时先关闭 response 与 socket 再抛出。不使用 SDK（直接 `http.client`），不存在隐式重试；显式重试（`api_retries` 0–3）计入账本且共用同一期限。

### 4.4 账本、回执与脱敏

审计目录写 `request.json`/`attempts.json`/`stream.json`/`response.json`（或 `error.json`）/`schema.json`：endpoint、模型、实际发送参数、prompt/schema/messages 指纹、逐次尝试（状态、HTTP 码、耗时、错误分类、request id）。回执在原有字段外增加 `backend`、`provider`、`request_params`、`mapping`、`request_id`、`request_count`、`requests`、`completion`。prompt 正文不重复落盘，凭据从不落盘。

预算守卫未改动：`planner`/`pipeline` 的 `call_guard` 仍在请求前执行并计数；离线测试证明守卫抛错时**一次 HTTP 请求都不会发出**。

### 4.5 参数映射（不伪称等价）

| Codex 侧 | 实际发给 DeepSeek | 记录 |
| --- | --- | --- |
| `reasoning_effort=medium` | `thinking:{type:enabled}` + `reasoning_effort:high` | requested `medium` / sent `high`，注明“兼容映射，非等价” |
| `reasoning_effort=none` | `thinking:{type:disabled}` | requested/sent 均为 `none` |
| `service_tier=default` | 不发送 | “本后端不支持，仅记录不发送” |
| 240 秒 stall watchdog | 不套用 | 心跳不是生成进度；总期限是唯一界限 |

---

## 5. 验证

### 5.1 离线（全部通过，不触真实服务）

`tests/pipeline/test_deepseek_backend.py`，**54 个用例**，进程内 loopback 脚本化服务。覆盖：正常完成（流式/非流式）、schema 不符（缺字段/类型/数组/非 JSON/空）、不完整输出（`length`、缺 `[DONE]`、缺 `finish_reason`、帧损坏、流内错误、连接中断、`insufficient_system_resource`、tool_calls）、401/402/429/5xx、连接失败、**总期限（静默流、不发响应头、DNS 卡住）**、取消并释放连接、重试共用同一期限、预算守卫 0 请求、脱敏、配置拒绝与无回退。

回归：`python -m unittest discover -s tests -q` → **Ran 386 tests, OK (skipped=3)**。既有 332 个测试的断言未改。

### 5.2 两套 planner 验证，必须区分

| 脚本 | prompt | 能证明 | 不能证明 |
| --- | --- | --- | --- |
| `verify_planner.py` | 8,568 B 合成夹具（无第三方依赖） | 适配器连通、传输与契约、冻结件可复现 | 原慢案例是否改善 |
| `verify_original_case.py` | 保存的 **45,397 B** RDKit RECAP 原始规划请求 + 151,668 B `PLAN_SCHEMA` | 真实困难请求，且用未改动的门禁判定 | 端到端业务验收 |

`verify_original_case.py check`（完全离线）证明原案例完整可用：

* prompt 指纹 `2327f993b744fb8c8b37d157d47a4ed998545c6f83e39c6b8d2261211795b521`（45,397 字节）与原请求记录一致；
* schema 指纹 `67e030bfdf6c8a9690a7b3d3926917834e43e41e602e3b68780d8f20f6147671` 一致；
* 由 handoff 目录**重建的 inventory 与保存的 inventory 相同**（证明材料树就是当初那份）；
* 显式 markdown-python binding 与交付包一致（提取区间 + code 哈希）；
* **该案例历史上被接受的 plan 仍能通过未改动的 `preparation.validate`（8 条用例）**——所以回放结果与历史判定可比。

### 5.3 在线：先 0 请求（缺凭据），后执行 1 次（凭据补齐）

凭据缺失期间两次验证均为：

```
status       blocked_config_invalid
error_class  model_config_invalid
reason       DEEPSEEK_API_KEY is not configured (...); no request was sent
request_count 0
```

记录：`validation/deepseek-api/result.json`、`validation/deepseek-api/evidence/blocked-config-invalid/`。

`.env` 补齐（`DEEPSEEK_API_KEY` + `DEEPSEEK_MODEL=deepseek-flash`）后，执行了**唯一一次**原案例回放：

```
endpoint   https://api.deepseek.com/chat/completions (official)
model      deepseek-flash
params     stream=true, response_format=json_object, max_tokens=65536,
           thinking=enabled, reasoning_effort=high (requested medium)
requests   1（无重试），HTTP 200，158.5 s
request_id c6842ac2-7d62-4b7d-a67d-152463ca0179
```

**通过**：传输、`data: [DONE]` + `finish_reason=stop` 完成判据、以及针对保存的 151,668 B
`PLAN_SCHEMA` 的本地 schema 校验——模型返回了完整计划（`python:3.11-slim`、`linux/amd64`、
`script=entry/skill.py`、依赖 `rdkit`、2 个构建步骤、7 条用例、`resource_assessment=unknown`、
`acceptance_json` 八个键齐全）。

**未通过**：未改动的验收夹具门禁在负向用例 `behavior-reject-empty-smiles` 上拒绝

1. `Unknown fixture fields: stderr_contains`（`check_case` 不支持该字段）；
2. 仅删除该字段后：`Behavior test requires assertions or explicit test runner`（该用例因此没有断言）。

这是模型的计划语义缺陷，不是适配器或传输问题。证据：
`validation/deepseek-api/evidence/original-case-live/`。
该请求独立记账，**不计入**后续批次的 8 次预算；批次本身 0 次调用。

### 5.4 第二阶段完整验收：前批门禁未通过，未启动

见 §7 与 `validation/deepseek-api/launch-check.json`。**未启动批次，0 次 Docker 构建，0 条业务用例，0 次查询/安装。**

---

## 6. 复现方式

```sh
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi

# 1) 全量离线回归（386 个用例）
python -m unittest discover -s tests -q

# 2) 后端用例
python -m unittest tests.pipeline.test_deepseek_backend -v

# 3) 合成夹具：冻结 prompt/schema 复核（不发请求）
python validation\deepseek-api\verify_planner.py check

# 4) 原案例：完整性 + 门禁彩排（不发请求）
python validation\deepseek-api\verify_original_case.py check

# 5) 真实验证（各≤1 次请求、600 秒硬上限、不重试、不续跑；需 .env）
python validation\deepseek-api\verify_planner.py run --timeout 600
python validation\deepseek-api\verify_original_case.py run --timeout 600

# 6) 完整链路（需 Codex CLI + Docker + .env；本次未启动）
python -m creation_pipeline build validation/deepseek-api/acceptance-input.json
```

`validation/deepseek-api/acceptance-input.json` 恢复为**已定稿的显式脚本 binding 案例**：来源集合、prompt、execution、limits 以及 `binding` 对象与 `validation/final-acceptance-review/input-batch-4.json` 逐字节一致，只额外加入 DeepSeek 提供方配置。

---

## 7. 第二阶段启动检查与阻断（本次）

| 检查项 | 结果 |
| --- | --- |
| 第一阶段提交 | 存在且工作区干净（`58917da` → `43a69ce` → `8d6bc7b` → `d61362f` → `55893da` → `778917b` → `32378a1`） |
| 离线回归 | `386 tests OK (skipped=3)` |
| 小范围真实 planner 验证 | 凭据补齐前为 `blocked_config_invalid`（0 请求）；本轮未重复该脚本 |
| 原案例验证 | 离线完整性检查与门禁彩排通过；**在线回放执行 1 次**：`plan_rejected`（见 §5.3） |
| planner 使用 DeepSeek API | 配置显式 `backend=deepseek_api`；本轮真实请求的账本证明规划阶段确实打到 DeepSeek `/chat/completions`，且不含 Codex 模型名 |
| NativeSession 使用 Codex CLI | 未改动：`review_snapshot`/`stage` 仍走 `codex_command()`，`model.backend` 仍强制 `codex_cli` |
| Codex CLI 可用性 | **可用**：`C:\Users\27343\.codex\.sandbox-bin\codex.exe`（`codex-cli 0.159.2`）。把它加入**本次进程** PATH 后 `codex_command()` 返回该路径；`isolated_options('https','medium','default')` 生成 40 个参数并隔离两个 MCP 服务；`model_call` 用到的 `--ephemeral/--skip-git-repo-check/--sandbox/--output-schema/--json/--model/-c` 均存在。未改系统配置、未重装。`auth_mode=chatgpt` 且有 tokens，但未用模型调用探测其有效性 |
| DeepSeek 配置 | **已补齐**：副本 `.env` 内有 `DEEPSEEK_API_KEY`（35 字符）与 `DEEPSEEK_MODEL=deepseek-flash`；endpoint 保持官方默认（无 `DEEPSEEK_BASE_URL` 覆盖）。修复时发现模板行未取消注释且注释里粘有密钥明文，已改为单条 `DEEPSEEK_MODEL=deepseek-flash`，密钥在文件中仅出现 1 处 |
| Docker | 可用：`29.8.2`，`linux/x86_64` |

结论：**首个阻断点已从“缺凭据”前移到“前批计划语义门禁未通过”**。按“结构与计划语义校验通过后才继续”的要求，唯一一批**未启动**：本轮共 1 次模型调用（仅前批验证，独立记账）、0 次 Docker 构建、0 条业务用例、0 次查询/安装。`first_blocking_point` 与 `next_step` 写入 `validation/deepseek-api/launch-check.json`。

---

## 8. 已知限制与剩余风险

1. **计划语义尚未通过**：DeepSeek 的**单次**产出结构合法但被未改动的夹具门禁拒绝（1 个负向用例）。生产流程会触发修复轮，本轮因“仅一次请求”无法修复，因此既不能说该案例失败，也不能说它通过。
2. **原超时案例是否改善仍未知**：本轮只记录了 158.5 s 完成、200、1 次请求；单次请求不能证明原超时根因已解决，也没有做性能对照。
3. **模型与参数不等价**：原始请求是 Codex `gpt-6-astra`（继承 `reasoning_effort=low`，schema 由 CLI 服务端强制），回放是 DeepSeek `deepseek-flash`（`medium→high`，schema 靠本地校验 + system 消息提示）。账本分别记录，不声称等价。
4. **显式 binding 对新创建仍是硬约束**：已在 input 中明确要求作者交付 `scripts/terminal_fragments.py`，但尚未在真实创建中验证作者会遵守。
5. **.env 使用痕迹**：该密钥曾被误粘在 `.env` 的注释行内（也已出现在本会话输出中），若该会话记录可能外传，建议轮换；本轮未在任何报告或证据中输出其值。
6. **Codex 阶段未迁移**：两种后端的“一次调用”语义不同（CLI 轮次 vs 一次 HTTP 请求），预算账本会同时记录两者，不能直接比较。
7. **迁移只覆盖结构化调用**，且后续批次尚未通过，不能据此判断性能验证完成或整个版本可合并；未执行 merge/push/发布。
