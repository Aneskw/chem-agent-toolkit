# 合并版最终验收：任务一（独立审查）与环境预检

执行日期：2026-10-26（第三轮）。基线提交 `746105a`，分支 `integration/planner-timeout`，工作区干净。本文件只覆盖**任务一 + 环境预检**；任务二（修复后正常新创建的真实验收）尚未开跑，需要单独授权真实模型调用批次。

## 1. 环境预检

| 项 | 结果 |
| --- | --- |
| Git | 分支 `integration/planner-timeout`，HEAD `746105a`，`git status --short` 为空 |
| 工作区 | 两个 worktree：本仓库与 `chem-agent-toolkit-planner-experiment`（`experiment/planner-protocol-v1`，非本次对象） |
| Python | 3.14.3 |
| 全量测试 | `python -m unittest discover -s tests -t . -v` → **286 项、3 跳过、全绿**（118.123 秒，记录见 `validation/final-acceptance-review/tests-baseline.txt`） |
| Docker | 29.8.2，Docker Desktop，Linux amd64 容器（x86_64 / overlayfs），可用 |
| 已存在镜像 | `chem-integrated:6f7bc044…-2871d99c`（a617ef6e，历史 accepted 构建）、`chem-validation:markdown-entry-20261026` 等，均未删除 |
| 后端可达性 | **不稳定**：连续 3 次 `codex doctor --json` 得到 provider_reachability = fail / fail / ok（每次约 8 秒超时），websocket_reachability = ok / warning / ok |

网络细节（独立复核，非 CLI 探针）：

- 直连 TCP 443 `chatgpt.com` 成功（1.07 秒）。
- 直连 HTTPS GET 到 `chatgpt.com/backend-api/codex/models` → 401（可达）但耗时 **12.3 秒**。
- 经本机代理 `127.0.0.1:7897` 同一请求 → 401，**1.6 秒**。

结论：Docker 与测试基线健康；**模型后端路径当前间歇性、且直连明显偏慢**（单次请求约 12 秒）。CLI 的 HTTP 可达性探针有约 8 秒上限，因此在慢路由下会随机报 fail，而同一时刻 WebSocket 握手仍可能成功。对下一批受控实验（已定为 HTTP/SSE）的直接影响：

1. 开跑前必须现场确认 `network.provider_reachability = ok`，否则 HTTP/SSE 实验大概率直接死在前置检查上。
2. 若直连持续 12 秒级慢，建议先让本机代理/TUN 走快速节点，或经你批准后为子进程显式传 `HTTPS_PROXY`（实测 1.6 秒），把它作为**受控实验的显式配置**而不是改生产默认。
3. 这不是代码缺陷，不得计入验收结论；但必须在报告里作为"实验条件"记录。

## 2. 单一架构盘点（自做部分）

- **单一 CLI 入口**：`python -m creation_pipeline`，子命令 `build / discover / plan / revise / resume / check / install / library / clean / runtime-build / runtime-prepare / runtime-validate / runtime-resume / runtime-inspect / runtime-import / runtime-relocate`（`creation_pipeline/cli.py`）。没有第二套旧创建/发布入口。
- **单一 catalog 实现**：`artifacts/store.py` 是唯一事务实现，`artifacts/library.py` 只是再导出（`adopt, entries, get, install_from_library, slug`）。
- **旧目录/旧产物依赖**：生产代码中 grep `newpipeline`、`chem-agent-toolkit_newpipeline`、`me-b`、`partner-pipeline`、`chem-agent-toolkit-recap-partner`、`validation/`、`docs/integration` **均无匹配**，即运行时不读旧项目目录、不读验证记录、不读文档。
- **运行时接口**：`runtime/interface.py` 用 `RuntimeRequest` 冻结指纹（package/source/binding/environment/acceptance、frozen_directory、freeze_sha256）并要求执行器 `preflight/build/validate/verify_current`；`runtime/strict.py` 要求每条报告 `status=execution_passed`、`acceptance_version=2`、`current_acceptance_validated=True` 且数量等于预期，才可能被判通过。
- **证据/素材安装**：`runtime/installation.py::install_envelope` 先比较 manifest 再复制，复制后再比较，失败时回滚删除目标目录；拒绝已存在或含链接的目标。

## 3. 独立审查发现

