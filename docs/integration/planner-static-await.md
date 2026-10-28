# RECAP planner：静态等待与重试核查

本次仅静态读取配置、历史证据及匹配版本源码，真实模型调用 0 次。没有修改生产代码、CLI 或配置。

基线：integration/planner-timeout，23c1c60，开始时工作区干净，未发现适用 AGENTS.md。二进制 SHA-256 再次核对为 1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098；已核验版本 0.164.0-alpha.11.1。本文全部 Rust 行号对应 tag rust-v0.164.0-alpha.11.1，不使用 main。证据与直接 await 索引见 ../../validation/planner-static-await/source-excerpts.json。

## 1. 超时与预算

| 项目 | 对应版本配置值与语义 |
| --- | --- |
| stream_idle_timeout_ms | 默认 300000，即 300 秒；不是整个响应的总时限 |
| websocket_connect_timeout_ms | 默认 15000，即连接建立 15 秒 |
| stream_max_retries | 默认 5 次重试，初次加重试通常最多 6 次流尝试；不能作为所有情况的全局上限 |
| request_max_retries | 默认 4；虽传给 max_attempts，实际 for 0..=max_attempts，故初次加 4 次重试，共最多 5 次 HTTP 尝试 |
| HTTP retry 分类 | retry_429=false、retry_5xx=true、retry_transport=true；基本延迟 200ms，退避/抖动，尊重 Retry-After |
| 特殊连接重试 | unbounded_connection_retries 默认 true。仅 Sampling + ConnectionFailed + 非 internal session + 非 Bedrock 条件成立时，无固定次数上限；等待 5 秒起、倍增至 60 秒 |
| 普通流重试 | 仅可重试错误生效；服务器建议或指数退避。预算耗尽且可切换传输时，切换后 retries 清零，故 5 不是跨传输总预算 |
| 外层 Python | 600 秒等子进程退出；覆盖初始化、全部尝试、内部消费和收尾 |

当前 CODEX_HOME 是默认目录；只提取配置白名单，model_provider/profile 均未设置，无自定义 model_providers，无 unbounded_connection_retries 覆盖。历史 request.json 命令也没有上述超时/预算覆盖；medium/default 只覆盖推理与服务层级。因而**现有配置与历史命令支持按内置 OpenAI 默认值重建为 300 秒 / 5 次 / 4 次**。

证据边界：历史未保存 CLI 最终合并的 provider/feature 配置，当前配置不能证明历史配置未改变；本次没有取得所有托管配置层的最终合并快照。因此这是静态重建值，不能冒充当时运行时回读的有效值。需新增只含 provider 标识、上述数值和 feature 布尔值的 resolved-config 记录才能封闭此缺口。部分猜测的配置加载源码路径返回 404，未作为证据。

request 重试是 HTTP 请求层策略，不能将它乘进已建立 WebSocket 的每次 send；stream 空闲错误走流错误重试分类，也不能直接当成 ConnectionFailed 的无限重试。

## 2. 主发送后的等待图

下表列出主 WS 路径各层直接等待类别；source-excerpts.json 列出该范围内每个 .await 行号与上下文，也包括 select 隐式等待的源码。它不是整个 CLI 所有被调辅助函数的递归穷举。没有将“调用点无 timeout”误写成“辅助函数内部一定无超时”。

| 层/位置 | 等待 | 超时、取消、下游依赖 |
| --- | --- | --- |
| WS pump，responses_websocket.rs 74–113 | command.recv / inner.next；inner.send；收到 Ping 后 send Pong | pump 自身无定时器；发送由调用者包装时才受其等待上限约束。Pong 发送没有单独超时。WsStream Drop abort pump |
| WsStream 135–152 | command.send、oneshot 回执、失败时 message.recv；next 的 message.recv | 单独无超时。正常主 send 整体由 300 秒包裹；next 由下面的 300 秒包裹 |
| stream_request 291–336 | 初始 metadata send；interrupt oneshot；stream.lock | metadata send 无定时器；锁等待与 consumer closed、显式 Cancel deadline 竞争；Drain 或 interrupt sender 丢弃不产生固定截止时间 |
| 主 send / interrupt send，736、762、1008–1012 | send_websocket_request | 每次 send 的本地操作 timeout(idle_timeout)，不是服务端确认时限 |
| 主接收，746 | timeout(idle_timeout, ws_stream.next()) | 每次下一消息等待最多 300 秒；与可用的 interrupt 请求竞争 |
| metadata 847、860、878、884、894、904 | tx_event.send | 无自己的时间上限，受下游消费影响；处于外层 consumer closed / 显式 Cancel deadline select 中 |
| 业务事件 916 | tx_event.send | 同上；Created 在 send 前保存 response ID |
| 完成 935 | tx_event.reserve | 等 API 消费者释放容量；不受当前 next 的空闲计时保护 |
| producer 收尾 370/375 附近 | 错误/保留完成事件 send | 已在主 select 外，无自己的定时器；消费者关闭会解除等待 |
| mapper，client.rs 2547 起 | api_stream.next 与 consumer_dropped.cancelled | 无空闲时限，等待 API producer；消费端 Drop 触发取消 |
| mapper 各分支 | mapped tx_event.send(OutputItemDone/Completed/其他/Err) | 1600 队列背压，无独立定时器；接收端关闭使 send 返回错误 |
| turn.rs 2808 | stream.next，经 preempt/cancellation 的 or_cancel | 有取消，没有固定时长；等待 mapper |
| turn 事件处理 2876–3372 | TTFT、消息排序、输出条目处理、计划/文本解析辅助调用、send_event、模型/安全元数据、速率限制、token usage | 调用点无统一 idle timeout；处理期间不消费下一事件，可向前传递背压。所有直接 await 行号在附件 |
| turn.rs 3175 | ModelsEtag → refresh_if_new_etag.await | 是明确存在的模型刷新关联路径；只证明收到此事件后的消费路径会等待该调用，不能证明历史三次刷新由此触发或堵塞主响应 |
| turn 收尾 3394–3434 | hook/accounting、消息 flush、drain_in_flight、token count、diff mutex/send | 调用点无整体响应时间上限；部分依赖内部任务/锁/事件输出；与“已经收到完成”是不同阶段 |
| responses_retry.rs | notify_stream_error / send_event；sleep/sleep_until；content-filter 记录 | 通知依赖事件路径；sleep 是退避等待，不是主响应超时。普通流失败后可能再发请求 |
| Python model_call.run | 等待 CLI 进程退出 | 600 秒总看门狗；CLI 终止事件与进程退出不同 |

