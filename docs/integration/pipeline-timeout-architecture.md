# Pipeline 超时：机理验证、架构缺陷与修复（2026-10-26 第二轮）

本轮起点 `5d3be31`，工作区含上一轮未提交的计数/预算修复与测试。用户本轮明确授权：最多 3 次串行真实调用、允许在 `model_call.run` 加仪表与默认 240 秒进度看门狗、允许把传输切到 HTTP/SSE 作为对照、Docker 业务验收另开一轮。

## 1. 结论（按确定性分级）

1. **已证明（本地可复现，无需真实模型）**：CLI 在 Responses-over-WebSocket 模式下的“流空闲超时”是**每收到一条 WS 文本帧就重置一次**的计时器，因此任何持续到达的文本帧（包括 CLI 无法解析、或与生成进度无关的帧）都会让一个真正停滞的采样请求**永远等不到超时**。HTTP/SSE 模式下同样的保活注释**不会**抑制超时，WebSocket 的 Ping/Pong **不会**抑制超时。证据见第 3 节矩阵。
2. **已证明（本轮真实调用）**：真实请求以 `workspace routing discovery timed out` 失败：WebSocket 侧连发 5 次重试 → 自动回退 HTTPS → 再 5 次重试 → `turn.failed`，全程 220.3 秒，进程退出码 1。即：**当前这台机器到 Codex 后端的连接根本建立不起来**，不是本地管道、不是 schema、不是业务代码。
3. **已定位（本机环境，非本仓库代码）**：`codex doctor --json` 报 `network.provider_reachability=fail`（ChatGPT 推理地址请求超时）、`network.websocket_reachability=warning`（握手超时，连接超时 15000ms）。直连 443 到 `chatgpt.com`/`api.openai.com` 均不通；经本机 Clash Verge 代理（`127.0.0.1:7897`）同一地址返回 401（可达）。Clash Verge 当时 `enable_system_proxy: true`、`enable_tun_mode: null`，**没有 TUN 适配器**，也没有默认路由进 TUN。CLI 的 `respect_system_proxy` 是“under development / false”的实验特性，默认不读 Windows 系统代理。历史成功调用（101.8 秒、100.8 秒）能直连后端，说明当时存在透明路由（TUN/VPN）；调用 #1 时没有。用户随后开启 TUN，`doctor` 的两项立即变 `ok`，#2、#3 都完成了传输。
4. **仍属推断（有证据但未直接观测）**：历史那几次 600 秒“完全静默”的失败，最可能是“WS 已连上、请求已发出、后端不再产生可用的采样进度，但仍有帧到达（路由/元数据/保活）”，于是 CLI 的自带超时永远不触发，只有外层 600 秒墙钟兜底。这个推断和全部历史事实相容（无 idle 日志、无 retry、models 请求仍 200、stdout 只有 2 条事件），但没有远端追踪，无法证明当时确实有帧到达。
5. **不是原因（本轮进一步排除或降级）**：污染 schema 作为唯一原因、stdin 未关闭、Python 双向管道死锁、必需并行争用、Ping/Pong 重置 idle、模型列表刷新阻塞主请求。另见第 5 节里“历史上看不到重试”的两个可解释原因。

## 2. 本轮真实调用（三次授权全部用完）

目录：`validation/timeout-deep-debug/call-*/`。固定 prompt（41695B，SHA-256 `8af7e441…0bc9d9`）、修复后 schema（`cbadd6d5…f1ea4`）、同一 CLI 二进制（`1103e9e0…58a098`）、`gpt-6-astra`/medium/default，外层 600 秒、进度看门狗 240 秒。

