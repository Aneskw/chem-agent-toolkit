# Batch-4 受控对照：只改规划传输

与 batch-3 相比**只动一个变量**：规划阶段的传输改为 `default`（用户 provider），其余全部保持——显式脚本 binding、agent 阶段 `https`、medium/default、8 次账本、600 秒单次、3600 秒总预算、240 秒仅观测、运行时失败门禁。

- 提交：`d40da69`
- input：`validation/final-acceptance-review/input-batch-4.json`，SHA-256 `aa71d067…86a7`
- 运行目录：`E:\Users\27343\Docker\final-acceptance-b4-20261027T010520Z\`

## 实际传输（已记录）

| 阶段 | 传输 | 证据 |
| --- | --- | --- |
| discovery | `https` | `agent-turns/001-discovery/command.json`，argv 内含 `model_provider=planner_https` |
| author | `https` | 同上，002 |
| review | `https` | 同上，003 |
| runtime_planning | **`default`** | `planning/0/model-0/request.json` 的 `transport` 字段 |

## 结果：与 batch-3 同形，仍然 blocked

| 项 | batch-3（规划 https） | batch-4（规划 default） |
| --- | --- | --- |
| 规划调用 | timed_out **600.01 秒** | timed_out **600.09 秒** |
| 最长静默 | 365.4 秒 | **593.7 秒** |
| stdout 行数 | 6 | **2** |
| 最后终止事件 | `error` | **无** |
| 归类 | `model_unavailable` / `model_transport` | 同 |
| 账本 | 4/8 | 4/8（150.5 / 239.5 / 83.4 秒 + 规划超时） |
| Docker 构建 / 业务用例 / 查询 / 安装 | 0 / not_run | 0 / not_run |

## 结论

**规划阶段的停滞与传输选择无关。** 两种传输都撞满 600 秒硬上限，静默都超过 240 秒观测窗口。差别只在“吵闹程度”：`https` 下 CLI 在 547 秒左右报了一个 error 事件，`default` 下几乎完全沉默（只有 2 条 stdout、无终止事件）。

因此：
- 换传输不是解法，也不该成为降级手段；
- 历史那种“600 秒静默”在当前环境下**可以稳定复现**，且不是 HTTPS/SSE 路径特有的；
- 下一步要看的是链路/服务端（或换时段、换网络路径重测），而不是继续调传输参数。

## 未执行（如实标记）

Docker 构建、全部业务验收用例、`library` 查询、`install` 均为 `not_run`；门禁未触发（没到 Docker）。预算是 4/8 后自然停止，**不是**预算耗尽型 `partial`。

## 不能证明什么

固定案例**没有通过**，没有任何业务证据。两次样本不能排除间歇性外部原因，只能说明“传输选择不是判别因素”。没有服务端归因、没有性能结论、不能作为任何版本可合并依据。
