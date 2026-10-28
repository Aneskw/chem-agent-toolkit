# RECAP planner 超时：新对话接手总报告

> 后续进展（2026-10-26 北京时间 19:20 后）：本次用户明确授权重新调试及最多三次串行对照。极小请求约 9.8 秒成功；原始完整 prompt＋修复后正式 schema 约 100.8 秒成功并通过完整计划验证，第三次对照未触发。历史超时根因仍未定位，Docker 业务验收未运行。新增预算/故障分类/计数修复、回归结果和架构分析见 [后续深度调试报告](timeout-deep-debug.md)。以下授权与“下一步”描述保留为上一轮历史，不能替代后续用户指令。
>
> 再后续（同日 22:00 后，提交 `6a4adf2`）：已用同一 CLI 二进制在本机回环环境证明 **WebSocket 的流空闲超时会被任意入站文本帧无限重置**（HTTP/SSE 不会），据此接入进度看门狗、OS 级读数与 `model_stalled` 分类；三次授权真实调用全部用完——第一次因本机代理/TUN 未生效而连不上后端（`workspace routing discovery timed out`），网络恢复后 HTTP/SSE 与 WebSocket 均在约 150 秒内完成传输（WebSocket 那份答案被计划语义校验拒绝）。Docker 业务验收仍未运行。详见 [Pipeline 超时机理、架构缺陷与修复](pipeline-timeout-architecture.md)。

更新时间：2026-10-26。本文汇总截至 `fb52bf6` 的已提交工作；本报告本身另作本地文档提交。**根因未确定；当前没有授权启动新的模型调用或全链路创建。**

## 1. 项目目标与当前状态

- 项目：`E:\Users\27343\Docker\chem-agent-toolkit-integration`。
- 分支：`integration/planner-timeout`。编写本报告前工作区干净，HEAD=`fb52bf6`；新对话必须重新核对实际 Git 状态、后续提交及适用 AGENTS.md。
- 最终目标：新版正常 CLI 完成固定 RDKit RECAP 任务，从来源准备、发现、编写、独立审阅、入口关联、模型环境规划、Docker 构建到完整业务验收和 catalog 晋升。
- 当前卡在 **planner 主请求本地发送完成之后，迟迟没有可用答案或 CLI 完成事件，外层 600 秒看门狗终止**。还不能定位到具体 CLI 内部等待点或服务端阶段。
- 第一轮曾正常创建成功：planner 约 101.8 秒，真实 Docker 业务 9/9 通过。旧产物在最终代码上重新验收、安装和迁移成功，但**不能代替最终版本正常新创建成功的证明**。
- 后续创建及受控诊断未返回 planner 答案，因此未进入本轮 Docker 或化学业务执行。`business_acceptance=not_run`，不能称为化学业务失败、无效计划或 JSON 校验失败。
- 已确定并修复 schema 共享引用污染；尚未确定它与全部超时的因果关系，也未发现另一个已复现且足以解释当前超时的本地功能缺陷。

## 2. 当前下一步：先维护方关联，暂不再跑

用户最后确定的顺序：

1. **先交维护方关联现有请求**，确认主请求是否到达、是否创建响应、是否发出业务事件。使用现有版本、哈希、UTC 窗口和客户端线程标识；本地 thread ID 未必能直接查询，必须明确限制。
2. **只有维护方明确无法关联，再准备最小诊断构建供批准**。不再仅调 RUST_LOG；不把尚未回复当作无法关联或批准。
3. 对应版本增加局部插桩，用独立诊断二进制，不安装覆盖原 CLI。先验证真实插桩点，再考虑下一次受控调用。二进制变化与插桩调度开销必须列为新增变量，其余条件保持不变。

**当前交接卡点：维护方接收渠道/已有工单链接尚未提供。交接文案已准备，但没有发送。** 上一对话已询问具体目标，不能猜测收件人或自行发到公开 issue。

可直接交付的文案：[`planner-maintainer-handoff.md`](planner-maintainer-handoff.md)。

最小脱敏附件：[`diagnostic-package.json`](../../validation/planner-retry-diagnostic/controlled/diagnostic-package.json)。不要默认附整个仓库、prompt、业务源码或完整日志原文。

## 3. 提交与实验沿革

