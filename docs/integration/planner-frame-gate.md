# RECAP 主请求入站观测能力核验（2026-10-26）

**结果：本次真实模型调用 0 次。启动门槛未满足，根因未确定。** 已完成对应版本源码核验、局部观测方案、17 项本地测试及维护方诊断包。没有为了用完一次调用而重复上次实验，没有修改/替换 CLI、生产 model_call、全局配置、代理、认证、传输、模型或超时。

## 基线和版本

实际基线 `48e1232`，分支 `integration/planner-timeout`，无后续提交，初始工作区干净。递归仓库及父目录未发现适用 AGENTS.md。先阅读两个专项报告、controlled 日志、source-excerpts、diagnostics.py、controlled_call.py 和 model_call.py；历史证据未改。

当前 CLI 路径 `C:/Users/27343/AppData/Local/OpenAI/Codex/bin/2993767bd1dfb009/codex.EXE`，版本 `0.164.0-alpha.11.1`，SHA-256 `1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`，与上轮保存的二进制哈希一致。当前 prompt/schema 哈希及原 handoff inventory、已读文本也核验一致。

通过 GitHub 连接器读取 `rust-v0.164.0-alpha.11.1` 对应源码，而非 main/其他版本。节选、行号和原链接保存在 `validation/planner-frame-gate/source-excerpts.json`。包名 codex-websocket-client 对应仓库目录 websocket-client（最初按包名访问返回 404，随后由该 tag 的 Cargo.toml 定位）；未将不存在路径当证据。首次版本辅助命令未显式指定编码，解码沙箱警告出现 GBK 异常；之后用显式 UTF-8 捕获 `--version`，版本和哈希核验成功。这不是模型传输失败。

