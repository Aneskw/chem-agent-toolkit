# Tool 共享层第二阶段交付（2026-11-01）

从发布分支 `pipeline-with-shared-docker` 的 `b5ad543c4e309325e996ac776b6d3066b15501f6`
继续开发。接手时主工作副本干净，原 HEAD `28495f5` 与发布提交文件树相同；已切换到发布分支，
没有 reset、重建仓库或修改三个只读样例工作副本。本轮仅本地提交，不 push。

实现了可选 `shared_tool_image_v1`：准备阶段精确解析；命中时绑定具体工具版本，跳过环境
planner、环境 build 和工具 build；当前 Skill 的审阅、来源/接口、验收编译、执行与 qualify
仍走原检查。首次构建在完整核验后发布工具记录，业务失败不污染工具或其他 Skill。

**范围限制：命中时需要调用方提供当前 `acceptance_plan`。** 尚未新增“只生成验收”的模型阶段，
不能声称任意新 Skill 的全自动生成已经验证。默认旧模式不变。完整配置、四对象/三身份协议、
架构和迁移细节见 [ToolArtifact 协议](../pipeline/shared-tool-artifact-protocol.md) 与
[集成流程](../pipeline/integrated-flow.mmd)。

## 验证与证据口径

机器索引：[shared-tool-phase2-results-20261101.json](../../validation/deepseek-api/shared-tool-phase2-results-20261101.json)。
索引列出独立目录、结果及日志摘要哈希，代码文件摘要用于确认受测实现。原始执行、冻结输入、
build 日志、输入输出和目录快照保留在 `E:\Users\27343\Docker` 的各独立证据根。
没有把旧 72 条作为本版本新验收，也没有合并重验数与生成批次。

| 类别 | 证据根 | 结果与边界 |
| --- | --- | --- |
| 最终离线回归 | `tool-phase2-regression-final2-20261101.log` | 666 项，663 通过、3 跳过，无失败/错误 |
| 三个提示/契约自检 | `tool-phase2-*-final.log` | 全通过；没有修改提示/schema，无需 freeze |
| 最终基础设施 | `shared-tools-infrastructure-20261101-05` | 7 个独立 fixture 场景、0 模型；其中故意业务失败与构建失败按预期拒绝 |
| 化学合同重验 | `shared-tool-atommap-20261101-02` | 原脚本/来源不变，两次各 22/22；第二次同 ToolArtifact，两个 build 计数均 0 |
| 同主机交付恢复 | 基础设施目录内 `delivery.json` | envelope 安装、导入、迁移、resume、显式 rebuild 后重新执行；导入与迁移均未继承资格 |

基础设施中的内容审阅是明确标注的确定性 fixture，**不是新的原生 Agent 审阅批次**；
化学试验是已有不变内容与锁定合同的重验。新的完整模型生成批次为 0，付费模型调用为 0。
生产链仍要求每个候选独立内容审阅通过，工具命中不会替换该事实。

前置轮保留：基础设施 `-01` 验证初始四场景，`-02` 加入并发与交付，`-03` 加入故障和耗时，
`-04` 单独做无并行化学构建的对照，`-05` 验证最终环境观察标记；原子映射 `-01` 是补强前的
44 条重验，`-02` 增加当前完整目录/安装版本检查。不得把这些轮相加包装成独立新生成成功率。
所有真实轮使用新目录，没有 resume/restart 失败轮；交付试验内部的 resume 是被测 API。

首次 Python 调用命中不可用的 WindowsApps 别名；初次全量回归和一次自检又遇到沙箱临时目录
权限错误。后续仅为命令设置 Python 3.14 路径与工作区 TEMP/TMP；本地模拟服务/子进程测试在
允许的主机执行环境运行。没有修改全局配置、模型后端或预算，也没有为消除漂移刷新提示。

## 针对性反例

- 19 个新增离线用例覆盖：源码/支持文件、显式要求/约束、接口及资源限制、策略变更，记录损坏，
  镜像/daemon 不可用，缺当前验收，调用方改变环境计划，失败构建，取消、等待超时与锁所有权。
- 真实同时准备的两个 Skill 使用同一请求，只发生一次工具 build，均独立执行；不同工具各有工具
  版本，依赖环境命中。此处是真实线程并发和文件锁，不冒充跨进程/跨主机分发实验。