| # | 时刻 (UTC) | 传输 | 结果 | 关键事实 |
| --- | --- | --- | --- | --- |
| 1 | 14:47:39 | WebSocket | 220.3 秒失败 | 无任何 WS 连接日志；5 次 WS 重试→回退 HTTPS→5 次重试；`workspace routing discovery timed out`。当时 `codex doctor` 报 provider 不可达 |
| 2 | 15:09:37 | HTTP/SSE | **成功，149.8 秒** | 有效计划，jsonschema + `preparation.validate` 通过，6 个用例；stdout 在 5.4 秒后静默 134 秒才出答案 |
| 3 | 15:12:10 | WebSocket | 传输成功，语义被拒 | 150.8 秒退出码 0，schema 合法，但 `preparation.validate` 拒绝：`Outcome assertion role must match the promised purpose: completion` |

三次调用共用同一份固定输入，唯一变量是传输与该时刻的网络状态。结论：**网络恢复后两种传输都能完成**；#1 的失败是网络路径，不是传输协议本身；#3 的失败是模型给出的计划语义不合格（**不是超时、不是 JSON、不是传输**），也不能据此判定 WS 更差（各一次）。

### #1（WebSocket，网络中断时）时间线

| 时刻（秒） | 事件 |
| ---: | --- |
| 0.52 | `thread.started` |
| 5.55 | `model_catalog_refresh_failed`（ERROR，/models 刷新失败） |
| 15.55 | `turn.started`（历史成功约 1.3 秒；本次启动明显更慢） |
| 35.8 / 51.0 / 66.5 / 82.2 / 99.0 | 采样流重试决策 1–5（WARN `codex_core::responses_retry`，`retry.layer=stream`） |
| 116.9 | `item.completed{item.type=error}`：`Falling back from WebSockets to HTTPS transport. workspace routing discovery timed out` |
| 132.1 / 147.3 / 162.8 / 178.5 / 195.2 | HTTPS 侧重试 1–5 |
| 213.2 | 终止错误 `workspace routing discovery timed out` → `turn.failed`，退出码 1 |

关键事实：

- 全程**没有任何 `websocket_connect_start/success` 日志**，每次尝试约 15.2–16.8 秒结束，正好等于 `websocket_connect_timeout_ms = 15000`。即连接从未建立。
- `stdout` 里 14 条事件中有 9 条是 `Reconnecting... N/5`：**release 构建会刻意隐藏第一次重试提示**（`retry_count > 1 || debug_assertions`），所以“只看到 2 条 stdout 事件”不能证明没有重试过。
- 进程读数在收尾时 `read_bytes_last_interval = 0`：最后 2 秒没有任何读 I/O，与“连不上”一致。
- 本次失败**不是**历史那种静默 600 秒，而是明确的连接失败链。两者是同一上层原因（到后端的路径）在不同网络状态下的两种表现。

### #3（WebSocket，网络恢复后）

`thread.started` 0.33 秒 → 第一次 `websocket_connect_start` 10.19 秒 → 第二次 20.40 秒 → `websocket_connect_success` 28.88 秒（连接建立花了约 18.5 秒，接近 15 秒连接超时上限并重试一次）→ 主发送 28.88 秒 → 答案 141.42 秒 → `turn.completed` 141.48 秒 → 退出码 0。全程无重试决策。stdout 静默 131 秒，未触达 240 秒看门狗。

## 3. 决定性本地实验：谁能发现停滞？

脚本 `validation/timeout-deep-debug/probe_transport.py`（同一 CLI 二进制 + 本机回环服务器，`stream_idle_timeout_ms=1000`、`stream_max_retries=2`，每个场景最多 9 秒），结果目录 `probe-20261026T143013Z/`：

| 场景 | 对端行为 | CLI 自带 idle 超时 | 主请求发送次数 | 结果 |
| --- | --- | ---: | ---: | --- |
| `ws_silence` | 收下请求后完全静默 | 6 | 4 | 重试到上限后 `turn.failed`，随后回退 HTTPS |
| `ws_ping_only` | 只发 WebSocket Ping（每 0.25 秒） | 6 | 4 | 同上：Ping 不抑制超时 |
| `ws_unknown_text` | 每 0.25 秒发一条无意义文本帧 `{"type":"nonexistent.event"}` | **0** | **1** | **9 秒时仍挂着**，只能外部杀掉 |
| `sse_silence` | HTTP/SSE 挂起不回事件 | 8 | 0（SSE 无 WS 请求） | 重试后 `turn.failed` |
| `sse_comment_keepalive` | 每 0.25 秒发 `: keepalive` 注释 | 8 | 0 | 仍然超时：SSE 注释不抑制超时 |

