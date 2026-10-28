# P1 合成流矩阵：状态与结论边界

## 结论先行

**矩阵目前无效，不得用于任何归因。** 控制场景（`complete_sse`，完整合法事件流）自身没有通过（exit 1、两个 `error`、`turn.failed`），因此其余场景的错误文本不能说明任何因果关系。

## 已建成的部分

`validation/planner-attribution/p1_stream_matrix.py`：

- 只绑定 `127.0.0.1`，独立临时 `CODEX_HOME`，合成 prompt/合成 schema，`requires_openai_auth=false`，无任何凭据；
- 用真实 CLI（SHA-256 `1103e9e0…58a098`）打本机端点，每个场景记录：命中的错误类别、stdout 事件序列、退出码、是否被外部杀掉、耗时；
- 场景维度按方案 §2 拆分：HTTP 消息完整性（`short_length`）、chunk framing（`bad_chunk`）、内容编码（`corrupt_gzip`）、SSE 协议（`missing_completed` / `invalid_json_event`）、连接关闭（`completed_then_abrupt_close` / `truncated_mid_stream`），并单列“completed 后截断”。

已修正的两个夹具缺陷（都属于“夹具错、不是 CLI 错”，记录下来避免以后误读历史结果）：

1. 早期版本不回读请求体就应答，导致客户端写入被打断，所有场景都伪造出 `decode_body`；
2. 早期版本缺少 `event:` 行与 `[DONE]` 终止标记。

## 当前失败点

修复上述两点后，`complete_sse` 不再报 `decode_body`，但仍以两个 `error` + `turn.failed` 结束（exit 1）。本轮继续推进得到三个结论，都指夹具、不指线上：

1. **应答顺序是原因之一**：必须先读走请求体（`Content-Length`）再应答，否则客户端写入被打断，所有场景都会伪造 `decode_body`。已修。
2. **`response.output_item.done` 才是助手消息的载体**：依据固定版本 `codex-api/src/sse/responses.rs::process_responses_event`，`response.completed` 只提供 id/usage，消息文本来自 `output_item.done` 里的 `ResponseItem`。加入该事件后 stdout 出现 `item.completed`，但仍有一条事件解析失败（`Failed to parse SSE event`）。
3. **仍有一条事件与 `ResponsesStreamEvent` 不匹配**：事件序列已最小化为 `created → item.done → completed → [DONE]`，解析失败依旧，说明失败点在这三者之一，而不是原先的 delta/added。

## 下一步（继续 P1，不消耗模型调用）

1. **逐事件探针**：分别只发 `created`、只发 `item.done`、只发 `completed`（各带 `[DONE]`），定位哪一条触发 `Failed to parse SSE event`。脚本已有单场景模式（`python p1_stream_matrix.py <scenario>`），只差登记这三个探针场景。
2. 依失败项对照 `ResponsesStreamEvent` 字段定义（是否 `deny_unknown_fields`、`response`/`item` 结构要求）修正。
3. 直到 `complete_sse` 绿色（`{"ok": true}` + `turn.completed` + 退出码 0），其余八个场景才有意义。
4. 有效后才判定“哪种破坏能复现 `error decoding response body`”，并且只写“与 X 相容”，不写“即 X”。

**本轮到此停止**：不是被阻塞，而是逐事件探针需要再改脚本结构，属下一轮 P1；不在本轮硬凑结论。


## 安全与成本

本轮零模型调用；端点仅回环、合成输入、无凭据；未改系统信任库、未做 MITM。P2 仍需单独批准。