- 镜像缺失用隔离测试记录引用不存在的 image ID，daemon 漂移用隔离记录中的不同 daemon ID；
  当前 Docker 元数据实际探测均 miss。损坏记录返回 `invalid_record`。未删除用户镜像来造故障。
- 故意退出 17 的真实环境构建返回 `build_failed`，不登记 ToolArtifact；旧版本文件摘要不变。
- 故意要求不可能 stdout 的当前 native 用例保留并实际失败，新 Skill 不合格；旧 Skill 仍通过
  当前 qualify。未删除或弱化失败断言。
- 超时、取消与替换锁所有权有离线确定性反例；本轮没有把它们称为真实 Docker 超时/取消实验。

## 耗时和存储

最终数值由机器索引及基础设施 `observations.json` 给出。三个对照均使用相同 Python 基础镜像、
相同依赖阶段、平台、运行限额和 stdout 工作负载；“不同工具”只增加源码注释以制造明确工具 miss，
保持依赖和工作量一致。SKILL 文案与当前 case 名称不同。无模型阶段均计 0；这不能外推为
完整生成批次的总模型调用数为 0。

| 最终对照（秒） | 环境 build | 工具 build | 准备 | 构建/绑定 | 当前验收 | 业务用例墙钟 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 环境 registry miss（skill-a） | 1 | 1 | 0.597 | 6.602 | 3.845 | 0.621 |
| 环境 hit、工具 miss（different-tool） | 0 | 1 | 0.441 | 3.464 | 3.812 | 0.640 |
| 完整工具 hit（skill-b） | 0 | 0 | 0.669 | 1.495 | 3.520 | 0.687 |

三者环境规划/验收模型调用均为 0，原因是显式 fixture 计划；`skill-b` 的准备回执另证明它
在环境规划前命中了具体工具。完整工具 hit 的本次环境观察为 `not_requested_tool_hit`，
历史 EnvironmentArtifact 身份单独保留，不把旧 built 状态计为本次构建。

构建/绑定耗时包含当前身份与内容探测；验收耗时包含 preflight、完整性检查和 Docker 启动。
`business_case_wall_seconds` 单独累加非 environment 用例的 run_case 墙钟时间，包含容器和文件
管理开销，不是纯化学 CPU 时间。单轮、小工作负载数据只作可复核观察，不给统计显著性或通用提速比。

各轮使用新 registry，Docker/BuildKit 缓存和预热镜像保留。因此“环境 miss”是 registry miss，
不是磁盘/网络冷启动；build 调用数不等于安装命令实际重跑数。基础设施依赖阶段只检查解释器，
不能声称测到了 RDKit 安装加速。化学 build 日志另保留真实安装/层缓存输出。

`storage-before.json`/`storage-after.json` 是 `docker system df -v` 的 Engine 观测（本机为
overlayfs/containerd snapshotter），包含共享/独占层记账。没有把镜像虚拟大小求和，没有清缓存，
也没有测宿主 VHDX 的实际占用或得出磁盘节省比例。工具规范树与兼容执行树存在两份内容，
存储成本如实保留。`-03` 与化学轮曾并行，不能用其全局磁盘 delta 归因；最终 `-05` 没有本任务
并行的化学构建，仍只是 host-wide 快照，不能排除外部活动。

## 已实现与未支持

已实现：显式完整包/来源闭包、精确本机解析、版本追加与有界互斥、具体绑定、独立资格、只读 CLI、
调用阶段/构建计数、真实执行耗时、同主机 envelope 迁移恢复，以及旧自包含路径回归。

有限支持：字节一致来源的 Python 脚本、无外部运行资源/网络、同名 Python distribution 版本要求、
固定 Linux amd64；命中后由调用方提交当前验收。包内 examples 等改动会保守 miss。
现有具体版本缺失时阻止，显式准备新修订才能选择/构建另一版本。

设计中/未支持：自动验收专用模型阶段、任意动态 Python 闭包分析、Markdown 工具、外部 executable
（因此 Open Babel 尚未接入新模式）、自动兼容合并、跨主机 OCI 分发、常驻 worker、结果缓存、GC。
没有新完整模型批次证明，也不提供科学有效性结论。

Skillnet 只梳理了 catalog Skill revision、具体工具绑定、typed artifact identity、独立 attempt 和
qualify 接口；未进行平台重构或部署。建议先把这些字段作为适配边界，再独立设计远端分发与策略协商。