代码依据（`rust-v0.164.0-alpha.11.1`）：`codex-api/src/endpoint/responses_websocket.rs` 中 `tokio::time::timeout(idle_timeout, ws_stream.next())` 包的是**单条消息**；`WsStream` 的 pump 只把 Text/Binary/Close/Frame 转给上层，Ping/Pong 在 pump 里就被消费（所以不重置），任何 Text 都会重置计时器。SSE 侧 `codex-api/src/sse/responses.rs` 同样按单事件计时，但 eventsource 解码器不会把注释当事件，因此保活注释不重置。另外 `session_telemetry.rs::record_websocket_event` **只写 metrics，不写任何级别的日志**，所以“日志里没有入站帧”从来不能证明“线上没有帧”。

## 4. 已实施的修复（本轮，本地提交）

1. `creation_pipeline/runtime/model_call.py`
   - 新增应用级进度看门狗：进度由两类信号构成——stdout 生命周期事件，或**真实入站字节增长**（2 秒采样窗口内 `read_bytes` 增长 ≥4KB 视为对端仍在发送，避免把“长静默但仍在流式生成”误判为停滞）。`progress_timeout` 默认 240 秒，且被外层总超时截断（`min(progress_timeout, timeout)`）；到点后 `status='stalled'`、写 `stall.json`、抛 `ModelExecutionError(code='model_stalled', kind='model_transport')`。这样“不明静默”最多花 4 分钟且带证据，而不是 10 分钟且只有 `timed_out`。
   - 新增 OS 级累计读数采样（`creation_pipeline/runtime/process_stats.py`，ctypes，无新依赖）：`read/write/other` 字节、读写操作数、CPU 时间，落在 `process.json` 的 `process_counters` / `process_counter_timeline`。只记录聚合计数，不记录任何载荷。实测两种传输期间 `read_bytes` 分别增长约 71–89MB，说明该信号可用；单次 2 秒窗口内为 0 即“对端没有再发东西”。
   - Windows 子进程加 `--enable respect_system_proxy`（用户批准），避免“机器只能通过本地代理上网、CLI 却直连”的静默失败；该特性在本版本标为 under development，效果需以真实调用复核，TUN 仍是已验证路径。
2. `creation_pipeline/runtime/planner.py`：`progress_timeout` 进入 `DEFAULTS`/`options()` 校验并可显式置 null 关闭；`plan()` 把该预算传给模型调用；传输性失败保留 `code`（例如 `model_stalled`），不再一律折叠成 `model_unavailable`。
3. `creation_pipeline/agent/backend.py`：NativeSession 现在也能做同样的停滞判定，但**默认关闭**，通过 `limits.agent_progress_timeout` 开启。原因：agent 轮次允许长时间静默的工具执行（例如长构建），单看 stdout 静默会误杀；开启后“新增 stdout 行”或“进程累计计数变化”才算活着，只有两者都停住才判定停滞。
4. `creation_pipeline/pipeline.py`：`summary/返回值 model_calls` 改为**本轮切片**（恢复构建不再把上一轮的调用算进来），`model_metrics.receipts` 仍保留完整会话轨迹（恢复审计需要）。
5. 上一轮未提交的修复一并保留：`preparation.py` 以“获准尝试次数”计数（含关联与失败传输，guard 拒绝不计数）；`planner` 在发送前重新核验剩余预算，不再把 0.25 秒扩成 1 秒；`ModelUnavailable`/`ModelExecutionError` 带 `code`/`kind` 元数据；`test_native` 的故障注入限定到模拟 CLI。

