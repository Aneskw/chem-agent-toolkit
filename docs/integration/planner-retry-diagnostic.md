# RECAP planner：隐藏重试专项诊断

## 范围与基线

基线 cb8d2b5，分支 integration/planner-timeout，开始时工作区干净，无后续提交；再次检查仓库及父目录未发现适用 AGENTS.md。本次只新增 validation 下的局部采集器、回环机制探针、受控调用脚本、汇总脚本和证据。生产代码、CLI、用户配置、代理、认证和业务输入未修改。

CLI 0.164.0-alpha.11.1，路径 C:/Users/27343/AppData/Local/OpenAI/Codex/bin/2993767bd1dfb009/codex.EXE，SHA-256 1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098。版本命令与二进制哈希再次核对。源码依据为 rust-v0.164.0-alpha.11.1，复用 static-await/source-excerpts.json，并补充 telemetry 的失败记账与发送耗时代码。没有使用其他版本源码。

## 先验证原版 CLI，而非手工日志字符串

local_cli_probe.py 启动原版 CLI，使用独立临时 CODEX_HOME、本机 127.0.0.1 模拟 WebSocket、合成 prompt、250ms 空闲超时与 2 次流重试。该机制测试不访问真实模型，不使用用户认证。它刻意缩短超时且指定本地 provider，**这些是机制测试变量，未带入真实受控调用**。

模拟服务只接受连接、丢弃客户端消息并记录时间，不返回业务帧。CLI 自己产生空闲超时、重试与重发日志；服务端独立记录收到的连接和消息。8 项检查通过：实际 CLI idle 错误、重试决策、序号、退避、三次主发送、本机服务收件、发送至超时的时间区间、敏感字段过滤。41 行实际日志逐行添加敏感哨兵后测试过滤，哨兵及任意原文不入文件；不是只匹配手工构造日志。

原宿主 websockets 为 10.4，适配其已有 server 接口，未安装依赖。默认沙箱中的首次探针没有得到可用证据，已终止；经平台具体操作审批后，本机探针完成。临时配置由作用域清理。此环境问题不作为模型传输失败证据。

已有 model_call 监督测试 9/9 通过，见 local-tests.log。初次默认临时目录受沙箱 WinError 5 限制；将测试临时目录限定在工作区后通过，没有改全局配置。

## 新增观测及边界

- 保持既有 INFO 生命周期日志，局部增加 codex_core::responses_retry=warn，以及 codex_otel.trace_safe=trace。
- 固定类别 websocket_idle_timeout 来自 CLI 映射错误或 retry WARN 中的固定错误文本；记录的是错误传播后的日志时间，不冒充底层定时器精确唤醒时刻。
- codex.retry 保留 retry.attempt、retry.delay_ms、retry.layer、retry.operation；不保存任意错误原文。
- 连接开始/完成有现成日志。主请求 send 完成有 warmup=false、success、duration_ms。send 开始没有独立事件，只能用完成 UTC 减 duration_ms 估算，精度受毫秒取整及日志时间影响。
- CLI UTC 来自发出日志的时间；observed_seconds 是采集器初始化后的单调时间。model_call 的 elapsed_seconds 有另一个起点，不能直接混用。
- 保留未知行的 UTC、级别与白名单模块，不保存认证信息、头部或请求/响应正文。已知错误只保留固定类别，其他错误归为 other_error。
- **codex.sse_event + response.completed 不是单独的远端成功证据**：see_event_completed_failed 也使用这个 kind。采集器增加 error_present/error_class 区分。预热日志与主发送分开分析。
- 本次门槛只要求区分 timeout/retry/reconnect/resend，不要求完整逐帧或 Ping/Pong。原版 CLI 仍无这些逐帧证据；不能据此推断服务器未生成。

## 唯一真实受控调用

启动前本机门槛通过，脚本再次核验二进制哈希；原 prompt 与修复 schema 哈希断言通过，材料 inventory 及文本完整性通过。保持 gpt-6-astra、medium/default、600 秒，业务输入、传输选择及其他调用参数不变，只有局部 RUST_LOG 与 stderr 投影新增。脚本以 controlled 目录的排他创建阻止无变化重复运行。

