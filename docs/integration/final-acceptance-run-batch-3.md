# Batch-3 执行结果

提交 `d40da69`，input `validation/final-acceptance-review/input-batch-2.json`（SHA-256 `455767d2…85b8`），隔离目录 `E:\Users\27343\Docker\final-acceptance-b3-20261027T003942Z\`。证据：`validation/final-acceptance-run/batch-3/`。

## 最终状态：blocked，原因 = 模型传输（规划阶段超时）

| 项 | 结果 |
| --- | --- |
| 显式 binding | **通过**：`scripts/terminal_fragments.py`、`association=explicit`、`source_id=recap`、`source_path=document.py`、引文 `>>> res = Recap.RecapDecompose(m)`，歧义门禁未触发 |
| discovery | completed，143.2 秒 |
| author | completed，207.8 秒 |
| review | completed，66.6 秒 |
| 环境规划（planner） | **timed_out，600.01 秒**，分类 `model_unavailable` / `model_transport`（repair_lane=environment） |
| 账本 | 4/8，预算未耗尽，无续批 |
| Docker 构建 | **0 次**，`image_id=null` |
| 业务验收用例 | **0 条执行**（not_run） |
| library 查询 / install | **not_run** |
| 门禁 | 未触发（未到 Docker） |

## 规划调用的观测（本轮关键证据）

审计目录：`state/runs/20261027T083947-4ecbebbc/runtime-preparation/…/materials/planning/0/model-0/`

| 项 | 值 |
| --- | --- |
| 传输 / 设置 | https / medium / default（`request.json` 记录） |
| prompt | 44718 字节 |
| 硬超时 | 600 秒 → 实际 600.01 秒被杀 |
| 观测模式 | `observe`，观测窗口 240 秒 |
| `progress_limit_exceeded` | **true** |
| 最长静默 | **365.4 秒**（远超 240 秒） |
| `inbound_activity_seen` | **true** |
| 进程读数 | read_bytes 增长 75.6 MB、write 0.93 MB、CPU 2.86 秒、300 个采样 |
| stdout / stderr | 6 行 / 3 行，最后一条 stdout 在 547.1 秒，stderr 在 551.9 秒 |
| 终止事件类型 | `error` |
| 清理 | 无 `cleanup_wait_expired`，进程树已回收 |

**这是历史那种“600 秒静默”第一次带着仪表被重放出来**：stdout 静默 365 秒、期间仍有入站读活动、CLI 最后发的是 error 事件、600 秒内没有可用答案。它解释了为什么历史上 CLI 自带的空闲超时没有救场，也说明“仅延长超时”不会有用。

边界：`inbound_activity_seen` 只证明存在至少一个 2 秒窗口读到 ≥4KB；`read_bytes` 也包含文件读取，所以**不能**据此断言“对端持续在推流”。服务端原因仍未定位。

## 未执行（如实标记）

Docker 构建、全部业务验收用例、`library` 查询、`install` 均为 `not_run`；门禁未触发——因为根本没走到 Docker 阶段。预算是 4/8 用尽后自然停止，**不是**预算耗尽型 `partial`。

## 这批证明了什么

- 显式 binding 在正常 build 里端到端可用，入口歧义门禁不再误伤；
- 三个 agent 阶段在固定 https/medium/default 下稳定完成；
- 规划阶段的停滞被**观测到并可区分**：静默超窗、有入站活动、CLI 报 error、600 秒无答案——与历史症状同形；
- 失败被正确归类为传输问题，而不是计划或内容缺陷；没有降级、没有重试、没有契约修正。

## 这批不能证明什么

固定案例**没有通过**：没有任何业务证据。与历史超时根因仍只到“同形复现”，没有服务端归因；没有性能结论；不能作为任何版本“可合并”的依据。三次 batch 各自独立记账，不能互相引用。