测试：`tests/pipeline/test_model_call.py` 新增 5 项（停滞分类、进度重置、看门狗不越过总超时、关闭看门狗、计数器且不含 prompt 载荷），`tests/pipeline/test_runtime_build.py` 新增 3 项（停滞不被当作无效计划、planner 传递看门狗预算、选项校验）。相关三模块 46 项全通过；全量 281 项中 2 项失败，均为**本轮之前就存在**的失败（见 5.6），已在干净 worktree 上复核。

## 5. Pipeline 架构缺陷清单

标“本轮已修”的只包含 4 节所述改动；其余为记录，未经用户批准不改变行为。

### P0

**5.1 唯一可靠的停滞保护是外层墙钟，CLI 自带超时不可依赖（本轮已修）。** 见第 3 节。现在停滞会在 240 秒内以可区分状态和证据结束；真实入站字节增长不会触发判定。仍未解决的是“卡死为什么发生”，属于服务端/链路侧：本轮 #1 已证明网络中断时命令会以连接超时结束，而历史那种“已连上、无进度、无日志”的情形仍需远端追踪才能定性。

**5.2 超时与传输失败长期被归类成“输入问题”。** `preparation.prepare` 的 gap 直接取异常的 `code`/`kind`；修复前 `ModelUnavailable` 与关联阶段抛出的 `ModelExecutionError` 没有类别字段，于是超时落进 `plan_unresolved`/`unresolved_input`，看起来像“计划有问题”。本轮补齐 `code`/`kind` 与关联阶段的计数，但**分类法仍是字符串约定**，没有集中定义，新增异常很容易再退化。

### P1

**5.3 两套并行的进程监督实现。** `runtime/model_call.py:run`（planner/关联/诊断）与 `agent/backend.py:stage`（发现/撰写/审阅）各自维护线程、队列、超时与清理逻辑。本轮只给前者加了看门狗，后者仍然是“到总超时为止”。同样的静默停滞在 agent 阶段依旧会耗尽 `model_timeout`。建议：抽出共享监督器，统一“完整答案＋成功终止事件＋正常退出＋完整 I/O＋有进度”的判据。涉及两处成功语义，属关键决策。

**5.4 传输配置语义分散且不可回读。** `model_call.isolated_options()` 保留用户 provider/reasoning/tier 配置并禁用工具，`agent/backend.py` 用 `ignore-user-config` 的 `NativeSession`，`http_only` 只作用于后者。没有一处保存“本次调用生效的模型/传输/超时”快照，排查只能靠重建。本轮的 `process_counters`/`request.json` 是局部补偿。建议显式 `ModelCallPolicy` + 脱敏有效配置回读。

**5.5 planner 单次生成承担过多职责。** `planner.py` 的 `PLAN_SCHEMA` 把安装步骤、依赖、资源、构建布局、用例、来源引用、入口关联与验收规则塞进一次结构化生成；`acceptance_json`/`case_json` 还是**嵌套 JSON 字符串**（模型要二次转义），成功样本 `input 24991 / output 3033` tokens、答案 12.5KB。这既放大尾延迟，也让“计划格式错误”与“传输失败”纠缠。建议拆成“资料请求／安装计划／验收提案”三个可分别校验和持久化的阶段，最后仍跑完整验证器，不降低任何锁定约束。

**5.6 `summary.model_calls` 在恢复构建上是累计值，与测试和直觉不符（本轮已修）。** 原实现 `pipeline.py:559` 用 `len(session.receipts)`（会话累计），而 `record["model_calls"]`（第 199 行）是本轮切片，于是恢复构建的 summary 把上一轮调用也算进来。本轮按用户决定改为本轮切片，`model_metrics.receipts` 保持完整轨迹。同时发现 `tests/pipeline/test_discovery.py` 两项断言（`2`、`4`）在干净 HEAD 上就失败：这两个构建实际发生 3 次和 5 次模型调用，多出来的是 **runtime planning（planner）调用现在也计入 session receipts**，测试期望值当时未同步。已按实际行为更正并注明原因。