prompt SHA-256：8af7e4416549cc30a3499000baf53293745efd82920ccbcc2bb1b0e7ba0bc9d9。

schema SHA-256：cbadd6d58b818812ef8672da6ad09664a1fdd1511a69e722d10cb999094f1ea4。

如有答案，脚本保留原答案并复用 jsonschema、planner.inventory 和 preparation.validate（计划、来源、入口、验收完整性）校验；受控成功不代表正常创建成功。没有运行创建/恢复、Docker、宿主化学业务或 catalog 操作。

## 实际结果

唯一远端调用于 2026-10-26 10:39:45 UTC 启动，约 10:49:45 UTC 被外层看门狗终止；耗时 600.060 秒（监督结束 600.008，清理 0.052）。thread_id 为 01a177cb-7841-7571-ba02-0f830c65e333。不是正常新创建验收。

| 事实 | 时间或数量 |
| --- | --- |
| stdin 写完并关闭 | 进程监督起点后 0.279 秒 |
| thread.started / turn.started | 0.481 / 1.335 秒 |
| 预热 send 完成 | 10:39:47.508519 UTC，warmup=true |
| 预热完成记账，无错误标记 | 10:39:47.932414 UTC |
| 主 send 完成 | 10:39:48.983022 UTC；warmup=false，success=true，duration_ms=1 |
| 主 send 开始 | 没有直接观测；按耗时估算约 10:39:48.982 UTC，不作为独立证据 |
| 主流 idle timeout 固定类别 | 0 条 |
| stream_retry_decision / codex.retry | 0 / 0 条 |
| 第二次主发送、主发送后的重连 | 0 / 0 条 |
| 模型列表请求 | 三次 HTTP 200；不能解释主流停滞 |
| stdout | 仅上述两个启动事件，无答案或终止事件 |
| 清理 | stream_threads_finished=true，io_errors=[]；清理前仍存活，清理后 returncode=0 不代表模型成功 |
| 输入完整性 | 调用前后均 passed |

最后一个已证明的主请求传输阶段仍是 **10:39:48.983022 UTC 的客户端 send 完成**。最终外层停在 waiting_for_process_completion。后来模型列表响应不是主流进展；不把没有记录当成服务端没有入站事件。

stderr 共 30 条脱敏记录。完整时间线见 controlled/timeline-summary.json；运行条件、request/process/events/stdout/stderr/timeout/result 均保留。没有答案，因此 schema/计划/来源/入口/验收内容校验没有可执行输入；business_acceptance=not_run，不属于化学业务失败。

## 分别回答三个问题

1. **隐藏的 300 秒超时与重试是否证实？没有。** 本机原版 CLI 的真实路径已证明这些日志能被采集；本次远端调用在主 send 后越过 300 秒仍没有该错误、重试决策、退避或再次发送。结果不支持所提出的完整时间线。它不等于证明所有低层或服务端都没有重试，也不回推历史运行。
2. **是否解释了 600 秒超时？不能。** 确定的是外层等待进程退出到期；没有第二次主发送证据，不能称为第二轮流等待被终止。
3. **最初停滞是否仍未知？是，根因未确定。** 仍无法区分持续收到被忽略文本而重置 idle、内部队列或消费者等待、历史静态重建之外的有效超时配置，或远端处理/响应问题。它们是待查分支，不是新结论。

没有发现新的已复现功能缺陷；确认并补齐了旧日志遗漏重试的观测缺陷。下一步最小决定性证据是：CLI 最终生效的 idle/retry 数值；主流 next 进入/返回及 timer expiry 的元数据；队列 send/reserve 开始/结束；收到文本后固定的 parsed/ignored/error 分类计数。无需正文或凭据。若既有接口仍不暴露这些状态，需要维护方提供 CLI/服务端关联证据；本次不修改 CLI、不新增调用。

最小脱敏维护包为 validation/planner-retry-diagnostic/controlled/diagnostic-package.json，含版本/哈希、UTC 窗口、thread ID、主发送及清理时间线和未知项。没有取得可直接查询的远端 response/request ID；thread ID 是客户端会话标识，不能冒充服务端确认。
