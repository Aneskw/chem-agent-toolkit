# 最终验收报告（真实实验 · 第 14–17 次运行，全部阶段改用 DeepSeek）

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
起因：Codex 账户限额（`run 13`），改为**把发现/编写/独立审阅也接到 DeepSeek API**，
保留 Codex 为默认后端，可一行配置切回。

## 最终结论

**三轮（15–17）全部执行，仍无 Docker 构建**；但这是本项目第一次让**整条模型链**在 DeepSeek 上跑通到
运行时准备之后：发现 ✅ → 编写 ✅ → 独立审阅 ✅ → 执行需求确认 ✅ → **入口绑定/规划前**止步。
每轮都暴露一个**提示契约缺口**，均已修复并回归：

| 轮次 | 调用 | 停止点 | 缺陷（提示契约） | 修复提交 |
| --- | --- | --- | --- | --- |
| 14 | 0 | 保存运行守卫 | `model.backend` 白名单仅 codex_cli | `4b1c535` 后续 guard 修复 |
| 15 | 4 | 编写 | 模型只给 exit-code 检查，无结果断言 | author 提示明确要求可观测断言 |
| 16 | 5 | 运行时准备 | `runtime_requirement` 返回字符串而非记录对象 | API schema 与提示给出对象契约 |
| 17 | 5 | 入口绑定 | SKILL.md 有 4 个 python 代码块且无可执行入口声明 | author 提示给出"唯一可执行入口"规则 |

调用合计 **14 次**（14 轮 0 + 15 轮 4 + 16 轮 5 + 17 轮 5），无重试、无回退、无探针；
失败轮次未重启/未续批。Docker 构建、业务验收、catalog 晋升、安装全部 `not_run`。

> 审查由**当前执行代理**完成，并非独立模型复核。

## 1. 关键改造：原生阶段可切到 DeepSeek（Codex 仍是默认）

- `model.backend` 现支持 `codex_cli`（默认，原样保留）与 `deepseek_api`（单次结构化调用）。
- 切换后每个原生阶段＝**一次有界 chat completion**：同样的 instructions、context、答案 schema、
  receipt/审计目录与调用预算；作者阶段额外返回 `files:[{path,content}]`，由宿主机写入后仍走
  **原封不动的 `delivery.finish` / `validate_package`**。
- 切回只需把 `model.backend` 改回 `codex_cli`；未知后端仍在发请求前被拒。
- 为什么不在 CLI 侧切：本机 CLI 已只支持 `wire_api="responses"`，而 DeepSeek 提供 chat completions，
  因此开关放在管线内而非 provider 配置里。
- 回归：`tests/pipeline/test_api_native_provider.py`（9 项）覆盖开关、提示增补、源文本内联、
  作者文件落盘（含路径穿越/二进制拒绝）、成功与失败的 API 阶段、codex 路径仍走 CLI。

## 2. 三轮的账本

| 项 | run 15 | run 16 | run 17 |
| --- | --- | --- | --- |
| 发现 / 编写 / 审阅 | ✅ / ✅ / — | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ |
| 执行需求确认 | — | `requirements_unknown` | ✅ `required`（引用 `document.py` 原文） |
| 入口绑定 | — | — | ❌ `entry_unsupported`（4 个 python 块、无声明） |
| 规划 / Docker / 验收 | `not_run` | `not_run` | `not_run` |
| 应用层调用 | 4 | 5 | 5 |

## 3. 证据与可复现

```text
validation/deepseek-api/evidence/
  real-batch-run14-20261027/  real-batch-run15-20261027/
  real-batch-run16-20261027/  real-batch-run17-20261027/
```