| 提交 | 工作与结果 |
| --- | --- |
| `38bffa6` | native 传输异常及清理修复，属于前期基线 |
| `8c1cac8` | 明确来源引文必须为连续原文，未弱化来源要求 |
| `28879cf` | 最终验收与失败证据，含旧产物安装迁移证据及后续 planner 超时 |
| `42df02c` | 第四轮全新串行创建的超时证据，排除“必须并行才失败”的解释 |
| `16de30c` | schema 共享引用最小修复，44/44 针对性测试；相同 prompt 的一次真实诊断仍超时 |
| `48e1232` | Python 等待阶段观测及一次真实诊断，证明主请求本地 send 已完成 |
| `23c1c60` | 匹配版本入站观测能力核验、原型和 17 项测试；门槛不足，真实模型调用 0 次 |
| `cb8d2b5` | 静态 idle/retry/await/队列核查；真实模型调用 0 次 |
| `a355d23` | 用原版 CLI 本机模拟验证重试观测，再做唯一一次真实受控调用；仍超时，未证实隐藏重试 |
| `fb52bf6` | 准备维护方关联文案及后续诊断构建门槛；未发送、未构建、未调用模型 |

### 各次失败不是相同根因的证明

| 运行 | 主要事实 |
| --- | --- |
| 后续第二轮恢复、第三轮正常创建 | 均约 600 秒超时；北京时间 16:08:55 几乎同时断流，其中一个重连出现 WebSocket TLS handshake EOF。仅为当时链路异常证据，未唯一定位根因 |
| 第四轮全新串行创建 | 固定来源下载/SHA-256、真实最小模型调用、Docker Linux amd64、目录读写预检通过；无并行模型任务。发现、作者、内容审阅、入口关联和批准完成，作者生成 scripts/terminal_fragments.py；planner 16:45:45 启动，600.063 秒超时。stdin 约 0.14 秒写完，turn.started 1.791 秒；无 TLS/重连或本地 I/O 错误 |
| schema 修复后受控调用 | 北京时间 17:11:42 开始；600.045 秒超时。stdin 0.199 秒，thread.started 0.381 秒，turn.started 1.658 秒。模型列表刷新超时，但不能等同主生成请求失败 |
| 等待阶段受控调用 | 北京时间 17:39:12 开始；600.049 秒超时。WS 连接约 3.313 秒，预热完成；主 send 约 4.855 秒完成。三次模型列表 HTTP 200，无答案 |
| 最新重试专项受控调用 | UTC 10:39:45 开始，600.060 秒超时。仅一次主 send；没有记录到流 idle timeout、重试决策、codex.retry 或第二次主 send；三次模型列表 HTTP 200 |

## 4. 已确定的 schema 缺陷与修复范围

`creation_pipeline/runtime/planner.py` 定义共享字典 `S={"type":"string"}`，多个字段和 `arr(item=S)` 复用它。原来向 acceptance_json 原地添加 description，把完整验收说明传播到其他 PLAN 字符串字段及 PATCH 的 value_json。

修改前真实导入并保存了引用身份、说明路径和序列化 schema；不是仅凭描述修改。

最小生产修复：**用独立的 `{"type":"string","description":ACCEPTANCE_SPEC}` 替换 acceptance_json 节点**。不重写共享 schema 架构；保留完整验收说明及 PATCH 原本有意的顶层说明。

| 项目 | 修复前 | 修复后 |
| --- | ---: | ---: |
| PLAN 字节 | 151668 | 8568 |
| PLAN 验收说明次数 | 37 | 1 |
| PATCH 字节 | 20438 | 4538 |
| PATCH 验收说明次数 | 5 | 1 |
| ACCEPTANCE_SPEC 字符数 | 3889 | 3889 |

去掉说明注解后，约束结构完全相同，未修改类型、required、枚举、additionalProperties、范围、来源或锁定断言。新增回归修复前失败、修复后通过；相关四模块 44/44 通过。

**重要反证：第一轮成功 planner 使用相同污染 schema。修复后相同 prompt 仍超时。** 因此缺陷确定，但不能认定它是全部超时的唯一原因，也不能断言它对耗时完全无影响。

## 5. 已排查的超时可能原因：证据与边界

