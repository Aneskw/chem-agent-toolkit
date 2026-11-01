# 工具命中后的验收专用模型阶段（2026-11-01）

基线为本地提交 `16e409d`。完整工具命中后，默认用 `acceptance_only` 协议生成当前 Skill 的验收，
不再要求调用方提供 `acceptance_plan`。显式覆盖仍兼容旧基础设施验证脚本。

最终结果：成功 A 21/21、成功 B 20/20，当前代码只读 qualify 均通过；B 环境规划、环境构建、
工具构建均为 0。完整回归 676 项：673 通过、3 跳过，无失败或错误，三个提示与契约自检通过。
机器可读索引：[shared-tool-acceptance-model-results-20261101.json](../../validation/deepseek-api/shared-tool-acceptance-model-results-20261101.json)。

模型只可返回 tests、acceptance_json、output_contract、unverified_behavior。环境、依赖、
资源、入口、source_files 与具体 ToolArtifact 均由程序固定；额外字段或环境 patch 会被拒绝。
响应确定性合并后仍经过原来的源码引用、锁定合同、负例覆盖、native check 与 qualify 检查。
新 Skill 不复制旧用例、旧执行输出或旧通过标记，独立内容审阅继续保留。

材料读取、模型后端与配置、deadline、调用 guard 和尝试数均沿用原 planner。新阶段在既有
调用账本中记为 `runtime_acceptance_planning`；工具 miss 仍使用 `runtime_planning`。
每次读取/生成占用原预算；不可用或超时直接保留阻止证据，不用旧验收或环境重规划兜底。

原组合 planner 的提示和 schema 哈希保持不变。新协议纳入 `verify_acceptance_prompt.py`
的实际发送提示/schema 身份检查，按 `verify_planner.py freeze` → `verify_acceptance_prompt.py freeze`
顺序更新快照；变化来自新增 acceptance_only 身份，而非盲目消除漂移。

真实验证脚本为 `validation/deepseek-api/verify_acceptance_only_e2e.py`。它沿用原子映射封套：
Codex CLI gpt-6-astra 用于发现、编写、独立审阅，DeepSeek deepseek-v4-pro 用于结构化规划；
每批 16 次准入调用、600 秒单次、3600 秒整批、2400 秒运行准备预算及原供应商重试配置不变。
两个批次独立生成文案，包中只含 SKILL.md 与字节未改的原脚本；运行要求相同、文案风格不同。
两批均不提供 plan 或 acceptance_plan。工具请求中的显式共同 requirements 保留全部业务义务，
只把纯文案风格差异留在当前 Skill，而非删除兼容性要求来制造命中。

每次脚本调用使用全新证据根。第二批必须命中同一具体工具版本，环境规划为 0、两类构建为 0，
但验收模型调用必须大于 0；两份当前合同指纹和 SKILL 文档摘要必须不同，且各自实际执行与资格通过。
源码前后摘要、完整模型回执、冻结输入与逐用例输出均保留。失败不 resume/restart，亦不放宽用例。

验收专用阶段另在冻结前拒绝带空白的 case_json.entrypoint（含 relation.runs 覆盖）：
它是单一可执行文件，不是 shell 命令；例如使用 entrypoint="python"、args=["-c", "..."]。
具名错误保留用例、字段与实际值，模型须修正参数结构并保留探针和断言。当前保守协议不支持
可执行文件名本身含空白；旧组合 planner 协议未修改。

证据根位于工作副本同级，按顺序保留：

- `acceptance-only-e2e-20261101-01`：A 完整生成及 Docker 验收成功，21/21。随后验证脚本
  因 Windows 文件排序差异误报文件列表不等；实际文件集合相同。修复为集合比较，原失败保留于
  failure.json / harness-diagnosis.json；未重跑 A，之后仅只读核验该成功产物。
- `acceptance-only-e2e-20261101-02`：独立 B 确实命中同一工具，环境规划 0、两类构建 0。
  15/16 通过；environment_python_rdkit_available 将整条 python -c 命令当成单一 executable，
  Docker 返回 127，B 未获资格。完整失败输出保留。offline-diagnosis.json 证明新增离线检查
  能拦截这份原始错误；post-failure-qualification.json 证明 A 仍合格、B 不合格。