四轮证据凭据形状命中 **0**。

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 524 OK (3 skipped)
```

`validation/deepseek-api/acceptance-normal-input.json` 现为：`model.backend=deepseek_api`、
`model.api_model=deepseek-v4-pro`、`model_calls=12`、`pin_base_image=true`。

**最终 SKILL.md**：未形成合格交付（候选在 candidates 区）。

## 运行 13 记录（历史，结论保留）

### 运行 13 结论

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
本次授权：最多 3 轮全新实验、每轮 12 次应用层调用；本轮为第 1 轮。
运行目录：`E:\Users\27343\Docker\acceptance-deepseek-run13-20261027`（构建 `20261027T200753-a864f013`）

### 运行 13 结论正文

**本轮被外部资源上限阻断，不是代码缺陷，也不是验收失败。** 10–12 轮暴露的三处缺陷都已修复并回归，
本轮在修复后的代码上重新开始；来源准备、发现、编写三步真实完成，第 3 步**独立审阅**调用被
Codex CLI 账户拒绝：

```
Incomplete Agent turn: exit=1
You've hit your usage limit. Visit https://chatgpt.com/settings/usage to purchase more
credits or try again at Nov 2nd, 2026 1:59 PM.
```

因此：**入口关联、环境规划、Docker 构建、业务验收、晋升、安装全部 `not_run`**；
本轮用掉 **3/12** 次调用（发现 completed、编写 completed、审阅 failed）。

授权中的第 2、3 轮**现在无法执行**：每一轮都需要 Codex CLI 完成发现/编写/独立审阅，
在当前账户额度恢复前同样会在审阅步失败。按“不重启、不续批、不浪费授权”的规则，我没有继续发起
注定失败的两轮，也没有把原生阶段改道到 API 提供方——那属于“全部模型阶段迁移”，本次架构明确不做，
需要你单独授权。

> 审查由**当前执行代理**完成，并非独立模型复核。

### 运行 13 账本

| 阶段 | Provider / 模型 | 状态 |
| --- | --- | --- |
| 来源准备 | — | **通过**（20,662 / 1,580 字节，哈希匹配） |
| 发现 | Codex CLI / `gpt-6-astra` | **completed** |
| 编写 | Codex CLI / `gpt-6-astra` | **completed** |
| 独立审阅 | Codex CLI / `gpt-6-astra` | **failed — 账户用量上限** |
| 入口关联 / 环境规划 / Docker / 业务验收 / 晋升 / 安装 | — | `not_run` |

应用层调用 **3 / 12**；单次 600 s、整轮 3600 s 均未触及；无重试、无回退、无探针；未重启、未续批。

### 运行 13 前的修复

| # | 缺陷 | 修复提交 |
| --- | --- | --- |
| F1 | 关联引文用上游路径而非快照路径 | `2bebb12`（提示给出 `citation_paths`；唯一别名可解析，引文仍按快照字节校验） |
| F2 | `none_documented` 操作被强制要求 checks；规划器看不到作者声明的拒绝检查 | `22548c0` |
| F3 | 完整计划不接受对象编码 | `d1e704b` |

离线回归：**515 OK (3 skipped)**；`verify_prompt_contract`、`verify_acceptance_prompt check`、
`verify_planner check` 均通过；冻结提示 15,204 B。

### 运行 13 处置选项

1. **等待/充值 Codex 额度**（提示的恢复时间：2026-11-02 13:59），之后按同样约束重跑；
   这是唯一不改变架构、可继续验证 `pin_base_image` 与 Docker 阶段的路径。
2. **授权更换原生 CLI/账户**（例如另一台已登录的 CLI 或另一模型），保持“发现/编写/审阅走 CLI、
   结构化调用走 DeepSeek”的边界。
3. **授权把发现/编写/审阅也迁到 DeepSeek**：这是完整模型阶段迁移，需重新评估工具调用循环、
   审阅独立性等，属于架构变更，不能由我自行决定。

### 运行 13 证据

```text
validation/deepseek-api/evidence/real-batch-run13-20261027/
  batch-summary.json  summary.json  sources.lock.json  record.json  run13.log
  agent-turns/00{1-discovery,2-author,3-review}/{command.json,prompt.txt,result.json,stderr.log}
  delivered/{SKILL.md,scripts/...}
```

凭据形状命中 **0**；轮次未被重启或续批。

```powershell
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 515 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付（本轮候选停在 candidates 区）。

## 第 10–12 轮记录（历史，结论保留）

### 10–12 轮结论

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
本次授权：最多 3 轮全新实验，每轮 10 次应用层调用，单次 600 s，每轮 3600 s，
`api_retries=0`，无回退、无探针、失败不重启/不续批；轮次之间自行修复阻断缺陷。
运行目录：`acceptance-deepseek-run10|11|12-20261027`

### 10–12 轮结论正文

**三轮真实实验全部执行完毕，均未通过；Docker 构建仍未发生。** 每一轮都在更深处阻塞，
且每一处阻塞都被定位为管线/协议缺陷并已离线修复：

| 轮次 | 构建 | 调用 | 停止点 | 暴露缺陷 | 处置 |
| --- | --- | --- | --- | --- | --- |
| 10 | `20261027T190606-63ec7fc1` | 4/10 | 入口关联 | 关联提案用上游路径 `rdkit/Chem/Recap.py`，而快照文件是 `document.py`，精确子串找不到候选 | 已修：提示给出允许的 `citation_paths`；唯一快照可别名解析，引文仍按该文件字节校验 |
| 11 | `20261027T191957-78146c53` | 8/10 | 环境规划 R2 | `none_documented` 操作按提示不应带 checks，校验器却要求非空；且规划器看不到作者声明的拒绝检查 | 已修：校验与提示一致；作者声明检查以紧凑形式进入规划约束 |
| 12 | `20261027T193932-92618ce4` | 6/10 | 环境规划 R1 | 完整计划把 `acceptance_json` 返回为对象（补丁路径一直接受两种编码） | 已修：完整计划与补丁共用同一编码归一化；语义门禁照旧拒绝 `invalid_input=true` |

三轮合计 **18/30** 次调用，墙钟约 1 小时，`600 s/次` 与 `3600 s/轮` 均未触及；
无回退、无重试、无认证探针、失败后未重启或续批。
Docker 构建、业务验收、catalog 晋升、安装与安装后使用全部 `not_run`。

> 审查由**当前执行代理**完成，依据源码、调用路径与反例；**并非独立模型复核**。

### 10–12 轮账本与阶段

| 项 | run 10 | run 11 | run 12 |
| --- | --- | --- | --- |
| 来源准备 / 发现 / 编写 / 独立审阅 | ✅ | ✅ | ✅ |
| 入口关联 | ❌ `binding_unresolved` | ✅ 作者声明 `scripts/recap_fragments.py` | ✅ |
| 环境规划 | `not_run` | ❌ 两轮后 `planning_no_progress` | ❌ R1 `model_schema_mismatch` |
| Docker / 业务验收 / 晋升 / 安装 | `not_run` | `not_run` | `not_run` |
| 应用层调用 | 4 | 8 | 6 |

`pin_base_image` 在三轮中均**未被执行**（没有任何一轮进入 preparation 的镜像解析）。

### 10–12 轮修复