三路只读审查（catalog 与资格 / 入口绑定与冻结断言 / 进程监督与失败分类）各自独立读代码，允许的探针只有阅读与 `python -m unittest tests.pipeline.<module> -q`（未改任何文件、未跑模型、未跑 Docker）。

### 3.1 catalog、资格、交付、恢复（审查 A）

| # | 严重度 | 位置 | 问题 | 影响 | 状态 |
| --- | --- | --- | --- | --- | --- |
| A1 | MEDIUM | `artifacts/store.py:118-119`、`store.py:74` | `lock.open("x")` 建文件与写入 pid 之间有崩溃窗口，留下 0 字节 `.catalog.lock`；`release_dead_lock` 直接 `int(data)`，空内容抛 ValueError，`--recover-lock` 永久失败，之后每次 `store.locked()` 都 `FileExistsError` | 库只能靠手工删锁文件救回；**fail-closed，不损坏数据** | 已证明 |
| A2 | MEDIUM | `store.py:186-225`（`entries`→`reconcile`）、`store.py:174-183` | `library LIB` 这个"读"会重跑 `qualify → evidence → verify_current`；Docker 引擎短暂不可用或镜像/tag 瞬时缺失时，把 accepted 持久降级为 candidates 并覆盖 `current_qualification`，不保留先前 accepted 记录 | 一次普通查询即可因**瞬时**主机状况永久撤销资格；主机恢复后也不会自动回滚，需显式 `runtime-resume`。同样的触发也适用于"复制库后未 `runtime-relocate` 就先查询" | 已证明（瞬时故障后果待实测） |
| A3 | LOW | `store.py:177-181` 对比 `docs/pipeline/runtime-recovery.md:101-103` | `execution_location` 守卫只在 `requirement.status == 'required'` 时执行；含 `not_required` accepted 项的库被直接复制后，仍默认可见且可安装，不需要 `runtime-relocate` | 与文档"复制 catalog 不保留资格"的表述不一致；不继承执行事实，包字节仍校验，影响限于不变量/文档 | 已证明 |
| A4 | LOW | `store.py:127-159`（journal 在 staging 之后写入）、`store.py:266-343` | 硬杀在 journal 前留下孤儿 `.transactions/<id>/new-*`；`adopt` 期间硬杀留下孤儿 `evidence/…/<uuid>`、`runtime/…/<uuid>`；`recover` 只处理 journal 内阶段 | 仅存储泄漏，未被 catalog 引用，不可安装 | 已证明 |
| A5 | LOW | `store.py:189-190`、`store.py:225` | `reconcile` 对已带 `invalidated` 的项 `continue`，而 `entries()` 只按 `zone == "accepted"` 过滤；外部手写 catalog 可造出 accepted+invalidated 项并被列出 | 安装仍双重把关（`store.py:367-369`），不构成安装绕过 | 已证明（需外部改写前提） |
| A6 | LOW | `store.py:239`、`store.py:349` | `active = {e["name"]: e}` 再 `list(...)`，同名项在下一次 adopt 时被静默合并掉一个 | 需手写/重复 catalog 前提；包与证据变成孤儿 | 已证明 |
| A7 | LOW | `store.py:370-384`、`artifacts/package.py:73-90` | 安装直接 `copytree` 到目标，无 staging+rename；中途被杀死留下半成品目录，重试因"目标已存在"失败；`install_envelope` 拒绝已存在 envelope，而调用方回滚只删 `target`，留下 `destination/.runtime/<name>` 需手工清 | 崩溃后需手工清理才能重装 | 已证明 |

A 组确认成立的关键不变量（决定性行号）：