| 候选原因 | 已做核查 / 实验 | 当前判断 |
| --- | --- | --- |
| schema 膨胀与错误字段指令 | 引用身份复现、实际序列化对比、最小修复、约束等价测试、真实受控调用 | 缺陷已修；修复不足以消除超时，唯一根因不成立 |
| 并行模型任务争用或共同断流 | 检查早期同时失败与 TLS EOF；第四轮及后续诊断串行执行 | 并行不是发生此类超时的必要条件；早期共同故障仍未定因 |
| 一般网络/代理/TLS 问题 | 分离早期 TLS EOF、后续无 TLS 错误、实际 WS 连接及本地 send 成功 | 不能把全部超时归因网络；也不能凭无错误日志排除响应链路问题。没有擅改代理/认证 |
| 模型列表刷新超时阻塞主请求 | 区分独立 models 请求；后两次诊断三次 HTTP 200；检查 ModelsEtag 消费分支 | 刷新失败不是后两次超时的解释。代码确有 ModelsEtag → refresh_if_new_etag.await 路径，但无证据证明本次走此路径并堵塞 |
| 初始化、认证或第一次 WS 连接未完成 | 预检真实最小调用、前序创作完成；连接成功与主 send 时间戳 | 本次并非停在首次连接或主发送之前；不证明服务端已接收主请求 |
| stdin 未写完或未关闭 | 核查 run 线程、EOF；真实日志记录发送与关闭时间 | 已排除相应运行中的未写完/未关闭 |
| Python 管道死锁或读取线程错误 | stdout/stderr/输入独立线程；双向 200KB、读至 EOF、不读 1MB 输入等本地机制测试；实际后期 stderr 仍被消费 | 嫌疑降低；io_errors=[]，不能绝对排除所有 OS/CLI 内部阻塞 |
| CLI 已发终止事件但进程不退出 | 代码核查和模拟子进程复现；终止事件仅记录，仍等待退出 | 是已验证的监督边界；本次没有终止事件，因此不能解释本次失败。未猜测性改变成功语义 |
| 清理后 returncode=0 被误判成功 | 对比清理前 None、监督 timed_out、清理后 0 | 正确拒绝超时；清理后的 0 不构成模型成功 |
| 300 秒 idle → 隐藏重试 → 第二轮被 600 秒终止 | 静态定位缺失 WARN/TRACE；原版 CLI 本机模拟确实发出并保留 idle/retry/resend；再做一次真实诊断 | **最新真实运行未证实**：0 idle 类别、0 决策、0 codex.retry、仅 1 主 send。不能据此解释该次 600 秒，也不回推历史 |
| Ping/Pong 保活不断重置 300 秒 | 核对精确版本 WS pump | 该解释与代码不符：Ping/Pong 在底层处理，不交给上层 next，因此不重置其 idle 计时 |
| 未知/非法文本不断重置 idle | 精确版本解析循环：非法 JSON continue、忽略事件返回 None 后再进入 next | 代码允许；实际没有逐文本分类/计数，未证实 |
| API / mapper / core 消费者背压 | 核查队列容量、send/reserve await、消费者 Drop/cancel | 代码允许离开 idle 覆盖区后等待消费；没有队列占用或任务栈证据，未证实 |
| 实际有效 idle 配置不同 | 用户配置白名单、历史命令及默认值核查 | 静态支持 300 秒；没有 CLI 最终合并配置回读，不能把重建值当运行时确证 |
| 服务端排队、复杂结构化生成耗时、服务端异常 | 固定输入和模型不变；缺少远端 ID/首业务事件/服务端状态 | 仍无法区分；没有证据足以单独归因规划复杂度或服务端 |
| 计划格式、来源、入口或业务断言有误 | 校验逻辑保留；等待真实答案才能执行 | 未返回答案，未进入这些校验；不能把超时判为计划或化学业务失败 |

## 6. 精确版本静态发现：不要重复误读

CLI：`0.164.0-alpha.11.1`。

路径：`C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.EXE`。

SHA-256：`1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`。

源码使用 `rust-v0.164.0-alpha.11.1`，不能换用 main 或其他版本来断言行为；猜测路径曾返回 404，未作为证据。

- 默认 stream_idle_timeout=300 秒，连接 timeout=15 秒。前者包裹单次发送/等待下一上层消息，不是整轮总时限。
- 默认 stream_max_retries=5；request_max_retries=4，HTTP 代码实际包含初次共最多 5 次尝试。不能把 HTTP 预算直接乘进已建立 WS 的每次 send。
- 特定 Sampling + ConnectionFailed + 非 internal + 非 Bedrock 条件有默认开启的无固定次数连接重试，5 秒起倍增至 60 秒；普通流预算在传输回退时可能清零。
- 命令队列容量 32；原始入站转发队列无界；API 事件及 mapper → core 队列各 1600。
- API producer 的 send/reserve、mapper send、core 消费处理没有统一 300 秒保护。消费者“活着但不 poll”不等于 Drop；仅前者可能持续背压而不触发 closed。
- core ResponseStream Drop 会取消 mapper；producer 观察消费者关闭；失败时 socket Drop abort pump，不等待优雅 close。
- 非法 JSON 或忽略文本可重启 next 的计时；语义错误返回 Err 则交给上层重试；Ping/Pong 不重启上层计时。
- 静态证据记录了审查范围内 83 个直接 await 及 select 等待源码；不声称递归穷举整个 CLI 的所有辅助函数。