| # | 缺陷 | 修复 | 回归 |
| --- | --- | --- | --- |
| F1 | 关联引文路径歧义（快照 vs 上游） | `entry.associate` 提示列出 `citation_paths`；`_candidate_source` 唯一别名解析；绑定记录快照路径+sha256+别名 | `test_association_alias.py`（6） |
| F2 | `none_documented` 操作被强制要求 checks；规划器看不到作者拒绝检查 | `contracts` 与提示一致（required 至少一个具名 check，none_documented/not_applicable 无 checks）；`preparation.declared_checks` 进入规划约束 | `test_input_contract.py`、`test_migrated_execution.py` |
| F3 | 完整计划不接受对象编码 | `normalize_text_fields` 复用于完整计划与 `validate_plan`；语义门禁仍判定状态 | `test_plan_text_fields.py`（6） |

修复后离线回归：**515 OK (3 skipped)**；`verify_prompt_contract`、`verify_acceptance_prompt check`、
`verify_planner check` 全部通过；冻结提示重建为 **15,204 B**。

### 10–12 轮未验证范围

未验证：Docker 构建、全部业务验收、catalog 晋升、默认查询/安装、容器内使用、
`pin_base_image` 的解析与冻结、三态 `none_documented` 的真实选用。

三轮的模式很清楚：每一轮都让链路更深一层（关联 → 规划 ×2 → 规划编码），缺陷都在**提示与
校验器的措辞/编码边界**上，业务语义门禁本身没有放宽。要走到 Docker 至少还需要一轮：
建议 **12 次调用**（3 Codex + 关联/审阅 2 + 规划 2–3 + 契约诊断/余量），其余约束不变。
第 12 轮的对象编码缺陷修复后，同一计划会进入语义门禁并得到可修复的诊断，而不是直接终止。

### 10–12 轮证据

```text
validation/deepseek-api/evidence/
  real-batch-run10-20261027/  （26 文件，202 KB）关联提案、提示、记录
  real-batch-run11-20261027/  （85 文件，658 KB）两轮规划与拒绝诊断
  real-batch-run12-20261027/  （56 文件，413 KB）对象编码失败的原样回答
```

三轮证据均 0 次凭据形状命中；失败轮次从未被重启或续批。