- **不存在"信任存储的成功标记"**：`contracts.py:131` 只写不读；判定处一律重算（`store.py:368`、`service.py:167`、`recovery.py:183`、`package.py:68`、`store.py:248`）；伪造 pass 布尔会被拒（`tests/pipeline/test_delivery_protocol.py:220-227`）。
- **默认只看 accepted**：`store.py:225,228-232`、`cli.py:48,131`；真实证据 `validation/final-continuation/first-lifecycle/{default-query.log,migrated-before-query.log}` 显示迁移前 `{"skills": []}`、默认查询有 accepted 项。
- **安装双重把关**：`store.py:363-369`（zone + 现算资格）与 `package.py:61-70`；旧格式输出被拒（`package.py:27-29`）。
- **草稿永不获资格**：`contracts.py:88-89`。
- **required 交付要活体 Docker 证据 + 原始结果复核 + 引擎身份**：`contracts.py:96-112`、`execution.py:148-220`。
- **冻结身份是 hash 链**：`contracts.py:80-83`、`evidence.py:62-94`（freeze manifest 排除自身，自身 hash 存在 catalog）。
- **四种状态分字段**：`delivery.execution.status`、`delivery.host.status`、条目级 `runtime`/`current_execution`、时间戳 `current_host`（`contracts.py:15-16,127-128`、`service.py:43-52`、`store.py:325-328`）。
- **事务**：lock → journal → 分阶段 rename → catalog 最后原子写（`store.py:111-159`）；rollback/`recover` 幂等（`store.py:41-60`）。
- **迁移先撤销再重推**：`recovery.py:169-196`；漂移在变更前就失败（`store.py:178-179`）。
- **导入不继承执行资格**（required）：`recovery.py:54,76-79` + `store.py:180-181`。
- **无旧路径依赖**：`paths.py:4-6` 仅 ROOT 相对默认值；所有运行期读取都经 `safe_relative`（`records.py:57-74`）与 `contracts.py:145-148` 的不相交检查。

### 3.2 入口绑定、Markdown、冻结断言（审查 B）

| # | 严重度 | 位置 | 问题 | 状态 |
| --- | --- | --- | --- | --- |
| B1 | high | `runtime/planner.py:578-582`、`runtime/execution.py:20-29,110-118`、`local.py:110-118,177-192`、`runner.py:211-237` | 只校验"被声明的文件"与镜像内字节，未绑定"真正执行它的解释器"；`entrypoint[0]="python"` 由 PATH 解析，`RUN` 步骤可替换 `/usr/local/bin/python` 或塞 `sitecustomize`，文件哈希仍全部匹配 | 已证明；利用需实测 |
| B2 | high | `pipeline.py:367-385` | "较新独立审阅约束旧计划"只在一种形状下生效：传了 `--library-dir`、catalog 存在、条目在 `candidates`、freeze 内含 `runtime/association/independent-review.json`、且 files 与 sources 完全相等；否则直接复用已保存计划、**零次作者调用**。其他位置的拒绝（`runtime/independent-contract-review.json`、`runtime_diagnosis`、别的库、任何文件变化）都被忽略 | 已证明 |
| B3 | medium | `preparation.py:91,240-243`、`service.py:217-218` | 冻结断言比对只在 `locked_cases is not None` 且非空时执行；从未拿到有效用例集的交付，恢复时**不比对**，并重写 `locked-tests.json` 与 acceptance payload | 已证明 |
| B4 | medium | `preparation.py:248-249`、`entry.py:194`、`service.py:243-256,268` | 审阅证据没有与它批准的 plan 绑定（只写入 materials、`review_sha256` 从不回读）；`--oracle-correction` 路径不套用 `diagnosis.py` 的字段白名单/负例保护，一条 `oracle_changes_verified=true` 的模型审阅就能改任意保留断言的取值、容差与 allowed-values 基数 | 已证明 |
| B5 | medium | `entry.py:83-89` | 入口类型选择：包内**恰好一个** `.py/.sh` 就直接绑定脚本、从不调用 `markdown_entry`，于是含 SKILL.md python 块 + 一个辅助脚本的包绕过全部 Markdown 规则（唯一性/完整性/缩进/上下文）；两个以上脚本且无块则 `entry_ambiguous`（fail-closed） | 已证明；无测试覆盖 `preflight` |
| B6 | medium | `entry.py:179`、`preparation.py:226-227` | `binding['invocation']` 只要求非空，之后只作为约束文本传给 planner，从不解析、不与 plan 的 entrypoint/args/cwd/outputs 比对，也不进 locked tests | 已证明 |
| B7 | medium | `preparation.py:213,233` | 调用方自带 plan 时把 `index["read_files"] = list(index["files"])`，使"未读来源"规则与 `acceptance.grounded` 的读取前提失效；可从普通 JSON 配置（`models.py:57-64`）与 `runtime-prepare --spec` 触发 | 已证明 |
| B8 | low | `entry.py:62-74` | 交互/动态代码拒绝只按 AST 裸名匹配 `input/breakpoint/exec/eval`；`f=eval; f(...)`、`__builtins__[...]`、`__import__` 可绕过；`globals/locals` 在白名单内 | 已证明（规则不完整，非安全边界） |
| B9 | low | `preparation.py:239-241`、`planner.py:638-642,670-673`、`coverage.py:112`、`execution.py:124` | 映射检查在 `validate_plan` 之后追加，不参与重名检查；同名 plan 测试可覆盖 `check-<origin>-<name>`，`by_name` 后者胜，逐用例产物目录按名称哈希共享 | 已证明；影响待实测 |
| B10 | low | `preparation.py:261-272,265` | 受阻修复仍返回 materials 路径、调用方无条件 seal+execute；rebind 丢掉上一个环境 plan，工作用 plan 只留在历史里（执行在 Docker 前即被拦住） | 已证明，无断言违规 |

