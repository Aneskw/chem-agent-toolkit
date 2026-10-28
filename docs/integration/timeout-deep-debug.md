# Pipeline 超时深度调试与架构审查（2026-10-26）

> 第二轮（同日稍后）：已用同一 CLI 二进制 + 回环服务器证明 WebSocket 模式的流空闲超时会被任何入站文本帧无限重置，而 HTTP/SSE 不会；并把进度看门狗、OS 级计数采样和 `model_stalled` 分类接入生产代码。新的真实调用暴露出本轮的直接原因在本机网络路径（`workspace routing discovery timed out`）。详见 [Pipeline 超时机理、架构缺陷与修复](pipeline-timeout-architecture.md)。以下为第一轮记录。

## 结论先行

历史 600 秒超时的唯一根因仍未确定，但本次已在不提高超时、不换模型、不弱化正式 schema 的条件下，重跑原始请求成功。不是仅返回 JSON：完整答案通过 jsonschema 和 preparation.validate，得到 5 个有效用例。没有执行 Docker，business_acceptance=not_run，也没有修改 catalog。

本轮起点提交 5d3be31，工作区干净，未发现仓库 AGENTS.md。交接文档中的上一轮暂停安排只作为历史；本次用户明确要求深度调试和重跑，并明确批准最多三次串行对照实验。

## 本次真实实验

结果目录：`validation/timeout-deep-debug/matrix-20261026T111805Z/`。

| 条件 | 极小请求 | 正式完整请求 |
| --- | --- | --- |
| CLI | 同一 0.164.0-alpha.11.1 二进制 | 相同 |
| 模型 / reasoning / tier | gpt-6-astra / medium / default | 相同 |
| 外层上限 | 600 秒 | 600 秒 |
| 结果 | ok=true；9.779 秒 | 有效 plan；100.846 秒（包含本地验收） |
| usage | 见 minimal/receipt.json | input 24991，output 3033，reasoning_output 134 |
| 业务验收 | 未运行 | 未运行 |

完整请求 prompt SHA-256：`8af7e4416549cc30a3499000baf53293745efd82920ccbcc2bb1b0e7ba0bc9d9`。
正式 schema SHA-256：`cbadd6d58b818812ef8672da6ad09664a1fdd1511a69e722d10cb999094f1ea4`。
CLI SHA-256：`1103e9e09c71fa2cd0afd6d8f3b9a2d63174fe8efd7cb5bd09f1cb14ef58a098`。

完整请求北京时间 19:18:15 启动，主 send 日志为 UTC 11:18:19.165104，turn.completed 在进程起点后 99.303 秒，进程正常退出约 100.736 秒，退出码 0，无 I/O 错误，工具事件为空。调用前后原始材料及文本核验通过。采集器与进程监督时钟起点不同，不混用其小数秒。

第三次“简化 schema”实验只在完整请求超时时运行；本次未满足条件，因此没有运行。成功不能证明某一种 schema 替换有效。

最初沙箱内两次尝试均在约 0.1 秒退出，未发出 thread.started；另行 CLI --version 检查显示用户 arg0 临时目录 access denied。这是启动环境问题，不能冒充模型超时。保留在 `validation/timeout-deep-debug/matrix/`。平台批准沙箱外执行后，上述两个实际模型调用完成。没有修改用户配置或复制认证材料。不能把沙箱临时目录问题反推成历史超时根因。

### 成功的因果边界

诊断直接调用 model_call.call，未经过本轮修改的 planner.plan 或 prepare；model_call 的生产修改只有错误类型元数据，不改变发送、等待或清理。因此成功不能归功于本轮预算/计数修复。相同固定输入有成功也有失败，反对“输入必然导致确定性死锁/必然需要超过 600 秒”的解释，但仍允许输入复杂度与暂态负载、连接或服务行为共同作用。

进程 cwd/TEMP 使用本次工作区独立目录；运行时间和远端状态也不同。未记录远端 request/response ID、任务栈或最终有效配置，不能宣称所有运行时条件完全相同。

