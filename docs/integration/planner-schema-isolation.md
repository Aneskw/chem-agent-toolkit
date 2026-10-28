# Planner schema 共享引用专项（2026-10-26）

## 基线与范围

分支 `integration/planner-timeout`，实际起点 `42df02c`（在已知 `28879cf` 后新增一次串行重试的证据提交）；开始时工作区干净。仓库递归搜索和父目录检查未发现适用 AGENTS.md。已阅读 final-continuation、final-single-retry summary/normal-build.log、planner.py 与 model_call.py。未回退历史、修改 partner、推送或发布。

## 复现与最小修复

`validation/planner-schema-isolation/inspect_schema.py before` 在修改生产代码之前直接导入现有 planner，保存两份实际序列化 schema、引用身份及说明路径。`base_image`、`requested_files.items`、PATCH 的 `value_json` 均与 `acceptance_json` 是同一字典。`arr(item=S)` 及多个字段共用 `S`，原地给 acceptance_json 添加 description 实际污染全部引用。

修复前 PLAN 字节与第四轮现场完全一致，SHA-256 为 `67e030bfdf6c8a9690a7b3d3926917834e43e41e602e3b68780d8f20f6147671`。也只读核实了第一轮成功调用的 schema，其 SHA-256 相同：污染是确定缺陷，但不能推断它必然导致超时。

唯一生产修改：将 acceptance_json 节点替换为独立的 `{"type": "string", "description": ACCEPTANCE_SPEC}`。保留共享原语的其他用途，避免架构重写。检查当前模块其他 schema 写入：resource_assessment 修改的是 plan 对象属性；PATCH 顶层 description 是有意设置，保持不变；未发现另一处对 S/B 原语的原地说明写入。以后若需修改共享字段仍须创建独立节点。

| 项目 | 修复前 | 修复后 |
| --- | ---: | ---: |
| PLAN 序列化字节 | 151,668 | 8,568 |
| PLAN 完整验收说明次数 | 37 | 1 |
| PATCH 序列化字节 | 20,438 | 4,538 |
| PATCH 完整验收说明次数 | 5 | 1 |
| ACCEPTANCE_SPEC 字符 | 3,889 | 3,889 |

PLAN 仅在 acceptance_json 字段保留说明；PATCH 仅在顶层保留说明。去除说明注解后的约束结构完全相同（正确保留名为 description 的业务属性），PLAN 指纹 `a2b99fc31b817f4050db25685c758fb7fed0ead5038164f831200c2fbe695586`，PATCH 指纹 `6cafda85d984e3568aabe6eb90d0bec96d93766ecdadc10db9cd4d04ad904e77`。没有修改 required、枚举、类型、数值边界、additionalProperties、业务范围、来源或锁定断言。

## 机制验证

新增 3 项回归：精确说明分布及共享原语未污染；目标字段可独立修改；与修复前实际 schema 精确对比，仅容许删除错误传播的注解。修复前三项均失败，修复后通过。

针对性运行 planner schema、runtime build、contract diagnosis、model call 四个测试模块，共 **44/44 通过**，包括锁定断言、计划修补、来源与入口、验收冲突及传输拒绝机制。测试使用 fixtures，不属于真实业务验证。初次扩展运行遇到系统沙箱临时目录 WinError 5，原日志保留；仅将该测试进程的 TEMP/TMP 指向工作区后通过，未改全局设置，也不是网络失败。

## 单次真实受控调用

诊断脚本 `validation/planner-schema-isolation/controlled_call.py` 只读取第四轮保存 prompt 和 handoff，验证 prompt SHA-256、完整 inventory 和已读文本相等。使用原 model_call.call 与全部现有传输完成条件；单次 600 秒，不自动追加读取、修补或重试。prompt 41,695 字节，SHA-256 `8af7e4416549cc30a3499000baf53293745efd82920ccbcc2bb1b0e7ba0bc9d9`，包含的源内容、要求与业务断言未改，只有 schema 的错误说明传播被移除。

首次预检在调用前发现当前配置已是 low，断言停止，未启动模型。保留 `precall-settings-mismatch.log`。随后仅对子进程显式设 `model_reasoning_effort="medium"`、`service_tier="default"`，模型仍为 gpt-6-astra；没有更改用户配置、代理或认证。具体操作经平台审批执行。`conditions.json` 同时记录当前继承值、实际生效值和局部覆盖，request 中的设置为该子进程生效值。

如有答案，先保存原答案和 receipt，再执行 jsonschema.validate 和 preparation.validate（包含 validate_plan、来源引用、验收 contracts/consistency/coverage/usage、实际交付入口、测试预算等），前后重新核验 handoff。返回 JSON 或 action=read 均不自动算有效计划。没有人工提供计划、业务代码或 Dockerfile，没有 host 化学执行、Docker 构建、catalog 写入或正常新创建。

**结果：600.045 秒超时，无答案，valid_plan=false。** 北京时间 17:11:42 启动，约 17:21:42 结束。stdin 0.199 秒发送完成，thread.started 0.381 秒、turn.started 1.658 秒，此后无方案或完成事件。清理后 stream_threads_finished=true、io_errors=[]；returncode=0 不构成成功，因为进程状态明确为 timed_out 且无完成事件。原始 request/process/events/stdout/stderr/timeout 和 failure/result 均保存在 controlled，未删除失败证据。

stderr 有 PowerShell snapshot 不支持警告，以及北京时间 17:16:20 的 `failed to refresh available models: request timed out`。后者仅证明可用模型列表刷新请求超时，不能等同于 planner 主请求失败的根因。本次没有记录 TLS/重连错误。CLI 的 thread.started/turn.started 不证明服务端已接收主请求或开始生成。无答案可供 schema/计划/完整性校验，不能称这些真实答案校验已通过。

## 结论与后续边界

确定修复了共享引用造成的错误指令传播，并通过约束等价与针对性回归；文件变小不等于模型验收成功。修复后的单次调用仍超时，因此“修复足以消除本次等待”不获支持，也不能证明 schema 对延迟毫无影响，更不能确定所有历史超时的唯一根因。第一次成功使用相同污染 schema 是进一步限制因果结论的反证。

**目前不建议立即进入新的全链路验收或候选恢复。** 在没有新的执行条件或定位证据前，完整重跑会重复消耗来源、发现和编写阶段。值得保留此最小修复；下一步若另行授权诊断，可优先取得主模型请求的发送/响应阶段、请求关联标识、首字节或服务端状态，并把模型列表刷新与主生成请求分开观测。这些是待验证方向，不是已取得的事实；不得记录认证信息，也无需据此擅改全局代理、认证或模型。

本次只执行一次真实模型调用；预检配置断言未触发模型。未追加读取、模型修补或无变化重试，未手工注入 catalog，未运行 Docker 或宿主化学业务。business_acceptance=not_run，正常新创建及最终验收仍未完成，今后必须由正常流程独立证明。专项完成后停止，等待审阅。