B 组确认成立：单块提取按计数与字面围栏判定（`entry.py:33-36,39-53`），偏移量与指纹记录（`entry.py:75-80`）并在每次物化/输入检查时复核（`entry.py:104-122`、`local.py:81-83`、`execution.py:44-46`）；交付文件与镜像字节双向核对（`evidence.py:36-39`、`local.py:189-192`、`execution.py:20-29,204-212`）；三种身份分离有代码与测试（`intake.py:110-114,134-137,184-188`、`contracts.py:29-32`、`test_markdown_entry.py:174-202`），但**"文档正文不得混淆"只靠模型审阅，无程序校验**；manifest 逐条比 path+sha256+bytes（`evidence.py:62-92`），唯一缺陷是 `manifest()` 按 `Path` 对象排序（`package.py:18`）导致 POSIX→Windows 会**fail-closed**（报错/失效/拒绝安装），不会静默通过。

### 3.3 进程监督、脱敏、失败分类、环境计划（审查 C）

| # | 严重度 | 位置 | 问题 | 状态 |
| --- | --- | --- | --- | --- |
| C1 | high | `agent/backend.py:113,161,186,263` | Native 轮次把 CLI stderr **原样**写盘（`stderr=stderr` 直接给 Popen），`prompt.txt` 与 `result.json` 也不脱敏；`model_call` 路径是脱敏的（`model_call.py:140`），两条路径保证不一致 | 写入点已证明；实际敏感行待实测 |
| C2 | high | `model_call.py:319`、`records.py:33-43` | 错误文本内嵌 `proc.stderr[-600:]` 原文，而 `redact()` 不匹配 `authorization="Bearer …"`（引号处失配）、`cookie=`、`?token=`、无标签 JWT，且被 600 字符切开的 token 会失去前缀特征 | 正则缺口已证明；泄漏待实测 |
| C3 | high | `model_call.py:293-297` | 生产 `call()` 从不传 `stderr_filter`，所以 `test_model_wait_stage.py:41-62` 证明的"固定类别投影"只存在于测试与 `validation/*/controlled_call.py`，**没有保护任何真实审计目录** | 已证明 |
| C4 | high | `planner.py:55,71-72` 全仓库仅此三处 | `pin_base_image` 是空开关：基础镜像只是可变 tag，`docker build` 无 `--pull/--no-cache`（`local.py:158-166`），只记录**构建产物**的 RepoDigests，从不记录基础镜像 digest | 代码已证明；漂移后果待实测 |
| C5 | high | `preparation.py:261-268`、`entry.py:185`、`review.py:50` | 关联阶段审阅里的 agent 传输失败/停滞不被 `review()` 捕获，落到 `prepare()` 的通用分支，记成 `code=plan_unresolved`、`blocker_kind=unresolved_input`、`repair_lane=environment` —— **传输失败被报成计划/输入缺陷** | 已证明 |
| C6 | medium | `planner.py:152-153,590` vs `preparation.py:142-151` | 模型声明的依赖 `version/channel` 既不渲染进 Dockerfile，也不与 `steps` 交叉校验，版本钉住完全取决于模型写的 shell 文本 | 已证明 |
| C7 | medium | `backend.py:269-270` vs `model_call.py:263-270`、`pipeline.py:181-182` | 同一症状（静默/停滞）在 planner 路径是 `model_stalled`/`model_transport`，在 agent 路径是 `BudgetError`（caller_limit），而 `BudgetError` 让记录变 `incomplete`、`ModelCallError` 让记录变 `failed` | 已证明 |
| C8 | medium | `planner.py:455-464`（只捕 `ModelExecutionError, OSError`） | 契约类缺陷（工具事件、答案不是 JSON）抛的 `ValueError` 未被包装，同样落到 `plan_unresolved`/`unresolved_input`/`environment` | 已证明 |
| C9 | medium | `process_stats.py:34-35,83-84`、`model_call.py:205-212`、`backend.py:23-32` | 计数器仅 Windows 可用：POSIX 上入站增长永远不算进度（看门狗退化为只看 stdout）；`activity_total()` 含 CPU 时间，纯 CPU 空转的静默子进程在 agent 侧永远"有活动" | 已证明 |
| C10 | medium | `model_call.py:118,205-212` | 入站进度阈值是"每个探针窗口 ≥4096 字节"（240 秒限额下 ≈2 KiB/s），健康的慢速流可能低于该门槛而在 240 秒被判 `model_stalled`，尽管外层 600 秒预算远未用完 | 待实测（取决于 CLI 的 TCP 读取粒度） |
| C11 | medium | `model_call.py:235-240,242-243`、`validation/runtime.py:28` | `job.close(); proc.wait(timeout=5)` 与 `terminate_tree` 末尾的 `proc.wait(timeout=5)` 未加保护：超时会抛 `TimeoutExpired`，覆盖原本的 `ModelExecutionError`，不被 `planner.py:459`/`preparation.py:261` 捕获，最终表现为构建级 "failed"；且名义超时最多可超出约 20 秒 | 已证明（控制流） |
| C12 | medium | `backend.py:213,304-311` | observe-only 确实不会终止，但：`progress_observation` 只在 `finally` 写，**hang 住时没有静默证据**；`model_timeout`/`total_seconds` 同为 null 时 `timeout=inf`，静默不退出的子进程会被无限等待；`counters_grew` 接受 CPU 变化，`process_activity_seen` 可能为真而零入站字节 | 已证明 |
| C13–C19 | low | 见下 | 敌意 MCP 名 `ValueError` 被归成 `plan_unresolved`；under-development 提示被算作 tool event 且 native 路径无法抑制（`--ignore-user-config` 挡住了 `suppress_unstable_features_warning`）；`respect_system_proxy` 效果未验证而警告被抑制；`--disable shell_tool` 可能不覆盖 `unified_exec`；`terminate_tree` 用 PATH 解析 `taskkill`（`runner.py:77-80` 已用绝对路径）；审计目录保留完整 prompt/答案正文；`events.json` 每行重写一遍（O(n²)） | 已证明/待实测 |

