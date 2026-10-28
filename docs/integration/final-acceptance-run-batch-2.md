# Batch-2 执行结果（已按离线回放更正）

提交 `6100723` 运行，input SHA-256 `455767d2…85b8`，隔离目录 `E:\Users\27343\Docker\final-acceptance-b2-20261027T002657Z\`。原始证据：`validation/final-acceptance-run/batch-2/agent-turn-001-events.jsonl`（该轮 events.jsonl 原样副本）。

## 更正后的事实

**discovery 这一轮本身是成功的**：事件流里有 `thread.started` → 若干 `item.completed`（含工具执行与 agent_message）→ 一条 `error`（`Reconnecting... 1/5 (stream disconnected before completion: Transport error: network error: error decoding response body)`）→ 更多工具执行 → 最终 `agent_message` → **`turn.completed`**，进程退出码 0。

原始记录里的“失败”是**我们的监督器误判**：它把任何 `error` 事件都当终止性错误，于是 CLI 自行重连成功、答案与 `turn.completed` 都到了，仍被判 `Incomplete Agent turn` 并中止整批。

## 因此本批的真实状态

| 项 | 状态 |
| --- | --- |
| discovery | **完成**（有有效最终答案与 `turn.completed`，退出码 0） |
| 账本 | 1 次调用（上限 8） |
| 入口 binding 评估 | not_run（发现阶段之后未继续） |
| Docker 构建 | 0 次，`image_id=null` |
| 业务验收用例 | 0 条执行 |
| `library` 查询 / `install` | not_run |
| 门禁 `stop_on_runtime_failure` | 未触发（未到 Docker） |
| 整批结论 | **未通过**：固定案例没有走完，也没有任何验收证据 |

**这不是整批通过**，也不是模型/传输失败；是一次被自身缺陷提前中止的运行。

## 修复（提交见文末）

`records.is_recoverable_notice()` 区分两类事件：

- 可恢复提示：`Reconnecting...`、`Falling back from WebSockets to HTTPS transport` —— 记入 receipt 的 `stream_notices`，不作为终止错误，也不计入工具违规；
- 终止性错误：其余 `error` / `turn.failed` —— 仍然失败。

两条监督路径（agent `NativeSession.stage` 与结构化 `model_call.call`）都改；`item.completed{item.type=error}` 也按同一规则区分。回归覆盖你要求的五类：恢复成功、重连未恢复、终止失败、缺少有效答案、非零退出，另加 batch-2 事件流的离线回放（回放证明该序列不再因重连被判失败；在结构化路径上它仍因工具执行被拒，这是正确行为）。

## 不能证明的事

没有 Docker、没有任何业务用例执行、没有 accepted、没有安装；与历史 600 秒超时根因无关；没有性能结论；不能作为“可合并”依据。