```powershell
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 515 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付；三轮的候选都只落在 `library/candidates/rdkit-recap-terminal-fragments`。

## 运行 9 记录（历史，结论保留）

### 运行 9 结论

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
本次运行目录：`E:\Users\27343\Docker\acceptance-deepseek-run9-20261027`
构建 ID：`20261027T183705-770487a9`（18:37:05 → 18:56:05，墙钟 19 分 0 秒）

### 运行 9 结论正文

**仍然未通过，但已推进到真实规划阶段。** 本批首次在修复后的代码上完成
来源准备 → 发现 → 编写 → 独立审阅 → 入口关联（作者声明的 `scripts/recap_terminal.py`），
并以 **DeepSeek API** 执行了两轮真实环境规划：

1. 第 1 轮：`deepseek-v4-pro`，469 s，17,403 prompt / 36,963 completion token。计划被语义门禁拒绝：
   `invalid_input=required` 但 `operations` 未附带具名 checks → `Each input operation must apply named input checks`。
2. 第 2 轮（修复补丁）：被**本地 schema 校验**拒绝：
   `operations/1: 'value_json' is a required property` → `model_schema_mismatch`，批次阻塞。

第 2 轮失败暴露的是**协议缺陷**（`remove` 操作被强制要求带 `value_json`），已离线修复；
Docker 构建、业务验收、晋升、安装均 `not_run`。本批 **7/8** 次调用，剩余 1 次不足以完成任何阶段，
按规则停止，**未重启、未续批、未显式恢复**。

> 独立代码与迁移审查由**当前执行代理**完成，依据源码、调用路径与反例；**并非独立模型复核**。

### 运行 9 基线

| 项 | 值 |
| --- | --- |
| 副本运行前 HEAD | `7f48cf4`（`feat(runtime): resolve and pin the base image digest instead of trusting a tag`） |
| 运行前工作区 | 干净 |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| Codex CLI | 0.164.0-alpha.11.1，仅本进程 PATH |
| DeepSeek | 官方端点，`deepseek-v4-pro`，`api_retries=0`，流式，无回退 |
| 新增配置 | `pin_base_image=true`（本批启用），`model_calls=8`，单次 600 s，整批 3600 s |

本轮运行**之后**的本地改动：`planner.PATCH_SCHEMA` 不再要求 `remove` 携带 `value_json`
（`patch_plan` 对 add/replace 显式要求、对 remove 忽略）、补丁协议与 POLICY 措辞同步、
`tests/pipeline/test_patch_encoding.py` 与 `test_planner_schema.py` 覆盖该规则、
冻结提示/证明重新冻结、本报告与 `validation/deepseek-api/` 证据。

### 运行 9 各阶段

| 阶段 | Provider / 模型 | 状态 | 证据 |
| --- | --- | --- | --- |
| 来源准备 | — | **通过** | `sources.lock.json`（20,662 / 1,580 字节，哈希匹配） |
| 发现 | Codex CLI / `gpt-6-astra` | **通过**（143 s） | `agent-turns/001-discovery` |
| 编写 | Codex CLI / `gpt-6-astra` | **通过**（191 s） | `agent-turns/002-author`，包布局合规 |
| 独立审阅 | Codex CLI / `gpt-6-astra` | **通过**（76 s） | `agent-turns/003-review` |
| 入口关联 | DeepSeek / `deepseek-v4-pro` | **通过** | `binding.json`：`scripts/recap_terminal.py`，`declaration_source=author_declaration`，`association=reviewed` |
| 环境规划 R1 | DeepSeek / `deepseek-v4-pro` | **语义拒绝** | `planning/0/rejection.json`：`invalid_input=required` 但无具名 checks |
| 环境规划 R2 | DeepSeek / `deepseek-v4-pro` | **模型输出无效** | `planning/1/model-0/request.json`：`operations/1` 缺 `value_json` |
| Docker 构建 | — | `not_run` | 规划未通过 |
| 业务验收 | — | `not_run` | — |
| catalog 晋升 | — | `not_run` | `candidate_saved`（candidates 区） |
| 安装 / 安装后使用 | — | `not_run` | 无合格正式产物 |

### 运行 9 调用账本

| 项 | 实际 |
| --- | --- |
| 应用层调用 | **7 / 8**（3 Codex + 4 DeepSeek：关联、关联审阅、规划 R1、规划 R2） |
| 模型 | Codex `gpt-6-astra`；DeepSeek `deepseek-v4-pro`（官方端点） |
| 单次上限 | 600 s 未触及；最长一次 469 s（规划 R1） |
| 批次时长 | 19 分 0 秒（3600 s 预算未触及） |
| 重试 / 回退 | `api_retries=0`；无 provider 切换；无探针 |
| 240 s 观测 | `observe`，`max_silence_seconds` 3.96–6.06 s，未触发终止 |
| 停止原因 | 规划 R2 本地 schema 校验失败（模型输出无效），非预算/超时 |
| 发送指纹（本批真实记录） | R1：prompt `ea12a80b…`（50,178 B）+ schema `141f8b01…`；R2：prompt `1b5365e5…`（62,182 B）+ schema `0ac6d7fa…` |

### 运行 9 审查发现

| # | 严重度 | 位置 | 触发条件 | 影响 | 处置 |
| --- | --- | --- | --- | --- | --- |
| F1 | **阻断** | `runtime/planner.py::PATCH_SCHEMA` | 任何 `remove` 操作（无值可编码） | 合法的修复补丁被判 `model_schema_mismatch`，整批阻塞（本批 7/8 调用后） | **已修**：`value_json` 仅对 add/replace 必需；协议与 POLICY 措辞同步；缺失值给明确错误；回归覆盖 |
| F2 | 中 | `acceptance.contracts` + POLICY | 计划声明 `invalid_input=required` 却不给具名 checks | 语义拒绝并消耗一轮调用（R1） | 门禁不变（该拒绝正确）；提示已含"required 需具名 checks；fixed-example 用 not_applicable"，下批观察 |
| F3 | 信息 | 预算结构 | 3 Codex + 关联/审阅 + 规划 2 轮 = 7/8 | 无余量做第二次 Docker/修复 | 建议下批 10 次，或把契约要点前置到发现阶段 |
| F4 | 信息 | `pin_base_image` | 本批规划未通过，未进入 preparation | 新增的镜像摘要解析在本批**未被执行** | 如实记录，机制测试已覆盖 |

未证明事项（待核查）：`none_documented` 三态在真实规划中的选用（本批模型选了 `required`）；
镜像摘要解析与 Docker 构建（未达该阶段）；Markdown 入口路径（本批为脚本入口）。

### 运行 9 能力映射

| 能力 | 机制 | 证据 |
| --- | --- | --- |
| 发现 / 编写 / 独立审阅 | Codex CLI `NativeSession` | 本批 3 次真实调用全部 completed |
| 结构化调用（关联、契约、规划） | `model_call` → `deepseek_api`，本地 Schema + 语义门禁 | 本批 4 次真实调用；R1 语义拒绝、R2 本地 schema 拒绝，均非崩溃 |
| 入口解析优先级 | 调用方绑定 → 作者声明 → 保守识别 | 本批走作者声明（`author_declaration`），未预填 binding |
| 单一 catalog / 资格 | `store.py` 单事务 + `library.py` 门面，查询/安装/晋升均过 `qualify()` | `test_skill_library`、`test_delivery_protocol` |
| 交付分离 | `deliveries/` ↔ `evidence/`（冻结指纹）↔ `runs/`（动态） | `evidence.py:verify`，本批真实写入 |
| 提示协议与发送指纹 | `INPUT_CONTRACT_SPEC` 单一源 + `build_prompt/schema_for/provenance` | 本批两轮真实记录 prompt/schema sha256 |
| 删除 | 无 | 生产树对 `validation/`、`frozen/` 0 引用 |

### 运行 9 未验证范围

未验证：Docker 构建、全部业务验收、catalog 晋升、默认查询/安装、容器内使用、镜像摘要解析、
三态 `none_documented` 的真实选用、故障注入类资格撤销。

最小剩余工作（需另行授权）：
1. 用包含 `value_json` 修复的代码新开一批；**建议 10 次调用**（3 Codex + 关联/审阅 2 + 规划 2–3 + 余量），
   仍受 600 s/单次、3600 s/整批、`api_retries=0`、首次 Docker 失败即停约束。
2. 若必须 8 次：把"required 必须有具名 checks"与"remove 无 value_json"前置到发现/关联上下文，降低规划轮次。
3. Docker 阶段尚未真实验证 `pin_base_image` 的解析与冻结，下批需观察 `base-image.json` 与
   `FROM repo@sha256:...` 实际渲染。

### 运行 9 证据

```text
validation/deepseek-api/evidence/real-batch-run9-20261027/
  batch-summary.json  summary.json  record.json  sources.lock.json  run9.log  binding.json
  agent-turns/00{1-discovery,2-author,3-review}/{command.json,prompt.txt,result.json}
  planning/{0,1}/prompt-0.txt prompt-provenance-0.json response-0.json rejection.json
  planning/{0,1}/model-0/{request.json,response.json,schema.json}
  delivered/{SKILL.md,scripts/recap_terminal.py,...}