因此不能从“超过 300 秒仍没有 stdout”推出 idle timeout 未启用。超时可能已发生但在重试，也可能持续收到被忽略消息，或处于队列/消费者等待。

## 3. 队列、生命周期与计时重置

链路：
- WS command 队列：32。
- pump → 上层原始消息队列：unbounded；业务消费者慢不会直接令 pump 的同步 enqueue 等待，但可能积压内存。
- API ResponseEvent 队列：1600。
- mapper → core ResponseEvent 队列：1600。

两个 1600 队列均有异步 send 背压。core 变慢可令 mapper 停止读取 API 队列，再令 API producer 停在 send/reserve，离开 per-next 空闲计时覆盖区。这里只证明可能的代码路径，没有队列占用或任务栈证据证明历史发生了背压。

core ResponseStream Drop 调用 consumer_dropped.cancel；mapper 退出会释放 API receiver；producer select 观察 tx_event.closed。失败时 producer 取出并丢弃 socket，WsStream Drop abort pump，避免等待优雅 close。消费者仍存活但不再 poll 与消费者被 Drop 不同，前者不触发 closed。普通 Drain 不具备 Cancel deadline。

| 入站情形 | 上层 idle 计时 |
| --- | --- |
| 完全没有转发消息 | 同一个 next 等待，300 秒到期 |
| 只有成功 Ping/Pong | pump 吞掉控制帧，**不重置**上层 next 的计时 |
| 非法 JSON 文本 | next 已返回；DEBUG 后 continue，下一轮重启 300 秒 |
| 有效但不关心/被忽略的事件，process 返回 None | 下一轮重启计时 |
| 业务事件进入 send 背压 | 已离开 next 的计时；等待消费，没有该 300 秒保护 |
| 语义解析返回 Err / Binary / Close / WS 错误 | 返回错误，交由上层处理；不是继续同轮计时 |

没有证据证明“服务器用 Ping 保活所以 300 秒不触发”；该解释与这版 pump 实现不符。持续的未知文本可以重置计时，但历史没有文本类型记录来证明发生过。

## 4. 上次日志与过滤丢失

| 信号 | 原实现 | 上次能否保留 |
| --- | --- | --- |
| 普通流重试 WARN | codex_core::responses_retry | 该模块未单独开放，全局 error 会屏蔽 |
| 特殊 ConnectionFailed 重试 WARN | 同上 | 同样被屏蔽 |
| codex.retry | codex_otel.trace_safe 的 TRACE；含 retry.attempt/delay_ms/layer/operation | 上次 target=info，先被级别屏蔽；旧 EVENTS 白名单也不包含它，单独升日志级别仍会损失 |
| 第一次 WS retry 的界面通知 | release 构建 report_error 条件通常为 false | 首次重试可能没有 stdout 通知；不能据此排除重试 |
| 非法 JSON | WS 模块 DEBUG，原文包含 text | 上次模块 info，屏蔽；不应直接开启并保存正文 |
| idle timeout | ApiError::Stream，经错误映射/重试路径传播 | 不保证有一条被旧白名单保存的 stderr；on_ws_event 主要是 metrics，不等同日志 |
| 未知/忽略事件 | 可不转发 stdout；没有通用 INFO 逐帧信号 | 未记录不等于未发生 |
| 未识别的 WARN/ERROR/其他行 | 旧 project 返回 unclassified_line | 仅 wrapper observed_seconds 留下；level/module/固定错误分类丢失 |
| 已识别事件的错误 | 旧 project 只保留 timeout_mentioned 等白名单 | 不保留错误分类全文；无法还原精确错误路径 |

codex-client/src/retry.rs 62–81 的 record_retry 宏是本次新增找到的安全诊断入口。后续可仅开启该 target 的 TRACE 并把 codex.retry 的四个数值/枚举字段加入白名单，配合 WS parse_error/ignored 的无正文计数、队列 send 起止及 resolved timeout 快照。它可帮助验证重试，但单独仍不能覆盖首帧和 Ping/Pong，也不能靠调高 RUST_LOG 自动获得未实现的事件。

## 结论

根因未确定。本次发现的是可证明的计时范围、背压路径以及过去确实无法覆盖的重试/解析观测，不是复现了功能缺陷。

300 秒 idle + 一次可隐藏的重试 + 第二次等待，是与 600 秒外层终止相容的候选时间线；没有证据认定它实际发生。模型刷新存在 ModelsEtag 消费路径的代码关联，但与历史主请求停滞之间没有已证明的因果联系。没有启动模型、完整创建、Docker、候选恢复或 catalog 操作。

本次仅新增文档与静态证据，执行 JSON 有效性/await 索引一致性及 git diff 检查；没有将静态检查称为 Rust 运行时验证。