使用 OpenAI Docs 技能核对官方 [遥测说明](https://learn.chatgpt.com/docs/agent-approvals-security)，但以该版本实现判断具体能力。只执行 `--version`、`debug --help`、`exec --help` 等无模型命令；没有执行 debug models 或 prompt-input。CLI 帮助没有列出专门的逐帧元数据导出选项；这不是对所有未公开接口的穷尽证明。

## 本次新增的关键代码证据

| 层次 | 对应版本事实 | 能力与限制 |
| --- | --- | --- |
| 最底层 WsStream 泵 | responses_websocket.rs 66–119：inner.next 收到 Ping 后直接发 Pong；Pong 分支为空；仅其他消息/错误向 tx_message 转发 | 成功 Ping/Pong 在进入上层 telemetry 前就消失；RUST_LOG 无法让未发出的应用事件出现 |
| 上层 WS telemetry | session_telemetry.rs 946–1005：文本取 type，记录 counter/histogram；Ping/Pong return | metrics 可以补部分事件种类统计，但没有完整逐帧时间、字节数、连接/请求身份、response ID；仍不能区分无帧与仅控制帧 |
| JSON 解析 | sse/responses.rs 405–419：response.created 提取 response.id 并生成 Created；failed 转错误 | 这是远端业务确认的可观测插入点，当前没有被安全逐项导出给外层 Python |
| 内部事件转发 | responses_websocket.rs 908–938：Created ID 保存在局部状态，tx_event.send 转发；Completed 还涉及 reserve/send | 可在这里区分解析完成与内部队列转发等待，现有日志不完整覆盖这些边界 |
| core 消费 | turn.rs 2873–2886：record_responses 后把 Created ID 放入 extension_data | “内部拿到 ID”不等于 stdout 输出 ID |
| trace span | session_telemetry.rs 637–675：记录 otel.name/部分使用量 | trace 可补部分已消费事件，不提供底层控制帧、帧长度或 Created ID；未将未验证的 trace 导出视为已覆盖 |
| 握手 | connector.rs 46–48 接收 `(stream, _status, ...)`，数值状态在此未往上带 | 已有连接成功日志不等于已有数值响应状态或完整关联标识 |
| timing TRACE | responses_websocket.rs 956–984 仅对 responsesapi.websocket_timing 生效，含完整 payload | 不是任意帧监听器，不保证服务端发送该类事件；没有启用原文 TRACE |

低层 websocket-client 的 Stream 包装和 otel-trace-websocket 也检查了：后者提供 trace 输出通道，其控制帧处理不等于主模型 WebSocket 的控制帧观测。没有把两条 WebSocket 混为一谈。HTTP SSE 的 `SSE event: data` TRACE 属于另一传输路径，且包含正文；不能用它证明当前 WS 路径覆盖，也没有切换传输或启用它。

## 为什么没有启动真实调用

至少 `wire_frame_metadata`、连接/请求身份、解析事件身份、内部转发、重试身份未得到可用接口的完整验证。当前可验证的 warmup 日志与 stdout 阶段已在上一轮使用，不能算新增决定性信号。

**“没有任何入站帧”和“只有成功 Ping/Pong”会在已核实的应用 telemetry 中留下相同空结果。** 这是该层观测丢失信息，不是过滤正则写得不够宽。OTel metrics/trace 可以部分改善其他阶段，但不能补齐这项必须区分的情形。因此本次没有启用新的导出器，也没有再发主请求。没有以“未记录到”冒充“明确没有”。

没有证明服务端未收到请求、没有生成或已出错。本次没有新的远端确认、首帧时间线或服务端 ID；不回推历史根因。也没有证明 CLI 存在导致超时的功能缺陷；确认的是观测覆盖不足。

## 局部方案与本地测试

新增 `validation/planner_frame_observation.py` 是**仅本地设计原型**，没有连接实际 CLI 的 producer，不含模型启动代码。它定义独立的连接/请求序号、warmup、单调时钟、握手状态、frame kind/字节数、解析事件、内部转发、stdout 转发、重试与看门狗记录。原型只抽取固定类型和明确白名单 response.id（保留可查询 ID，拒绝凭据形态）；不写正文或解析异常原文。未知日志投影保留限定级别/模块和固定错误分类，不保留任意原文；模块不在白名单时记 other。

17/17 本地测试通过：10 项新方案/门槛测试，加 7 项已有监督测试。模拟输入是 byte payload 流，经原型观察器实际解析、生成元数据和序列化，覆盖无帧、仅 Ping/Pong、Created 后停滞、业务事件未完成、解析未转发、重试重连、预热与主请求隔离、终止后仍存活、敏感内容与非法 JSON。已有真实本地 Python 子进程测试确认终止事件后继续存活会触发外层看门狗。模拟轨迹使用合成单调时钟，握手 101 也是 fixture，不属于真实调用结果。

这些测试验证**方案能区分所需情形和拒绝泄漏**；不证明原版 CLI 发出这些信号。另有源代码对应关系断言，但它也不是运行或重新编译 Rust 测试。启动门槛测试明确保持 allowed=false，原型测试通过不能将其打开。模拟文件及 local-tests.log 明确标注此边界。

## 如需 CLI 支持：最小插桩位置和实验变量

要满足全部观测要求，需要维护方提供原版 CLI 可用的安全 producer，或另行批准带诊断插桩的同版本构建。**本次未修改、编译、安装或替换 CLI。** 最小插桩提案：

1. `WsStream::new` 中 inner.next 返回后、Ping/Pong 分流之前：记录 monotonic_ns、connection_seq、frame_seq、frame_type、payload byte_count；不序列化消息。
2. 请求发送前/完成后：request_seq、warmup、connection_seq、固定状态；关联边界需显式标识 idle/prewarm/main，不能将没有归属的控制帧强行归入主请求。
3. 握手只抽取 status 与明确白名单 `x-request-id`/trace ID；解析 Created 只取 response.id；绝不记录完整 headers。不存在 ID 时明确 null，不从其他字段猜。
4. JSON parse 后、tx_event.send 前后、core 接收、stdout 输出：关联同一请求并记录事件枚举与固定错误分类；分别记录 response 终止、CLI 终止和进程退出。
5. 明确重试/重连序号和原因枚举；诊断写入不得阻塞推理任务。若队列溢出，计 dropped_records 并把“没有事件”的结论降为未知。退出/看门狗前须持久化最后进度，不能只依赖正常退出时批量 flush。

改用诊断构建会改变二进制哈希、日志开销和调度时序，是必须声明的新实验变量。应先用同版本 Rust 本地假 WebSocket + 本地子进程设施验证七类场景及丢日志行为，再考虑唯一真实调用；不能把本次 Python 原型测试替代那一步。TLS 验证、传输选择、请求内容和原有超时应不变，不使用中间人代理。

## 维护方最小包与结论

`validation/planner-frame-gate/maintainer-package.json` 只携带上一轮真实调用的元数据，不包含业务 prompt、源码或帧正文：

- CLI 版本/路径/哈希、prompt/schema 哈希；UTC 起点 `2026-10-26T09:39:12Z`，结束估算 `09:49:12.049Z`（起点只有秒精度）。
- 本地线程 `01a17794-08e4-7742-8417-d4cb1392cad9`；不是远端 request ID。request/response/trace ID 都是 null，不能声称维护方已能直接按请求查询。
- 历史阶段时间线、一次主发送、600.049 秒超时及清理状态；诊断时钟与 run 零点约相差 0.248 秒。
- 首帧、控制帧、远端确认、解析/转发状态和权威重试次数仍未知。没有只有哈希却冒充原始可查询 ID 的情况。

最细已证明阶段仍来自上一轮：**非预热主请求本地 send 完成之后，到可用完成结果之前；外层等待进程退出超时。** 本次没有新增远端事实，所以没有新增排除服务端/传输/CLI 消费原因。先由维护方用时间窗和本地线程尝试关联服务端记录；若无法关联，需要上述 producer 支持，而不是立即再跑 600 秒。

根因未确定。专项在真实调用前按用户设定的停止条件结束；不进入完整创建或候选恢复，等待审阅。