```

凭据扫描：本目录 0 次凭据形状命中。

```powershell
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 503 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付（候选位于 `library/candidates/rdkit-recap-terminal-fragments`）。

## 附录 A：运行 8 记录（历史，结论保留）

### A.1 运行 8 结论

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
本次运行目录：`E:\Users\27343\Docker\acceptance-deepseek-run8-20261027`
构建 ID：`20261027T171821-354e8d22`（17:18:21 → 17:24:58，墙钟 6 分 37 秒）

### A.2 运行 8 结论正文

**未通过（阻塞：作者交付违反包布局，在 3/8 次调用后失败）。** 来源准备与发现阶段真实通过；
编写阶段交付了根级 `LICENSES.txt`，被既有包布局校验拒绝；唯一一次作者修复轮此前**只被告知**
check 定义错误（`json_equals must be an object`），于是修好该错误后仍因布局失败而终止。
独立审阅、入口关联、环境规划、Docker 构建、业务验收、catalog 晋升、安装与安装后使用全部 `not_run`。

本批暴露并已离线修复两个**阻断性**缺陷（见 §4）：作者可见的打包规则从未写明"闭合角色布局"，
以及 `finish()` 只报告第一个校验问题（导致一次修复轮被浪费）。修复后离线回归 493 OK (3 skipped)。
本批**没有**执行为验证而额外增加的任何真实调用，也没有重启、续批或恢复。

> 独立代码与迁移审查由**当前执行代理**完成，依据源码、调用路径与反例；**并非独立模型复核**。

### A.3 运行 8 基线