C 组确认成立：隔离保留 provider/auth 且从不读凭据（`model_call.py:41-61`，`test_model_call.py:16-30`）；观测到的设置字典无密；敌意 MCP 名被拒（fail-closed）；钉住的 CLI 接受全部参数（含 `--enable respect_system_proxy`、`--disable shell_tool`，见 `call-20261026T150937Z-https/model-0/{request,process}.json` 的 returncode 0）；看门狗被外层预算截断；**不存在把部分读取当成功**的路径（`model_call.py:245-246,260-273,305-322`）；启动失败/取消/后代回收均有持久记录；过滤在捕获与落盘之前；内容/环境/传输三条通道分开；冻结计划在构建前后都复核；同一冻结计划的 Dockerfile 渲染确定（排序复制清单、无时间戳）。

## 4. 本轮已修的缺陷

| 编号 | 修法 | 测试 |
| --- | --- | --- |
| A1 | `release_dead_lock` 区分三种锁内容：可解析且存活 → 拒绝；空内容或不可解析 → 只有超过 5 秒获取窗口才归档，窗口内报 "being acquired by another process; retry shortly"；归档统一走 `_archive_lock` 并保留为 `lock-recoveries/*.txt` | `test_ownerless_lock_is_only_dead_after_the_acquisition_window` |
| C2 | `redact()` 补齐 `authorization="Bearer …"`（带引号）、`cookie=`、`?token=`/`&sig=`、无标签 JWT | `test_review_fixes.RedactionTests`（6 种样例 + 普通文本不变） |
| C3 | 生产 `model_call.call()` 现在总是传 `stderr_filter=redact`；错误消息里的 `stderr[-600:]` 也强制 `redact` | 同上；`test_model_wait_stage` 既有用例 |
| C1 | agent 轮次 `stderr.log` 经 `RedactingLog` 逐行脱敏，`prompt.txt` 落盘前 `redact` | `test_native` 全量 |
| C7 | agent 停滞改为 `AgentStalled(code='model_stalled', kind='model_transport')`，映射成带 code 的 `ModelCallError`，不再伪装成 `BudgetError` | `test_stall_is_a_transport_fault_not_a_budget_stop` + 更新后的原生停滞用例 |
| C8 | 契约违规（工具事件/答案非 JSON）抛 `ModelOutputInvalid(code='model_output_invalid')`，不再落成 `plan_unresolved` | `test_model_call` 既有用例；planner 捕获新类型 |
| C13 | 隔离配置不可读/不可解析/敌意 MCP 名 → `ModelConfigError(code='model_config_invalid')` | `test_mcp_isolation_refusal_is_typed` |
| C11 | 清理阶段 `proc.wait(5)` / `terminate_tree` 的 `TimeoutExpired` 不再覆盖原判据，只记 `cleanup_wait_expired` | `test_model_call`、`test_model_wait_stage` 全量 |
| C4（部分） | `pin_base_image=True` 由“静默忽略”改为**显式拒绝**（`PlanningError: not implemented`），避免假保证 | `test_unimplemented_pin_flag_is_refused_instead_of_ignored` |
| A2 | 查询时的**暂态**主机不可用不再永久降级：accepted 保留、写 `current_qualification.deferred` 与 `current_host`，主机恢复后下次查询自动清除 deferral；真实漂移仍按原规则降级 | `test_review_fixes.TransientHostDeferralTests`（3 例：宕机保留、漂移降级、恢复清除） |
| B5 | 入口选择改为**明确候选优先、歧义拒绝**：Markdown 块与脚本同时存在 → `entry_ambiguous`；两个以上脚本 → `entry_ambiguous`；仅当 Markdown 块不可用时才绑脚本，并记录 `markdown_candidate_rejected`；无脚本且块不支持时保留原 `entry_unsupported`/`unsupported_contract` 判定 | `test_review_fixes.EntrySelectionTests`（6 例） |