## 已复现并修复的本地缺陷

### 1. 失败调用计数为零，故障被归成输入问题

原 prepare 仅在 propose 成功返回后统计 receipt 文件。planner 发出请求后超时，计数仍为 0；ModelUnavailable 和入口关联直接抛出的 ModelExecutionError 没有分类字段，落入 plan_unresolved / unresolved_input。

修复：在外部 call_guard 接受后记录 admitted invocation attempt，覆盖关联、关联审阅、规划和失败；guard 拒绝不计数。两个模型传输错误类型提供 model_unavailable / model_transport，保留内容审批状态及原异常，不触发业务代码修改。model_calls 是获准尝试数，不是服务端接收数或成功数；guard 返回后若预算过期，该尝试可能尚未启动子进程。

这修复的是可观测性和分类。原 pipeline 已有外层 session receipts 计数，并非所有模型预算都失效；也没有证据表明旧分类已实际导致自动修改业务源码。

### 2. planner 沿用过时剩余预算，并把不足 1 秒扩为 1 秒

原循环在 prompt 构造、落盘、guard 前计算 remaining，调用时使用旧值与 max(1, int(...))。确定性测试让 guard 消耗完预算，原实现仍进入 model_call；修复后在发送前重新核验，保留浮点剩余预算，不把 0.25 秒扩大为 1 秒。

此修复约束新请求启动时的预算；操作系统启动和清理仍可产生开销，不声称总墙钟硬实时保证。历史诊断未配置 planner 总预算且直接调用 model_call，故它不是已知 600 秒问题的解释。

## Pipeline 主要架构缺陷

| 优先级 | 代码依据 | 缺陷及影响 | 建议 |
| --- | --- | --- | --- |
| P1 | agent/backend.py vs runtime/model_call.py；pipeline.py 配置传递 | 两套 CLI transport/config 语义：NativeSession 使用 ignore-user-config；planner 继承 provider/reasoning/tier；http_only 仅作用于 NativeSession。前序成功不能证明 planner 使用相同配置 | 定义一个显式 ModelCallPolicy，统一模型、推理、tier、transport、超时与隔离规则；每阶段保存脱敏有效配置。涉及改变生产传输，需关键决策确认 |
| P1 | planner.py PLAN_SCHEMA、POLICY、plan | 安装、资源判断、依赖、构建、案例、来源与验收规则集中于一次生成；action=read 仍要求完整 plan；acceptance_json/case_json 再嵌套 JSON 字符串 | 将资料请求与计划提交分开；把安装计划和验收提案分阶段检查/持久化，最后仍执行完整原验证器，不能以拆分为由减弱来源和锁定规则 |
| P1 | planner.py DEFAULTS/inventory/supply | context_chars、max_file_bytes、max_files 默认 None，第一次 supply 会读所有可读文本；inventory 还会对所有文件读取并哈希。大仓库可造成内存和 prompt 放大 | 提供用户显式可选的材料预算配置、文件分块与按需读取；保留完整来源清单和未读标记。不能把隐式裁剪当优化 |
| P1 | model_call.py run、CLI 的 producer/mapper/core 等待链 | 只有进程总超时；无服务端首事件、业务进度、队列等待等信号。600 秒只能说明监督到期 | 明确 startup / send / first-event / active / terminal / exit 阶段；区分 transport timeout 与 malformed answer；增加白名单 request/response ID、有效配置和结构化错误；不要把 models HTTP 200 当主请求健康 |
| P2 | model_call.run 两个 pump、save(events.json) | 输出全部留在内存；每个 stdout 事件重写整个事件数组；审计磁盘写与管道消费耦合。大量输出或慢盘可形成额外背压 | 追加式事件日志与有界摘要；审计故障应显式失败，不能静默丢数据。历史仅两个 stdout 事件，因此不是本次已证明根因 |
| P2 | model_call.run / NativeSession 各自维护线程与作业对象 | 相同进程监督机制重复实现，成功和异常路径容易分歧；收到 terminal 后仍必须等待退出 | 抽取共享监督器，保留“完整答案＋成功终止事件＋正常退出＋完整 I/O”的成功判据；单独设置经批准的退出收尾策略，不把 kill 后退出码 0 当成功 |
| P2 | preparation.propose、planner.plan、entry.associate | 多层预算与读/修正循环；默认不设总上限，不同调用点独立估算剩余时间 | 使用同一个绝对 deadline 和显式模型调用计数接口；本次只修 planner 发送前预算，不宣称其它阶段已统一 |
| P2 | recovery.inspect_candidate 等恢复路径 | 超时前未产生完整 plan 时只能保留输入重做，不能恢复远端已开始但本地未知的请求 | 使用不可变输入指纹和请求状态记录；仅在幂等、可查询、经授权的前提下重试。不要自动连续花费多个 600 秒 |