| 项 | 值 |
| --- | --- |
| 副本运行前 HEAD | `d569bb0`（`feat(prompt): record the identity of what the acceptance path actually sends`） |
| 运行前工作区 | 干净（`git status --porcelain` 空） |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.EXE`（0.164.0-alpha.11.1），仅本进程 PATH |
| DeepSeek 配置 | 官方端点，`deepseek-v4-pro`，`api_retries=0`，流式，单次 600 s，无回退 |
| 取源预检 | 通过：`Recap.py` 20,662 B / `license.txt` 1,580 B，SHA-256 与固定值一致 |
| Docker | 可用：linux/x86_64，8,115,138,560 B 内存，12 CPU（`docker info`） |
| 本批授权 | 8 次应用层调用、单次 600 s、整批 3600 s、240 s 仅观测 |

本轮运行**之后**的本地改动（不改变本批已记录的运行证据，但影响后续批次）：
`artifacts/delivery.py`（聚合反馈）、`docs/skills/packaging.md` 与 `minimum.md`（闭合布局规则）、
`tests/pipeline/test_author_feedback.py`（回归）、本报告与 `validation/deepseek-api/` 证据。

### A.4 运行 8 各阶段

| 阶段 | Provider / 模型 | 状态 | 证据 |
| --- | --- | --- | --- |
| 来源准备 | — | **通过** | `sources.lock.json`，两文件哈希匹配 |
| 发现 | Codex CLI / `gpt-6-astra` | **通过** | `candidate-discovery.json`：1 个候选 |
| 编写 | Codex CLI / `gpt-6-astra`（2 轮） | **失败** | 根级 `LICENSES.txt` → `Unsupported file role` |
| 独立审阅 | Codex CLI | `not_run` | 未达该阶段 |
| 入口关联 | DeepSeek | `not_run` | 未达该阶段 |
| 环境规划 | DeepSeek | `not_run` | 未达该阶段 |
| Docker 构建 | — | `not_run` | 未达该阶段 |
| 业务验收 | — | `not_run` | 未达该阶段 |
| catalog 晋升 | — | `not_run` | 仅 `candidate_saved`（candidates 区） |
| 安装 / 安装后使用 | — | `not_run` | 无合格正式产物 |

候选记录：`status=failed`、`error="Unsupported file role: LICENSES.txt"`、`repair_rounds=1`、
`checks=[author_or_validation: fail]`。交付文件（原样保留在证据中）：
`SKILL.md`（4,520 B）、`LICENSES.txt`（3,200 B）、`scripts/terminal_fragments.py`（1,596 B）。

### A.5 运行 8 调用账本

| 项 | 实际 |
| --- | --- |
| 应用层调用 | **3 / 8**（turn 1 发现，turn 2 编写，turn 3 编写修复） |
| 提供方 | 全部 Codex CLI（`gpt-6-astra`，HTTPS，medium/default）；**本批 DeepSeek 调用 0 次** |
| 单次时长 | 未触及 600 s 硬上限；CLI 内部重连未出现 |
| 批次时长 | 6 分 37 秒（3600 s 预算未触及） |
| 重试 / 回退 | `api_retries=0`；无提 provider 切换；未做认证探针 |
| 240 s 观测窗口 | `progress_watch=observe`，无终止 |
| 停止原因 | 作者修复轮后包布局校验失败（非预算、非超时、非模型不可用） |

### A.6 运行 8 审查发现

| # | 严重度 | 位置 | 触发条件 | 影响 | 处置 |
| --- | --- | --- | --- | --- | --- |
| F1 | **阻断** | `docs/skills/packaging.md`、`minimum.md`（作者可见上下文） | 交付任何根级非 `SKILL.md` 文件（如 `LICENSES.txt`、`LICENSE`、上游模块副本） | 候选在消耗作者调用后必然失败；本批 3/8 调用即止步于此 | **已修**：明确闭合布局（`SKILL.md` 唯一顶层文件；其余必须在 `scripts/references/examples/resources/assets` 下；许可文本放 `references/`），并加回归测试 |
| F2 | **阻断** | `artifacts/delivery.py::finish` | 同时存在包布局错误与 check 定义错误 | 修复轮只收到第一个错误，修好后仍因未告知的问题失败（本批即如此） | **已修**：一次性聚合所有问题（布局/check/issues/entry），单一修复轮可见全部；加回归测试 |
| F3 | 中 | `runtime/planner.py:126`（`pin_base_image`） | 需要"基础镜像同版重建" | 只按构建记录镜像身份，不保证重建同一镜像 | **未修**（既有已知缺口，保持显式拒绝而非静默），报告为未验证边界 |
| F4 | 信息 | 本批执行路径 | 批次在关联/规划前终止 | 三态非法输入提示、嵌套补丁、provenance 记录在本批**未被执行**；先前真实请求早于这些改动 | 如实记录，不以机制测试代替 |

未证明事项（待核查）：Markdown 定位/提取在真实候选上的行为（本批未到关联阶段，仅有机制测试）；
跨平台 manifest 已在 `artifacts/evidence.py` 以"排序无关、逐项 path/sha256/bytes"比较并有测试，但本批
未在真实冻结树上重复验证。

### A.7 运行 8 能力映射

| 能力 | 机制 | 证据 |
| --- | --- | --- |
| 发现 / 编写 / 独立审阅 | Codex CLI `NativeSession`，无工具、`--output-schema` | 本批真实运行 3 次；`test_native`、`test_components` |
| 结构化调用（入口关联、环境规划、契约诊断） | `model_call` → `deepseek_api`，本地 JSON Schema + 语义门禁 | 本批未执行；真实请求证据在 run 3–7 |
| 单一主入口与状态协议 | `pipeline` 单一编排；`runtime/service.py` 各恢复/构建入口 | `test_runtime_recovery`、`test_reconnect_recovery` |
| catalog 唯一实现 | `artifacts/store.py` + `artifacts/library.py` 门面 | 查询/安装/晋升均经 `qualify()`/`reconcile()`；`test_skill_library`、`test_delivery_protocol` |
| 交付分离 | 作者回执 `deliveries/` ↔ 冻结证据 `evidence/` ↔ 动态记录 `runs/` | `test_delivery_protocol`；`evidence.py` 冻结/校验 |
| 资格过滤 | `qualification()`/`install_from_library()` 复核当前 Docker 证据与内容撤销 | `store.py:206/423`；查询不因宿主暂不可用而永久失格（`host_unavailable` 保留记录、标 deferred） |
| 新增（本轮前） | 三态 `input_contract`、嵌套补丁、`scope-delta`、prompt provenance/契约审计 | `test_input_contract`(26)、`test_patch_encoding`(23)、`test_prompt_contract`(7)、`test_prompt_provenance`(5) |
| 删除 | 无（未删除仍被调用的成熟逻辑） | 生产树对 `validation/`、`frozen/` 的历史依赖审计为 **0** |

### A.8 运行 8 未验证范围

未验证：独立审阅、入口关联、环境规划、DeepSeek 三态提示的真实执行、Docker 构建、业务验收、
catalog 晋升、安装与容器内使用、镜像丢失/漂移的破坏性验证。

最小剩余工作（需另行授权）：
1. 用修复后的代码**新开一批**正常创建（建议 8→10 次调用，因关联+审阅+规划需更多余量），
   仍受 600 s/单次、3600 s/整批、`api_retries=0`、首次 Docker 失败即停的约束。
2. 若仍要在 8 次内完成，需要在作者阶段减少往返（例如把布局规则前置到发现阶段上下文）。
3. F3（基础镜像同版重建）如需保证，必须实现 `pin_base_image` 或显式接受"镜像身份随构建记录"。

### A.9 运行 8 证据

```text
validation/deepseek-api/evidence/real-batch-run8-20261027/
  batch-summary.json  summary.json  record.json  sources.lock.json  checkpoint.json
  candidate-discovery.json  run8.log
  agent-turns/00{1-discovery,2-author,3-author}/{command.json,prompt.txt,result.json}
  delivered/{SKILL.md,LICENSES.txt,scripts/terminal_fragments.py}
```

凭据扫描：本目录 0 次凭据形状命中；`.env` 值从未写入证据。

```powershell
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 493 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付（候选位于 `library/candidates/rdkit-recap-terminal-fragments`）。

## 附录 B：运行 1–7 记录（历史，结论保留）

### B.1 运行 7 结论

**未通过（阻塞：规划契约未通过 + 模型重复同一非法补丁）。** 前五个阶段真实通过；环境规划在两次尝试、4 次 DeepSeek 调用后仍未产出合格计划，第 3 次尝试提交了**与上一次完全相同**的非法补丁，被既有"无进展"规则拦下（`plan_unresolved`）。Docker 构建、业务验收、晋升、安装全部 `not_run`。

值得记录的是：运行 6 暴露的**管线崩溃缺陷**（结构化值写进文本字段导致 `TypeError` 逃逸、整批 `failed`）已修复，并在运行 7 中**验证生效**——同样的补丁现在被干净地判为无效补丁，进入修复轮而不是崩溃。

> 审查与判定由**当前执行代理**完成，非独立模型复核。

---

### B.2 运行 7 基线与提交