## 7. 观测工作做到哪一步

### 旧观测为什么不足

- thread.started / turn.started 是 CLI 级事件，不证明服务端已接收或开始生成。
- `record_websocket_event` 主要写 metrics；Ping/Pong 在低层就被处理。提高 RUST_LOG 不能创造不存在的逐帧信号。
- 旧日志全局 error 屏蔽 responses_retry WARN；codex.retry 是 TRACE，上次 trace-safe=info 不收；旧脱敏白名单也不识别它。
- 旧未知行只剩 unclassified_line 和时间，丢失级别、模块及错误类别。旧记录不能重新还原原文。
- `codex.sse_event` 的 `response.completed` 也用于失败记账，不能单独当作远端完成；最新投影保留 error_present/error_class。

### 已完成的新增观测与测试

1. `model_call.py` 增补 stdin 关闭、终止事件、监督结束、清理前后退出码等观察，未擅改完成判定。
2. 入站逐帧原型有 17 项本地测试，但没接入原版 CLI producer；不能把原型通过当真实可观测。该轮按门槛停止，0 次真实调用。
3. 最新局部采集器开放 responses_retry WARN 与 trace-safe TRACE，保留固定 idle 类别、retry.attempt/delay_ms/layer/operation、连接/发送完成、UTC/单调时间、未知日志级别与白名单模块。
4. 使用同一原版 CLI 连接 127.0.0.1 模拟服务，独立临时 CODEX_HOME、合成输入、250ms idle、2 次 retry。真实 CLI 自己产生空闲超时、重试、重连、3 次主 send；模拟服务独立确认收件。**不是只测试手工日志字符串，也不是远端模型调用。**
5. 8 项探针检查通过，41 行实际日志逐行敏感哨兵过滤通过；9 项 model_call 监督回归通过。已有 websockets 10.4，未安装依赖。
6. 默认沙箱曾影响本地探针/测试临时目录；探针走平台操作审批，测试限定工作区临时目录后通过。这些是本地环境问题，不当作 RECAP 网络根因。

仍缺：最终有效配置值、接收等待进入/退出、入站消息分类与解析类别、队列发送等待与消费、日志丢弃计数、可查询的远端 response/request ID。

## 8. 最新真实实验：维护方关联所需事实

| 项目 | 值 |
| --- | --- |
| 对应提交 | `a355d23` |
| UTC 时间窗 | `2026-10-26T10:39:45Z` 至 `2026-10-26T10:49:46Z` |
| 客户端 thread_id | `01a177cb-7841-7571-ba02-0f830c65e333` |
| 远端 request_id / response_id | 均未取得；本地 thread ID 未必可索引 |
| stdin 完成并关闭 | run 起点后 0.279 秒 |
| thread.started / turn.started | 0.481 / 1.335 秒 |
| WS 连接完成 | `10:39:47.499256 UTC` |
| 预热 send 完成 | `10:39:47.508519 UTC`，warmup=true |
| 主 send 完成 | `10:39:48.983022 UTC`，warmup=false，success=true，duration_ms=1 |
| 主 send 开始 | 无独立日志，完成时间减耗时仅是估算 |
| 主流 idle timeout / retry decision / codex.retry | 0 / 0 / 0 条 |
| 主 send 数量 | 1；无第二次主发送/重连记录 |
| 最终结果 | timed_out，600.060 秒；监督结束 600.008，清理 0.052 |
| 清理 | stream_threads_finished=true，io_errors=[] |
| stdout / stderr | stdout 仅两个启动事件；stderr 30 条脱敏记录 |
| 材料完整性 | 调用前后均通过 |

**最后已证明阶段是客户端主 send 完成。外层最终等待子进程退出到期。既没有证据证明第二轮等待，也没有证据证明服务端没生成。**

诊断时钟 observed_seconds 起于采集器初始化，和 run elapsed 起点不同；CLI UTC 是发出日志时间。跨日志比较应使用明确时钟，不能直接混合小数秒。

## 9. 固定输入、原始现场与校验要求

所有修复后真实诊断都使用第四轮保存的相同 planner prompt 和修复后的 schema：