- `acceptance-only-e2e-20261101-03`：修复离线通过后，全新 B 完整生成成功，20/20，资格通过。
  result.json / post-run-audit.json 保留与成功 A 的对照和失败 B 的复核。新 B 的首次验收草案
  因 file_batch_valid_persisted_output 引用 SKILL.md 的原文不匹配被拒绝；第二次修正后冻结。
  A 的三次组合规划中也保留了用例名及正则格式的冻结前拒绝；都不是删除已锁定失败用例。

这些基础设施失败与验收失败分别计数，不把失败 B 算作成功批次，也不把只读资格复核算作新业务执行。
当前用例始终由当前模型及独立审阅产生，不拷贝 A 的合同来绕过失败。

| 观测 | 成功 A（-01） | 成功 B（-03） | 失败 B（-02） |
| --- | ---: | ---: | ---: |
| 实际用例 | 21/21 | 20/20 | 15/16 |
| 当前资格 | 通过 | 通过 | 不合格 |
| 全部模型调用 | 6 | 5 | 5 |
| 发现 / 编写 / 独立审阅 | 各 1 | 各 1 | 各 1 |
| 组合环境与验收规划 | 3 | 0 | 0 |
| 验收专用规划 | 0 | 2 | 2 |
| 环境 / 工具构建调用 | 1 / 1 | 0 / 0 | 0 / 0 |
| 整批秒数 | 739.445 | 726.023 | 675.599 |
| 构建或绑定秒数 | 7.779 | 2.902 | 2.594 |
| 全部用例执行秒数之和 | 17.956 | 17.312 | 13.621 |

本轮实际完整生成 **3 批、16 次模型调用**，其中 2 批成功、1 批失败；成功对照为 41/41，
不并入历史 72 条，也不把 A 的重复只读核验记作新生成或新执行。各模型阶段耗时、usage、
独立 author/review 会话、逐用例日志和文件 SHA256 见索引与其指向的本地证据。

三个观察均绑定同一 ToolArtifact `a786f6af32abc11279b54c59e8bcff50beae9351eaf08127f583257e3c4eb6be`，
request_key 为 `77b46e53b801266c7fb79894a08a6077934372f145dd2fc9904d1920c956e21b`；
实际本机 image ID 为 `sha256:f807561ab0797e3271be241cc5c088aace95b3c84d43a107e4d63cf23163dd24`。
这不是 OCI manifest digest。脚本 SHA256 一致且与只读来源一致，A/B SKILL 文案及验收合同摘要均不同。
新 B 首次模型输入含当前 SKILL.md，bound_environment 不含四个验收字段，previous_plan 为空，
实际提示 provenance 与最终代码一致。失败 B 的资格在成功 B 完成后仍为 false，A 仍为 true。

重现实验使用新绝对目录执行 `python validation/deepseek-api/verify_acceptance_only_e2e.py <new-root>`；
`--offline` 仅检查输入配置，零模型调用。`--previous-a <successful-a-root>` 只读复核原成功 A，
然后在新根启动完整 B，专用于本次验证脚本误报后的续接；它不恢复失败 B，也不复制旧验收。
最终回归日志为同级 `acceptance-only-offline-final2-20261101.log`；三个自检日志为
`acceptance-only-{prompt-contract,prompt-provenance,planner}-20261101-final.log`，摘要均收入索引。

范围保持本机 `shared_tool_image_v1`：调用方显式声明的完整 Python 闭包、同 daemon 可核验的
具体工具镜像。此次补齐验收生成，不扩展自动兼容合并、远端制品分发、常驻 worker、结果缓存或 GC；
安装、迁移、恢复的支持边界仍见版本协议和第二阶段交付，未声称本轮重新执行所有交付实验。
未来 Skillnet 可分别消费具体 ToolArtifact/SkillBinding、`runtime_acceptance_planning` 调用回执、
当前锁定合同及 ExecutionAttempt/qualify 结果；工具可用性与 Skill 资格仍须分开查询。

本机已有 Docker/BuildKit 缓存和基础镜像，本轮没有清理它们。构建调用为零是直接计数，
不等同于安装命令的执行次数；首次两次 build 也不宣称冷启动。不同 Skill 当前合同的用例数量
可能不同，因此总耗时只作观测，不据此归因固定加速比例。未以镜像虚拟大小相加推算磁盘节省。
