# P1 合成流矩阵：结果（控制场景已绿）

固定 CLI `1103e9e0…58a098`、回环端点、合成输入、独立临时 `CODEX_HOME`、`requires_openai_auth=false`、**零模型调用**。结果目录：`validation/planner-attribution/p1-20261027T014335Z/results.json`。

控制场景 `complete_sse` 已通过（`thread.started → item.completed ×2 → turn.completed`，退出码 0），因此矩阵有效。

## 结果表

| 场景 | 破坏的维度 | CLI 报告 | 退出码 |
| --- | --- | --- | --- |
| `complete_sse`（控制） | 无 | — | 0 |
| `silent_after_headers` | 发头后静默（无 completed） | `error decoding response body` | 1 |
| `truncated_mid_stream` | 响应体在 completed 前截断（短 Content-Length） | `error decoding response body` | 1 |
| `missing_completed` | 事件完整但缺 `response.completed`，正常收尾 | `stream closed before response.completed` | 1 |
| `completed_then_abrupt_close` | 已发 completed，随后不写完 chunked 收尾 | **成功** | 0 |
| `completed_then_truncated_message` | 已发 completed，随后截断 HTTP 消息体 | **成功** | 0 |
| `invalid_json_event` | 一条非法 JSON 事件 + 正常 completed | 成功（记一条 `Failed to parse SSE event`） | 0 |
| `bad_chunk_framing` | 错误 chunk 长度声明 | **成功** | 0 |
| `corrupt_gzip` | `Content-Encoding: gzip` 但体不是 gzip | `UTF8 error: invalid utf-8 sequence…` | 1 |

## 可以得到的结论（有边界）

1. **`error decoding response body` 只在“`response.completed` 之前的响应体被中断”时出现**（静默未收尾、completed 前截断两个场景）。它是“响应体在业务完成之前结束”的相容解释。
2. **一旦 CLI 收到 `response.completed`，后续 HTTP 消息体的截断或异常关闭不再影响判定**（两个“completed 后破坏”场景仍成功）。所以“HTTP 消息完整”不是 CLI 的硬要求，业务完成事件才是。
3. **各类错误的文本互斥**：缺 completed → `stream closed before response.completed`；编码损坏 → UTF-8 错误；非法 JSON 事件 → 记一条解析失败但继续成功。因此**错误文本可用于粗分流**，但见下。
4. `bad_chunk_framing` 在我的构造下仍成功，说明该场景没有真正破坏 framing（我的 `ffff` 长度声明与实际字节一致地提前关闭，被当成结束）。**该行不构成“framing 错误可被容忍”的结论**，需重做。

## 不能得到的结论

- 不能反推线上只能由“completed 前截断”造成：合成矩阵只是**充分性**演示，不是必要性证明；中间网络、代理、服务端都可能在更复杂形态下产生同文本。
- `invalid_json_event` 的 `Failed to parse SSE event` 说明该文本也可能来自无害事件，**不能**单独当作流损坏证据。
- 本矩阵不涉及 TLS 层（HTTP 以上）、不涉及真实认证、不涉及真实后端。

## 与 batch-3 的对照（只写相容，不写因果）

batch-3 规划调用的实际错误正是 `error decoding response body`（4 次重连），且始终未收到 `turn.completed`。与本矩阵第 1/2 行**相容**：即“响应体在业务完成前结束”。仍不能判定是谁结束的（服务端、中间层、代理或 CLI 解码路径）。

## 复现

```powershell
python validation/planner-attribution/p1_stream_matrix.py            # 全部场景
python validation/planner-attribution/p1_stream_matrix.py complete_sse  # 单场景
```