**未修（明确列为相关功能验收前置，不进本轮结论）**：B1 解释器绑定、B2 旧计划撤销检查、B3 空 `locked_cases`、B4 契约修正保护、B6 `invocation` 交叉校验、B7 自带 plan 的读取前提、C5 关联阶段分类细化、C6 依赖版本渲染、C9 POSIX 进度通道、C10 4096 字节阈值、C12 运行中静默证据、C4 的基础镜像 digest 记录。基础镜像 digest 与解释器保证按“明确支持范围”另做，不在本轮宣称。

## 5. 证据地图（机制测试 vs 真实证据）

| 能力 | 机制测试 | 真实证据 | 缺口 |
| --- | --- | --- | --- |
| accepted/candidates 分离与默认过滤 | `test_delivery_protocol.py:88-101,308-320` | `validation/final-continuation/first-lifecycle/{default-query.log,migrated-before-query.log}`、`final-acceptance/copy-default-query.log`、`stage3/rdkit-library/catalog.json` | — |
| 未合格/候选安装被拒 | `test_delivery_protocol.py:94-101,322-327` | `final-acceptance/copy-install-rejected.log`、`final-continuation/final-candidate-install-rejected.log` | — |
| 内容/来源/契约漂移撤销资格 | `test_delivery_protocol.py:141-162`、`test_runtime_recovery.py:37-47` | `stage3/recovery-results.json`、`stage4/results.json` | 撤销不写 `history`，只有单槽 `runtime_invalidated` |
| 四种执行状态区分 | `test_runtime_execution.py:89-92,133-146` | `stage2/build-failure-library/catalog.json`（build_failed）、`stage3/rdkit-library/catalog.json`（execution_failed vs passed）、`final-acceptance/copy-current-validation.log`（runtime_blocked） | — |
| 事务/回滚 | `test_delivery_protocol.py:229-249,266-280`、`test_runtime_recovery.py:191-231`、`test_skill_library.py:111-120` | 崩溃/断电证据**缺失**（文档已声明不宣称） | A4（孤儿 staging） |
| 锁恢复 | `test_runtime_recovery.py:84-91` + 本轮新增用例 | `stage4/initial-windows-lock-diagnostic.log` | 0 字节锁用例此前缺失，本轮补上 |
| 迁移撤销 + 重验 | `test_runtime_recovery.py:49-64,133-141` | `final-acceptance/copy-relocate.log`、`stage4/results.json` | A3：`not_required` 不触发守卫 |
| 导入不继承执行资格 | `test_runtime_recovery.py:143-171` | `stage4/import-results.json`（`source_removed: true`）、`stage4/imported-library/catalog.json` | — |
| 引擎/主机变化不得继承 | `test_runtime_recovery.py:122-131` | **第二台主机证据缺失**（`final-acceptance.md:90`、`final-continuation.md:68` 自认未测） | 需实测或明确列为不支持 |
| 只读交付无需 Docker | `test_delivery_protocol.py:60-68` | 真实的 accepted 只读 catalog **缺失** | 与 A3 同源 |
| Markdown 单块提取与指纹 | `test_markdown_entry.py:47-58,60-68,74-80` | `validation/markdown-entry/`（含真实字节位置与指纹） | B5：只有一个辅助脚本时不检查 Markdown |
| 交付文件与镜像字节一致 | `test_runtime_build.py:203-211,244-249,308-315` | `validation/markdown-entry`、`final-single-retry` | B1：解释器绑定 |
| 冻结断言不可改写（有 locked_cases 时） | `test_runtime_build.py:193-201`、`test_runtime_execution.py:94-131` | `markdown-entry`、`final-single-retry` | B3：空 locked_cases 路径无覆盖 |
| 模型传输失败分类 | `test_model_call.py`、`test_model_wait_stage.py`、`test_runtime_build.py:100-110,121-133` | `validation/timeout-deep-debug/call-*` | C5：关联审阅阶段的传输失败未被分类 |

