# P2：一次固定 planner 请求的结果

按批准的额度执行：**一个已保存的固定 planner 请求，一次应用层启动**，不重跑发现/作者/审阅。目录 `validation/planner-attribution/p2-20261027T015833Z/`。

| 项 | 值 |
| --- | --- |
| prompt SHA-256 | `8af7e441…0bc9d9`（归档固定请求，运行时校验） |
| schema SHA-256 | `cbadd6d5…f1ea4`（修复后正式 schema） |
| CLI | `0.164.0-alpha.11.1`，SHA-256 `1103e9e0…58a098` |
| 传输（实际） | `https`，记录于 `request.json` 的 `transport` |
| 设置 | reasoning `medium`、tier `default`（记录于 `requested_model_settings`） |
| 超时 | 600 秒硬上限；进度窗口 240 秒，`observe`（只记录） |
| 应用层启动次数 | 1 |
| 结果 | **timed_out，600.15 秒**，无答案 |
| 本地线程 ID | `01a17b14-cecd-7410-a925-4ccee6b083d8`（`thread.started`，可用于向维护方关联时间窗） |

## 阶段时间线（P0 五类时间线首次用于真实调用）

| 时间线 | 值 |
| --- | --- |
| 首个 stdout 事件 | 2.296 秒（`thread.started`） |
| 生成进度（最后一个生命周期事件） | 2.315 秒（`turn.started`） |
| 重连/通知 | **无**（`last_notice_seconds=null`，本运行 stderr 无 `Reconnecting`） |
| 终止事件 | **无**（`terminal_seconds=null`） |
| CLI 活动（任意输出） | 至 546.056 秒仍有 stderr 行 |
| 进程退出 | 600.089 秒（外部终止），`io_errors=[]`，读线程正常收尾 |
| 静默窗口 | 超过 240 秒（`progress_limit_exceeded=true`） |
| 进程 I/O 增长 | `process_io_growth_seen=true`（**仅旁证，不作进度**） |

## A1 的结论：该版本在规划路径上不输出请求 ID

即使把 `codex_otel.trace_safe=trace`、`codex_api=debug`、`codex_core::responses_retry=warn` 全开，本次 stderr 中**没有**出现可提取的 request/response ID（`ID_PATTERN` 命中 0 次），只有 `codex.api_request`（models）、`codex.conversation_starts`、`codex.startup_phase` 等事件。

因此：
- **A2 不能靠 request_id**；可交付给维护方的是 **UTC 时间窗 + 本地 thread_id + 精确的启动/终止时刻**。
- 若要拿到可查询 ID，需要维护方指点该版本在哪个日志目标/级别会输出，或改用有其支持的诊断构建；这属于外部输入，不在本轮自造。

## 与 batch-3 的对照（只描述，不归因）

| | batch-3（2026-10-27 08:39） | P2（2026-10-27 01:58） |
| --- | --- | --- |
| 传输 | https | https |
| stdout | 6 行，含 4 条 `error`（`error decoding response body`） | **2 行，零重连/错误事件** |
| 终止事件 | `error` | 无 |
| 结果 | 600 秒超时 | 600 秒超时 |

同一固定请求在两种形态下都超时：一次是“有响应体解码失败并反复重连”，一次是“完全静默、无任何重连提示”。这说明**停滞至少有这两种表现**，不能用单一机制（如仅 WS idle、仅解码失败）解释全部。

## 不作结论

不据此判定根因；不把 `process_io_growth_seen` 当作“对端仍在推流”的证据；不声称错误文本互斥；不把本次静默形态推广到历史所有超时。