- 模型 `gpt-6-astra`，reasoning `medium`，service tier `default`，单次外层限制 600 秒，串行。
- prompt：41695 字节，SHA-256 `8af7e4416549cc30a3499000baf53293745efd82920ccbcc2bb1b0e7ba0bc9d9`。
- 修复后 schema SHA-256：`cbadd6d58b818812ef8672da6ad09664a1fdd1511a69e722d10cb999094f1ea4`。
- 污染 schema SHA-256：`67e030bfdf6c8a9690a7b3d3926917834e43e41e602e3b68780d8f20f6147671`，第一轮成功与第四轮失败均使用过。
- 当前用户配置曾为 low，诊断仅对子进程显式设 medium/default；不改用户全局配置。
- 第四轮原现场：`E:\Users\27343\Docker\final-recap-codex-4\state\runs\20261026T163755-8844c416\runtime-preparation\rdkit-recap-terminal-fragments\ec03b83616df43a7960b49cb27c6c77b\materials\planning\0`。
- 归档：项目 `validation/final-single-retry/run-snapshot/` 下的相同相对路径。原目录变化时以归档与 inventory 为准。
- controlled_call.py 验证 prompt/schema 哈希、handoff inventory 及文本；若有答案，先保存原答案，再执行 jsonschema 和 preparation.validate，覆盖计划、来源、入口及验收完整性。JSON 或 action=read 不等于有效计划。

## 10. 新对话建议阅读顺序与证据索引

先读本文，再按需要读以下文件，避免从头重跑创建来“恢复上下文”：

| 内容 | 项目内路径 |
| --- | --- |
| 维护方可提交文案与条件门槛 | docs/integration/planner-maintainer-handoff.md |
| 最新实验报告 | docs/integration/planner-retry-diagnostic.md |
| 最小维护包 / 完整脱敏现场 | validation/planner-retry-diagnostic/controlled/diagnostic-package.json / 同目录 model-0 |
| 原版 CLI 本机探针与结果 | validation/planner-retry-diagnostic/local_cli_probe.py、local-probe.json |
| 最新过滤器与真实调用脚本 | validation/planner-retry-diagnostic/diagnostics.py、controlled_call.py |
| 静态 await/预算/队列报告及源码 | docs/integration/planner-static-await.md；validation/planner-static-await/source-excerpts.json |
| 入站观测能力门槛 | docs/integration/planner-frame-gate.md；validation/planner-frame-gate/ |
| 首次发送阶段定位 | docs/integration/planner-wait-stage.md；validation/planner-wait-stage/controlled/ |
| schema 缺陷与修复证据 | docs/integration/planner-schema-isolation.md；validation/planner-schema-isolation/ |
| 第四轮串行正常创建 | docs/integration/final-single-retry.md；validation/final-single-retry/summary.json、normal-build.log、run-snapshot/ |
| 更早验收与旧产物边界 | docs/integration/final-continuation.md；validation/final-continuation/ |
| 生产实现 | creation_pipeline/runtime/planner.py、model_call.py、network.py、runner.py；creation_pipeline/agent/command.py |

## 11. 授权与不可越过的边界

- 新对话开始先核对 Git/AGENTS；不覆盖未提交改动，不回退历史，不改 partner，不删历史失败记录或共享镜像。
- 不重跑完整创建、不恢复候选、不写 catalog、不执行 Docker 或宿主化学业务、不安装宿主业务依赖。
- 不人工提供正确计划、Dockerfile、业务代码或断言；不弱化来源、入口和验收约束。
- 不擅改全局代理、认证、配置、模型、服务层级、传输或超时，不关闭 TLS 校验，不做中间人解密。
- 不采集 token、认证头、cookie、完整环境/头部、请求响应业务正文；仅固定类别及白名单非认证 ID。
- 不推送、不发布、不合并远端 PR；必要代码、测试、文档及证据本地提交。维护方发送需明确渠道，当前未发送。
- 最新一次真实调用授权已用完，失败后已停止；**没有自动追加调用授权**。
- 若维护方无法关联，先提出最小对应版本插桩构建并获得批准；独立二进制先本地验证，不覆盖安装。真实调用还要确认门槛和授权，不能将本地测试通过自动视为许可。
- 即使将来受控诊断成功，也不等于正常新创建验收成功；最终验收仍须以后由正常流程独立完成。

## 12. 可直接复制到新对话的开场

> 请先阅读 E:\Users\27343\Docker\chem-agent-toolkit-integration\docs\integration\recap-planner-handoff-summary.md，并核对实际 Git 状态、后续提交及 AGENTS.md。当前根因未确定；schema 污染已修，最新一次真实诊断仍在 600.060 秒超时，已验证可采集的 idle/retry 信号没有出现，不能宣称隐藏重试得到证实。请先协助维护方关联现有请求：确认接收、响应创建和业务事件发送。交接材料已备但尚未发送，接收渠道待提供。本地 thread ID 未必能查询。只有维护方明确无法关联后，才准备对应版本最小诊断插桩供批准，使用独立二进制并先本地验证。不要再跑模型、完整创建、候选恢复或 Docker，不改全局配置；需要新增调用时另行确认授权。