## 6. 结论与最小剩余工作

**本轮结论：任务一完成，未发现会阻止任务二开跑的阻断项；但存在需要在结论中限定范围的已证明缺陷。**

- 阻断项：无。资格过滤、默认视图、安装双重把关、事务、迁移撤销、导入不继承都已核实，且不存在"信任存储成功标记"的路径。
- 需要在验收结论里显式限定的已证明缺陷：
  1. **B1 解释器绑定**：镜像校验保证"声明文件字节正确"，不保证"该文件被那个解释器执行"。首版若不修，报告只能声明到文件完整性层面。
  2. **B2 旧计划复用**：`build --plan` 在"审阅与库形状不匹配"时零作者调用复用旧计划；本轮正常新创建不走该路径，但恢复能力的宣传必须按此收窄。
  3. **B3 空 `locked_cases`**：未拿到有效用例集的交付在恢复时无冻结比对；任务二若一次成功并直接拿到用例集，则不受影响。
  4. **C4 `pin_base_image` 空开关**：不得宣称基础镜像被钉住；报告只能给"实际使用的基础镜像 tag + 构建产物 digest"。
  5. **C5 关联阶段传输失败误分类**：若任务二在关联阶段遇到传输失败，会显示成 `plan_unresolved`，需要人工按 transport 解释，不能当成计划缺陷。
- 建议在任务二之前决定（都需要改已确认政策，未擅自改）：
  1. 是否修 C1/C2/C3（脱敏一致性）：至少让 agent 路径与 `model_call` 路径的脱敏保证一致。
  2. 是否修 B5（入口类型优先级）：改为"存在唯一合法 Markdown 块时优先 Markdown"，会影响既有脚本型交付的行为。
  3. 是否修 C7/C8（把契约缺陷与传输缺陷彻底分开）与 C5（关联阶段分类）。
  4. 是否把 A2（查询会因瞬时 Docker 不可用而永久降级）在任务二之前处理，或至少在跑 `library` 查询前确认 Docker 引擎在运行。
- 任务二开跑前的硬前置：`codex doctor` 的 `provider_reachability` 需为 `ok`（当前 fail/fail/ok 抖动，直连单请求 12.3 秒 vs 代理 1.6 秒）；Docker 引擎需在运行；真实模型调用按批次单独授权（每批最多 3 次）。