现有架构的优势仍应保留：确定性来源与入口核验、不可变交付、锁定断言、独立审阅、Docker 构建与业务验收分离，以及 accepted/candidates 的持久证据。这些机制不是当前无响应的证据，不应为缩短耗时而删除。

## 超时原因的当前证据排序

1. **暂态服务/请求处理、响应链路或 CLI 内部状态**：与“同固定输入后来成功”相容，是下一次故障时应优先采证的方向。但没有远端追踪，无法在三者之间排序，更不能认定服务端故障。
2. **复杂结构化生成与负载相互作用**：仍有可能，成功请求实际 input_tokens=24991；但本次约 101 秒完成，不能说必然超预算。没有做简化 schema 对照，尚无其因果证据。
3. **CLI 接收过滤、队列背压或有效配置差异**：匹配版本静态源码允许这些等待；无运行时堆栈或逐事件分类，仍是待证假设。
4. **历史网络异常**：早期 TLS EOF 对当时有解释力；本次成功不排除间歇性网络问题，但不能概括全部历史失败。

已降低优先级：stdin 未关闭、Python 双向管道死锁、必需并行争用、污染 schema 是唯一原因、所有失败均为模型列表刷新、Ping/Pong 重置上层 idle。最新失败没有证实隐藏重试，不能再次用“300+300”当结论。

## 验证与后续决策

修复前两个定向测试分别复现计数错误和过期后继续调用；证据在 before-tests.txt。首批四模块 36 项基线通过，修复后对应 39 项通过；新增关联错误分类和小数预算测试后，runtime_build 的 22 项通过。

全量运行 271 项、3 项跳过，无测试失败，163.889 秒，见 full-tests.txt（该进程在最后两个新增测试写入前已加载测试集）。该轮存在一个既有故障注入噪声：test_native 的 Popen mock 也包装了清理辅助进程 stdout，使 subprocess.communicate 的读取线程报 BrokenReader 无 read 属性。已将故障注入限定到模拟 CLI，保留真正的 reader-failure 断言；最终相关模块复查记录在 final-regression-tests.txt。Python 3.14 还有既有 is_reserved 弃用警告，与本次模型超时无关。

最终相关模块复查：50 项、1 项跳过，无失败，32.997 秒；不再出现上述 BrokenReader 线程异常。git diff --check 通过。

官方非交互说明将 `--json` 定义为事件输出、`--output-schema` 定义为约束最终响应，两者不能互相替代；本次完整验证保留两层检查：[OpenAI 非交互模式文档](https://learn.chatgpt.com/docs/non-interactive-mode)。具体版本行为优先依据本机二进制与已存匹配源码。

下一步建议：先以本次生成且通过验证的计划做独立 Docker 构建/业务验收，仍需正常流程最终验收才能宣称新创建成功。另行决定是否统一模型调用配置和拆分 planner；这些属于行为变化，不能将本次诊断成功自动视为批准。当前没有修改传输、模型、全局配置或 CLI 二进制，没有人工补写正确计划、业务代码或断言。