| 项 | 值 |
| --- | --- |
| 运行时 HEAD | `6b468fc` |
| 本次改动 | `33d087f`：policy 增加 selector 字面 token 与 patch 编码正反例；预算 8 → 12<br>`6b468fc`：`patch_plan` 应用补丁后立即按 `PLAN_SCHEMA` 校验，文本字段非文本时报 `PlanningError`<br>`2c767f4` 之后：**预算已改回 8**（运行 7 在 10/12 时因无进展停止，证明停止与预算无关） |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `bin\2993767bd1dfb009\codex.EXE`（0.164.0-alpha.11.1，code-mode host 齐全），仅进程 PATH |
| DeepSeek | 官方端点，`deepseek-v4-pro`，`api_retries=0` |
| 取源预检 | 通过（20,662 / 1,580 字节，哈希匹配） |

### B.3 运行 1–7 一览

| 运行 | 结果 | 根因 / 处置 |
| --- | --- | --- |
| 1 | 发现失败 | CLI 缺 `codex-code-mode-host.exe` → 换完整安装 |
| 2 | 规划 52.5 s 中断 | `_Reader` 切片超时毒化 → 已修（读取超时=剩余期限、不重试、捕获 socket） |
| 3 | 规划 3 轮语义拒绝 | `deepseek-flash` 违反三条夹具规则 → policy 加正反例 |
| 4 | 发现前失败 | 源码下载被截断 → 固定哈希正确拒绝 |
| 5 | 规划 2 轮 → 预算耗尽 | v4-pro 计划被 selector 规则拒绝；补丁 `value_json` 非法 → policy 补两条 |
| 6 | **崩溃 `failed`** | 补丁把结构化值写进 `acceptance_json` → `json.loads(dict)` `TypeError` → 已修 |
| 7 | 阻塞 `plan_unresolved` | 见 §3 |

### B.4 运行 7 各阶段

| 阶段 | Provider | 状态 |
| --- | --- | --- |
| 来源准备 | — | **通过** |
| 发现 | Codex | **通过** 166.4 s |
| 编写 | Codex | **通过**（1 次修复）247.5 s + 67.4 s |
| 独立内容审阅 | Codex | **通过** 89.1 s |
| 入口关联 | DeepSeek v4-pro | **通过**（作者声明 markdown 入口） |
| 关联独立审阅 | Codex | **通过** |
| 环境规划 | DeepSeek v4-pro | **失败**，见 §3.1 |
| 构建 / 验收 / 晋升 / 安装 | — | not_run |

#### B.4.1 规划两轮与停止点

| 尝试 | DeepSeek 调用 | 结局 |
| --- | --- | --- |
| 0 | 514.4 s，完整计划 | 拒绝：`Case acceptance requires an exact quotation from read source` |
| 1 | 251.3 s / 269.0 s / 240.8 s（3 轮） | 三轮补丁**全部**被同一 schema 错误拒绝：`Patched plan schema error: {...} is not of type 'string'`（把结构化对象写进 `case_json`）；第三轮重复同一诊断 → 触发"重复非法补丁/无进展"规则停止 |

停止码：`plan_unresolved`，detail 为 `No progress: repeated invalid plan patch: ...`。
**不是预算耗尽**（10 / 12），也**不是超时或传输失败**。

#### B.4.2 本次修复在真实运行中的验证

运行 6 的崩溃点现在表现为：

```
patch-rejection-0.json: Patched plan schema error: {'args': [...], ...} is not of type 'string'
```

即：非法补丁 → 干净的 `PlanningError` → 进入修复轮（并最终由无进展规则收尾），不再让整批 `failed`。

### B.5 运行 7 调用账本与预算

| 项 | 值 |
| --- | --- |
| 应用层调用 | **10 / 12**（当时上限 12；本次已改回 8，见 §7） |
| Codex 回合 | 4（166.4 / 247.5 / 67.4 / 89.1 s） |
| DeepSeek 请求 | 5（关联 1；规划 4，其中 3 轮为修复并全部被拒），全部 HTTP 200、无重试 |
| API 重试 / CLI 重连 | 0 / 0 |
| 单次最长 | 514.4 s ≪ 600 s |
| 批次墙钟 | 2,088 s ≪ 3,600 s |
| 终止原因 | 无进展（重复非法补丁），非预算、非超时 |

### B.6 审查发现（累计）

| # | 严重度 | 位置 | 状态 |
| --- | --- | --- | --- |
| F1 | high | CLI 缺 code-mode host | 已解决（换完整安装） |
| F7 | high | `_Reader` 超时毒化 + `connection.sock` 失效 | 已修并验证 |
| F8 | medium | 失败分支缺取证 | 已修 |
| F11 | **high** | `patch_plan` 允许把结构化值写入文本字段，`TypeError` 逃逸导致整批 `failed` | **已修并验证**（`6b468fc`） |
| F9 | medium | 规划对验收契约的遵守 | **未收敛**：每次失败点不同（selector token → 资源引用 → 用例引用 → 补丁编码），第 7 次尝试还重复了同一非法补丁 |
| F10 | medium | 编写回合接近单次上限（247 s / 500 s 波动） | 观察项 |
| F3 | medium | `pin_base_image` 未实现 | 未实测 |
| F4/F5/F6 | low/info | 入口声明范围、渲染确定性、参数映射 | 已记录 |

**待核查**：跨平台换行下的 manifest 严格性；"较新审阅拒绝对旧计划恢复"缺真实反例。

### B.7 运行 7 未验证范围

规划通过、计划语义门禁通过、Docker 构建、全部业务验收、catalog 晋升、默认/候选查询、隔离安装、容器内实际使用。

### B.8 运行 7 最小剩余工作（需授权）

