# RECAP planner 等待阶段诊断（2026-10-26）

## 基线、证据来源与边界

起点 `16de30c`，分支 `integration/planner-timeout`，无后续提交，初始工作区干净；仓库及父目录未发现适用 AGENTS.md。未覆盖用户工作、改写历史或修改 partner。先阅读 schema 专项报告/controlled 证据及 model_call、network、command、runner；本次没有全链路创建、候选恢复、Docker、宿主化学业务或 catalog 操作。

实际 PATH 解析到先前相同位置的 `codex.exe`，当前自报 `0.164.0-alpha.11.1`，二进制 SHA-256 `1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`。前次没有二进制哈希，故不能声称已逐字节核验历史二进制相同。

官方 [对应版本发布页](https://github.com/openai/codex/releases/tag/rust-v0.164.0-alpha.11.1) 指向 `6905ece`。实际通过 GitHub 连接器读取该 tag 的源码，精确文件/行号节选在 `validation/planner-wait-stage/source-excerpts.json`。开始尝试的 `event_processor_with_json_output.rs` 返回 404；读取目录后找到正确的 `event_processor_with_jsonl_output.rs`，没有把不存在的文件或 main 分支充作版本证据。发布源码与二进制自报版本对应，不等于可复现编译认证。

使用 OpenAI Docs 技能核对官方 [环境变量](https://learn.chatgpt.com/docs/config-file/environment-variables) 和 [遥测说明](https://learn.chatgpt.com/docs/agent-approvals-security)。RUST_LOG 支持局部过滤，但最新文档不能代替本版本实现。只读查询本机日志库前次受控线程/PID及时间窗，记录数为 0；没有读取原始日志正文、认证文件或完整环境变量。`baseline.json` 保存查询条件和结果。

## 由对应版本源码建立的时序

1. Python 创建隔离临时 cwd/schema；Windows 先挂入 Job 再恢复子进程。三个线程分别写 stdin、读 stdout、读 stderr。Windows 的 model_environment 返回环境副本，没有 macOS 的 scutil 分支；本次未改代理值。command.py 解析实际安装 CLI。
2. CLI 使用本地 in-process app-server。thread/start 返回后，exec/lib.rs 1153–1178 将返回值转成 SessionConfigured 并打印配置；jsonl processor 403–406、605–612 在此生成 `thread.started`。它不是远端推理服务器确认。
3. exec 发本地 turn/start；jsonl processor 594–596 把 ServerNotification::TurnStarted 转成 `turn.started`。core/tasks/regular.rs 48–80 明确在等待启动预热之前发出 TurnStarted。它不是模型请求已发送或开始生成的证明。
4. websocket 预热使用 `generate=false`（core/client.rs 2066–2070）；prewarm_websocket 等待预热 Completed 后才用于第一轮请求（2331–2386）。因此预热的 response.completed 不能当成 planner 答案完成。
5. codex-api 的 connect_websocket 在 connector.connect 成功（HTTP 升级响应）后记录连接成功；send_websocket_request 在 ws_stream.send 返回后记录 on_ws_request。`codex.websocket_request success=true` 证明客户端发送操作完成，不证明服务端接收、调度或生成。随后代码等待 ws_stream.next；这是本地可观测与远端不可观测的边界。
6. Python 仍等待子进程退出，退出后才解析成功/失败和答案。600 秒是外层进程看门狗，不是某个远端请求的专用计时器。

## 模型列表刷新与主请求

该版本 app-server/models_refresh_worker.rs 创建独立 tokio 任务，先 Online 刷新，完成后等待 270 秒再刷新。models-manager 的 raw_model_catalog await 刷新失败后记录错误，并返回当前/回退目录；默认目录没有显式 provider 使用的 refresh mutex。另有部分调用路径会 await 目录刷新，因此不能笼统说“目录刷新从不阻塞”。

前次 stderr 的一行刷新超时没有任务/请求关联，无法认定来自哪次刷新，更不能证明阻塞主生成。本次真实诊断中模型列表 HTTP 200、预热完成、非预热发送成功均已发生，故至少本次长期等待并非被首次目录刷新卡在主请求发送之前。独立后台刷新是代码事实；历史错误的具体调用链仍未确定。

## 最小观测与机制测试

生产仅改 model_call.run 的观测：stdin 关闭时刻、各输出通道首/末行和行数、终止事件时刻、清理前状态/退出码及清理耗时；新增可选 stderr_filter，在内存捕获和文件写入前调用。默认调用无过滤，既有接受/拒绝、超时和清理逻辑未改。没有猜测性“修复网络”或提前接受答案。

本地诊断 helper 只保留固定事件类别、数字耗时/状态/attempt、布尔值、限定流事件名、endpoint 角色及请求标识 SHA-256；原始 stderr 不保存，未知行只记数量/时刻。不保留认证头、cookie、token、地址查询参数、用户邮箱、完整环境、错误正文或请求/响应内容。CLI 自身的普通 stdout 答案仍按既有逻辑保存。

19 项针对性机制测试通过（7 项新增、原 model_call 9 项、schema 3 项）：

- 子进程发出终止事件却继续运行，会被看门狗拒绝；这是已复现的监督边界，不能解释前次根本没有终止事件的情况，也不把终止事件直接当成功。
- 双向 200 KB 管道并发读写、读取 stdin 至 EOF 正常完成；不读 1 MB stdin 的子进程仍被看门狗有界终止。局部测试降低管道死锁嫌疑，不声称证明所有 OS/CLI 路径绝无死锁。
- 白名单丢弃假凭据、嵌入字段、URL userinfo/query；过滤发生在 capture 与持久化之前；过滤器异常按 I/O 失败拒绝，不保存原始行。
- 清理前 returncode=None 与清理后 returncode=0 可以并存，status 仍明确为 timed_out，不混淆自然退出成功与 Job 关闭后的结果。

最初扩展测试中的一项断言误把测试命令自身携带的假敏感字符串也算作泄漏；改为检查实际 io_errors 只含异常类型，stderr 内容检查保持不变。原失败日志保留，随后 19/19 通过。此前调用前的 16/16 与过滤器定向测试也保留。

## 唯一真实受控诊断

固定第四轮 prompt SHA-256 `8af7e4416549cc30a3499000baf53293745efd82920ccbcc2bb1b0e7ba0bc9d9`，修复 schema SHA-256 `cbadd6d58b818812ef8672da6ad09664a1fdd1511a69e722d10cb999094f1ea4`，gpt-6-astra、medium/default、600 秒；与上次 payload 相同。配置覆盖限于子进程 reasoning/service tier 与 RUST_LOG，无全局改动。预检对照原 inventory、已读文本，若有答案执行原 schema + preparation.validate，再验证输入未改。

调用前说明要区分初始化/预热、连接、发送及响应阶段。只启用 trace-safe 遥测和指定模块 INFO，未启用 HTTP header/body 或完整帧 TRACE；用匹配版本源码选择信号。诊断相对时间由 wrapper 的 StderrProjection 起点计算，略早于 model_call.run 起点；不得与 events.json 时间混作完全相同的零点。

最终结果：**600.049 秒超时，无答案，根因未确定。** 北京时间 17:39:12 开始、约 17:49:12 结束；未自动重试。主要时序如下（诊断时间零点约比 run 早 0.248 秒）：

| 观测 | 时间/结果 |
| --- | --- |
| stdin 写完并关闭（run 时钟） | 0.250 秒 |
| thread.started / turn.started（run 时钟） | 0.462 / 1.317 秒 |
| models 请求完成（诊断时钟） | 2.569 秒，HTTP 200，attempt=0 |
| WebSocket 连接成功 | 3.313 秒，连接耗时 1752 ms |
| 预热发送成功 | 3.319 秒，warmup=true |
| 预热 response.completed | 3.932 秒；不属于主 planner 答案 |
| 主请求本地发送成功 | 4.855 秒，warmup=false，发送耗时 1 ms |
| 后台 models 刷新 | 274.834、546.592 秒均 HTTP 200，attempt=0 |
| 外层看门狗决策（run 时钟） | 600.001 秒，子进程仍存活，returncode_before_cleanup=null |
| 清理 | 0.048 秒；全部 I/O 线程结束，io_errors=[] |

共观察到 1 次 WebSocket 连接启动、1 次预热发送、1 次非预热发送；没有观察到第二次主发送，不把它扩大为所有内部重试次数为零。stdout 两行均为启动事件，无 CLI 终止事件。stderr 共 30 行投影，其中 18 行仅保留 unclassified 标识。清理后 returncode=0，但状态始终是 timed_out，不算成功。输入完整性在结束后再次核验通过。未返回 JSON，因此未执行真实答案的 schema/计划/验收完整性校验；business_acceptance=not_run。

## 本次能够和不能够作出的结论

- **明确阶段：** 外层在等子进程退出；内层至少已完成主请求的本地 WebSocket 发送，之后未得到可用的完成结果。这比“turn.started 后无输出”更具体，但不是精确到远端服务内部栈的定位。
- **本次可以排除：** stdin 未写完/未关闭；首次 WebSocket 从未连接成功；启动预热未完成；首次目录刷新阻止主请求发送；已收到 CLI 终止事件但只因进程不退出而超时。依据是本次相应时间戳和事件，不是仅凭机制测试。
- **只能降低嫌疑：** Python 管道死锁。三个线程及 EOF 路径已核实，本地压力/超时测试通过，实际 stderr 直到约 546 秒仍被消费、清理无 I/O 错误；但不能以此绝对排除任意 CLI/OS 内部阻塞。
- **最值得继续查：** 主请求发送后的响应链路，包括服务端排队/复杂结构化生成、响应传输、CLI 的流读取/消费。阶段定位证据强；上述具体原因彼此尚无足够证据排序。根因未确定，不默认归因网络或化学业务。
- **目录刷新关联：** 已证明共享同一 CLI 生命周期且存在独立刷新任务，本次三次刷新成功；没有已证明的“刷新超时导致主生成超时”因果关联，也不能回推历史调用与本次路径完全相同。
- **本地缺陷判断：** 未发现能解释本次超时的 Python 实现缺陷。复现了“终止事件不使监督立即结束”的边界，现有策略最终拒绝超时而非错误接受，未据此改完成语义。生产修改仅补观测，仍需要 CLI/服务端层证据。

本次专项已停止，不再无变化重试；暂不启动完整验收。所有新增可提交证据及哈希清单在 `validation/planner-wait-stage/`，旧失败证据原样保留。

### 观测限制与决定性下一步

本版本 record_websocket_event 对每帧主要记录 metrics，Ping/Pong 直接返回，不逐帧输出上述 trace-safe 文本日志。因此本轮没有主请求首帧时刻，不能从 stdout 只有启动事件推出服务端没有生成，也不能从缺少错误事件推出连接始终健康。连接成功说明升级握手得到响应，但所选遥测未提供该握手的数值状态或可关联的远端请求 ID。请求 ID 如有只保存哈希；本次不能凭空补一个。

未知诊断行故意只保留 unclassified_line 和时间，不保留其任意正文。这是隐私优先投影的明确局限，不能宣称捕获了所有错误/重试。发送与连接事件的计数只代表已观察次数；不是所有 CLI 内部重试的权威计数。现有前次裸 stderr 与本次投影格式不同，不能机械按文本错误数量比较。

下一步最省成本的是先用本次精确 UTC 时间窗、CLI 版本、线程标识和非预热发送时间，请 CLI/服务端维护方关联主生成请求，查询请求接收、排队/推理开始、首帧、终止状态；不必再发现或编写 Skill。如果缺少关联 ID 阻止查询，再对这个精确版本增加仅记录主请求 correlation ID、response.created ID、每帧类型/字节数/时间与重试序号的脱敏观测，先用本地假流验证，再另行授权一次调用。不采集认证头或帧正文。不能把全量 trace/header/body 日志当作必要前提。

只增加 Python 阶段时间戳无法跨越远端可观测边界。服务端处理/排队、响应传输中断、CLI 内部流消费停滞和结构化生成耗时仍需上述证据区分。此处是诊断建议，不是已证实原因，也未实施代理、模型或配置变更。
