# Docker 合并流水线复查与追加验收（2026-10-28）

## 结论的边界

run47 的混合后端执行结果是真实的：冻结输入、当前 Docker 镜像和业务原始输出重新验证后仍获资格。它不是所有输入、所有 skill 或全阶段 DeepSeek 的通用保证。本次追加实验的结果与 run47 分开记录；不以单测或模型审阅代替真实容器业务验收。

## 代码审查

检查范围：`contracts.qualify`、`runtime/preparation.py`、`local.py`、`service.py`、`execution.py`、`coverage.py`、`runner.py` 及规划补丁路径。

1. **入口绑定漏洞（已修复，`6e76924`）**：旧门禁仅检查 argv 包含脚本路径。离线复现 `python -c 'print(123)' /opt/skill/package/main.py` 可得到 `prepared`，实际没有执行交付脚本。新门禁要求直接执行该路径，或将其作为支持的 Python/shell 解释器的脚本操作数；拒绝 `-c`、`-m` 和命令包装。支持明确的无操作数 Python 开关。加入绕过拒绝与合法调用回归；这会使无法证明绑定的特殊解释器形式阻塞，而不是推断它有效。
2. **run48 暴露的补丁审计崩溃（已修复，提交以 git log 为准）**：模型将对象写入本应放字符串 ID 的 `operations[].checks`。外层 JSON schema 只知道 `acceptance_json` 是字符串，作用域审计先执行 `set(...)`，正式嵌套契约校验尚未到达，导致 TypeError 逃出整批。现在在补丁比较/降级审计前检查嵌套引用类型，返回具名可修复拒绝；同时保护 purposes、operation/check ID 和分类状态等参与集合运算的字段。
3. **误导诊断（已修复）**：run48 已引用检查 ID，但检查对象定义在 `input_contract.checks`，而非顶层。旧诊断“names no checks”使模型把引用 ID 改成了对象。新诊断列出 operation、缺失 ID、正确顶层路径，并明确禁止用对象替换引用 ID。行为用例缺断言的诊断同时补上具体用例名。判定标准没有放宽。

## run47 独立复核

当前严格资格复核通过；原始入口为 `['python', '/opt/skill/package/scripts/recap_terminal.py']`，不涉及新发现的绕过。

只在内存中修改报告进行反例检查：把真实计算输出改为 `{}`，保留 `passed` 标志，验证拒绝；删除一条用例，验证拒绝。原始冻结证据和报告未修改，也没有重跑 run47 业务。

证据：`E:\Users\27343\Docker\acceptance-review-20261028\run47-current-audit.json`。

## run48：原有描述符 skill

- 源目录：`E:\Users\27343\Docker\chem-agent-toolkit_newpipeline\tools-skills\rdkit\chem-rdkit-descriptors`，仅作为只读输入。
- 封套：`validation/deepseek-api/acceptance-existing-descriptors-input.json`；新 state/library；16 次计数调用、3600 秒；保留原脚本字节与依赖版本。
- 必需验收包括乙醇分子量 46.069、供体/受体计数、空串/畸形输入拒绝、混合行批次的实际文件输出及退出后持久化检查。旧 smoke 报告不算本轮证据。
- 构建 ID `20261028T210014-e4ec226a`，预算计数 6，结果 `failed`，在第三次规划补丁阶段因上述 TypeError 崩溃；**没有 Docker 镜像或业务通过证据**。来源快照、发现、编写、内容审阅完成，交付业务脚本未进入真实执行。没有恢复或重启本轮。
- 诊断依次为 `Behavior test requires assertions or explicit test runner`、`Operation direct-smiles is required but names no checks...`；随后原始补丁把检查引用改成对象，触发审计崩溃。
- 原始证据：`E:\Users\27343\Docker\acceptance-existing-descriptors-run48-20261028\`。错误发生在记录导出前，`summary.errors` 中保存异常；完整模型响应仍在该目录的 `state/runs/.../materials/planning/2/response-0.json`。
- 使用原始响应离线重放后，现返回指名 `direct-smiles` 和 `acceptance_json.checks` 的可修复补丁拒绝。重放没有模型调用，见 `E:\Users\27343\Docker\acceptance-review-20261028\run48-patch-replay.json`。

## 第二个授权实验

优先用相同描述符来源和相同验收义务新开 run49，验证 run48 修复；不更换材料避开失败，不把失败轮续跑，不追加第三个真实批次。run49 结果将在结束后补入。