0. **预算**：`validation/deepseek-api/acceptance-normal-input.json` 当前是 **12 次**
   （运营者本轮临时上调；此前曾改回 8）。运行 7 在 **10/12** 因"重复非法补丁/无进展"
   停止，因此**停止点与预算无关**。
1. **已实现、尚未验收的协议改动**（本轮仅代码 + 离线验证，0 次真实模型调用）：
   * **嵌套指针**：`/acceptance_json/<pointer>`、`/tests/<i>/case_json/<pointer>` 先解码
     该 JSON 文本字段、在内部应用指针、再重新编码；改一条 check/selector/断言不再需要
     重发整段文档，也不必双重编码或整段替换 `/tests`。锁定计划仍禁止触碰
     `/tests` 与 `/acceptance_json`，补丁仍是全有或全无。
   * **撤回范围带保护**：锁定修复只能增长；被拒草稿的修复可撤回**自己**过度承诺的
     用例/用途/检查，但调用方给定的必需用例名、已接受用例内容与上游 fixture 不可删改；
     全量重写走同一检查，撤回写入 `planning/<n>/scope-delta-<k>.json`，不静默缩范围。
   * **资源评估可诚实表达**：`status=unknown` 不再要求引用，但须在 `unresolved` 写明
     未定项；执行策略不变，`resources_unknown` 仍阻止 Docker。
   * **policy 去重**：capture_stdout、case_json 键表、修复期范围保持各只保留一处权威
     表述（fixture 示例仍是可执行反/正例）。
   * **非法输入三态化（按 operation）**：`required` / `none_documented` /
     `not_applicable` 分开判定，"要求"与"是否已验证"分开输出
     （`coverage_complete` / `validation_gaps` / `blockers`）。判定依据包含**交付接口
     自己的承诺**（作者/配置声明的拒绝检查、独立审阅过的要求引文、调用方 requirements
     文本），上游沉默不能豁免；`none_documented` 要求记录检查材料及其指纹、范围、理由、
     limitation 与独立确认，且**不能**替代用户明确要求的非法输入验收——缺独立审阅产物时
     `invalid_input_review_missing` 阻塞。修复轮降级必须带证据，锁定契约不可改。
   * **提示协议已与校验器同步**：三态规则只有一处权威文本（`INPUT_CONTRACT_SPEC`），
     同时渲染进 POLICY 正文与 `acceptance_json` 的 schema description，两者无法各说各话；
     修复协议抽成生产与审计共用的 `patch_protocol()`。`verify_prompt_contract.py` 离线重建
     POLICY、补丁协议、两份 schema 以及**冻结的** prompt/schema 并核对：校验器要求的字段与
     状态必须出现，旧的"两态/整段替换"表述必须消失，修复反馈必须点名缺失证据。审计接入
     测试套件（`test_prompt_contract`），规则与提示脱节即失败。
     代价是提示变大：POLICY 9.5 KB → 12.1 KB，schema description 3.9 KB → 5.7 KB，
     frozen prompt 12,291 B → **14,814 B**（已重新冻结）。
   * **正式验收路径只用当前代码生成 prompt/schema，并记录最终发送指纹**：生产代码不读取
     `validation/deepseek-api/frozen/`（审计断言 0 处引用），每轮提示由
     `planner.build_prompt()`、答案 schema 由 `planner.schema_for()` 从当前模块对象生成；
     每轮在审计目录写入 `prompt-<n>.txt` 与 `prompt-provenance-<n>.json`（prompt/schema/
     policy/acceptance description 的 sha256 与字节数），两种后端的 receipt 都记录
     `prompt_sha256`/`prompt_bytes`/`schema_sha256`（DeepSeek 另记请求体 `messages_sha256`）。
     `validation/deepseek-api/prompt-provenance.json` 离线固化当前代码身份，并用**真实
     planner** 跑到首次模型调用之前，复现已保存 RECAP 案例的 round-0 提示
     （`95f48639…`，schema `141f8b01…`）与其冻结夹具（`50460c7d…`）不同，证明验收不依赖该夹具。
     校验：`verify_acceptance_prompt.py check`、`tests/pipeline/test_prompt_provenance.py`。
   * 这些改动没有放宽任何验收门禁，但**也没有被真实批次验证**。RECAP 历史已接受计划仍是
     `required`（引用交付 `entry/skill.py` 的空白校验），`verify_original_case check`
     显示它在未放宽的门禁下通过（8 个用例）；因此该案例不会、也不应靠新增
     `none_documented` 过关。
2. 之后重跑唯一一批（12 次预算、3600 s、新隔离目录）。
3. 若仍不收敛，则需要重新评估：要么接受"该模型在 8–12 次预算内无法满足这套验收契约"，要么改变策略（更强模型/更多预算/把这套契约拆成可迭代的更小步骤）。

### B.9 运行 7 证据

```
validation/deepseek-api/evidence/
  real-batch-20261027/  real-batch-run2-20261027/  real-batch-run3-20261027/
  real-batch-run4-20261027/  real-batch-run5-20261027/  real-batch-run7-20261027/
```
运行 6（崩溃）的证据并入本报告的 F11 描述与运行 7 的验证记录；凭据在全部运行树中出现 **0 次**。

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 490 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付（候选在 `library/candidates/`）。

### B.10 运行 7 边界声明

未通过只说明：在 12 次预算内该模型未产出满足既有验收契约的计划，且修复轮出现重复无进展。它不说明门禁有误，也不说明历史 600 s 超时根因已解决、性能达标或版本可合并。未执行 merge / push / 发布，未修改源目录，未删除共享镜像；未自动重启、续批或恢复。