**5.6b 计划语义不合格与超时混在同一失败通道。** 调用 #3 说明这是常态而非偶发：同一固定 prompt、schema 合法的答案，被 `preparation.validate` 以 `Outcome assertion role must match the promised purpose: completion` 拒绝。这类失败应当（现在也确实）归类为计划缺陷而非传输问题，但对外仍然只是 `status=blocked` 加一条 gap 文本，缺少“模型产出不稳定”的统计口径。建议按失败类别聚合，而不是逐次人工判读。

### P2

**5.7 材料读取默认无预算。** `planner.DEFAULTS` 的 `context_chars`/`max_files`/`max_file_bytes` 默认 `None`，首次 `inventory`/`supply` 会读并哈希全部可读文本，大仓库会同步放大内存与 prompt；`context_chars` 超限才报错，没有分块或按需读取。

**5.8 每个 stdout 事件都重写整个 `events.json`。** `model_call.run` 的 pump 在审计目录里对每条事件重写全量数组，输出多或磁盘慢时形成额外背压（历史失败只有 2–14 条事件，不构成已知原因）。建议追加式日志＋有界摘要，审计失败要显式失败而不是丢数据。

**5.9 Windows 没有代理处理，只有 macOS 有。** `runtime/network.py::model_environment()` 仅在 `sys.platform == 'darwin'` 时读取系统代理；Windows 侧完全依赖 CLI 的 `respect_system_proxy`（实验特性、默认关闭）或透明路由。今天这台机器的 `network.provider_reachability=fail` 正是这个组合的结果。是否让 pipeline 显式传递代理属于关键决策（见第 6 节）。

**5.10 失败不可关联、不可幂等重试。** 没有保存远端 `request_id`/`response_id`，也没有“请求已发出但结果未知”的状态记录；`recovery.inspect_candidate` 在没拿到完整计划时只能保留输入重做。一旦厂商侧确实开始生成而我们超时放弃，无法查询也无法安全幂等重试。

**5.11 历史观测工具本身有盲点。** 旧的 `RUST_LOG=error` 全局屏蔽 `codex_core::responses_retry` 的 WARN；`codex.retry` 是 TRACE；`codex.websocket_event` 根本不打日志；release 构建还隐藏第一次重连提示。因此“看不到重试”曾被误读为“没有重试”。本轮的投影新增 `ws_text_frame_unparsed`/`sse_event_unparsed`/`ws_to_https_fallback`/`stream_retry_decision` 等固定类别标记，只落类别、不落原文。

## 6. 下一步建议（需要用户决定的事）

1. **先修网络再谈超时**：`codex doctor --json` 的两项网络检查是这条链路的体检入口。历史 600 秒静默与今天的连接失败都出现在后端路径异常时；网络正常时 #2/#3 都在 150 秒内完成。
2. **是否把 planner 的传输默认切到 HTTP/SSE**：本地实验证明 SSE 的停滞检测不会被保活帧击败，#2 也用它拿到了通过验证的计划。但这会改变生产传输，且只有一次成功样本；建议先用 `progress_timeout` 观察若干次真实创建，再决定是否切换。
3. **#3 暴露的计划质量问题**：`Outcome assertion role must match the promised purpose` 属于业务语义校验，按现有规则不应放宽。若这条规则频繁命中，正确方向是缩小 planner 一次生成的范围（见 5.5），而不是下调校验。
4. **agent 阶段看门狗是否默认开启**：现在需要显式设置 `limits.agent_progress_timeout`。默认关闭是因为 agent 允许长静默工具执行；如果你希望默认开启，需要接受“静默且无进程活动即中断”的语义。
5. **Docker 业务验收**：本轮按批准未运行。已有通过验证的计划在 `call-20261026T150937Z-https/validated-cases.json`，可作为下一轮独立构建与验收的输入（但那次成功本身仍不等于新创建验收通过）。

## 7. 未做的事

- 没有跑 Docker、没有写 catalog、没有回收候选、没有改全局配置/代理/认证、没有降级 schema 或来源约束。
- 没有用“简化 schema”之类会改变正式契约的做法换取成功。
- 业务验收 `not_run`；任何真实成功调用都不等于新创建验收通过。
