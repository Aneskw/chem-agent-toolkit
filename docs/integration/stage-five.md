# 阶段五：联合验证、文档与有限清理

固定基线 `integration/docker-stage4` 的 `368dca0422c1357eb914d93b99e0aaf31278c8c6`。
在干净的独立集成工作区创建 `integration/docker-stage5`；未发现适用 AGENTS.md。
只读核对远端 partner 仍为 `e117c434f54d11fd24e3e5566f187a8f4a41a87f`，未更换基线。
原 Docker 工作区及历史归档不修改。阶段三、四交接与证据被复用，未重新记为本阶段新实验。

## 最终结论：三条链路分别成立的范围

| 链路 | 真实观察 | 未证明的范围 |
| --- | --- | --- |
| 完整创建链路 | DNA 新来源经正常 CLI、真实 gpt-6-astra 发现/作者/独立审阅；首次规划调用超时保存候选。随后仅 runtime-prepare 恢复真实模型规划、Docker 构建与 10 项验收，进入 accepted。未人工修改生成文件、检查或计划 | 不是一次不中断、无需显式恢复的自动 build 成功；只证明该 DNA 字面计数能力 |
| 失败隔离与恢复 | DNA 恢复前后源码、交付和作者检查未变；稀释失败时不能安装。正常 CLI 安装正式 DNA 成功；导入 DNA 的候选默认查询为空、安装拒绝。阶段四缺资源/清理临时目录/中断/ZIP 的真实证据继续有效 | 同机跨路径及 ZIP 已验证，第二台主机未实测；本阶段不是实时模型自动多候选批次，partial 调度有机制测试 |
| 验收契约修正 | 稀释的 planner 类型谓词错误经**显式来源提案**、真实独立模型审阅、v2→v3、新修订和 13 项真实 Docker 重验后入正式区；业务源码、交付及其他断言未变。最终独立验证库保留 catalog 到旧失败文件的直接历史引用 | 已验证显式入口；未验证模型自主识别、提出并完成 oracle 修正。不能把正确业务代码要求改成迎合错误测试 |

DNA：`20261026T001829-20a70452`，正式项 `dna-base-counting-cli`，
修订 `rev-60fb7348eb9a6b1b05934168254ea13c4c4b1e559bd2b6e51dd94f95da07e199`，
镜像 `sha256:be807e6596d849822b8019b1c6b25740f5658309676a9b60d4952b8b6c9e7509`。
入口 `scripts/base_count.py` 及支持文件真实覆盖；10 项包含正常计数、非法小写/空白、
文件持久输出、原生参数契约。证据：`validation/stage5/summary.json`、creation-audit、
library、CLI 查询/安装记录。首次 `build` 状态仍原样保存为 blocked，绝不改写成 ready。
恢复使用原候选、原流程，仅将单次规划故障超时从 600 调至 900 秒，无整体工作配额。

稀释最终复验修订 `rev-d8ad200a6264958f7b268e354bda149421ba97e9911b916951ce565c7e57688b`，
证据 `validation/stage5/oracle-summary.json`、oracle-library。旧 v2 的失败不能继承资格；
新 v3 经过真实独立批准 `oracle_changes_verified=true` 和全部 13 项重验。首次修正试验
旧文件虽保留但历史缺 pending 引用，补齐 store 的历史快照后在独立验证库重新完整复验；
没有人工改 catalog 来制造通过。样例库都使用同一 store/catalog 实现，不是第二套服务。

`review_required`/内容资格撤销是保守门禁，**不是已证明 Skill 源码错误**。本例归因为
planner acceptance-contract error。恢复提示明确区分需作者修复的内容/调用缺陷与可走
现有 `runtime-prepare --oracle-correction` 的来源支持契约错误。

## 能力迁移核对

| 能力来源 | 当前唯一实现 | 保留、适配与证据 |
| --- | --- | --- |
| partner 资源获取/快照/补充材料 | resources/*、agent/tools.py | 保留来源注册、文件校验与补充；test_sources、test_research |
| partner 发现/直接文件作者/独立审阅 | generation/*、agent/backend.py、pipeline.py | 保留逐候选流程与 Native checkpoint；test_discovery、test_native |
| 旧 runtime planner / acceptance | runtime/planner.py、acceptance.py、coverage.py、preparation.py | 保留来源依据、计划结构与业务覆盖；交接到最终交付入口，取消隐藏 production 配额；test_runtime_build |
| 旧 runtime_package 进程/容器/断言/输出 | runtime/runner.py | 保留 Windows Job、POSIX 进程组、超时清理、挂载、业务断言；test_migrated_execution 及阶段三真实 RDKit |
| 旧 runtime_model_lifecycle validate/evidence | runtime/execution.py、local.py、service.py | 分离冻结与动态目录，核验镜像/输入/契约及原始输出；test_runtime_execution |
| 旧 strict_acceptance | runtime/strict.py、contracts.qualify | 证据重算后执行严格资格判断，不信 passed 布尔值 |
| 旧 inspect_run / relocate_runtime / lifecycle 恢复 | runtime/recovery.py + 原 service/store | 只组合原执行器与库事务；阶段四真实缺资源、进程中断、ZIP/路径迁移、同内容新证据 |
| 旧 runtime_transaction | artifacts/store.py | 统一 staging/backup/journal/catalog 事务；迁移的四种失败/回滚测试 |
| 新政策必需衔接 | contracts.py、artifacts/evidence.py、runtime/checks.py | 修订身份、双区库、冻结交付、Native 检查容器映射、当前资格与历史分离；test_delivery_protocol、test_runtime_recovery |

不存在旧创建/发布 CLI、旧 bindings 或旧 ZIP 协议的第二套主流程。library.py 是 store 的
公开导出，不是另一套库管理器；runtime-resume/validate/build 共享 service.resume_build。
Native resume 负责发现/作者 checkpoint，冻结后的恢复由同一 runtime 服务承接。

本阶段仅删除失效的 `--execute-generated-checks` 宿主执行 CLI 开关和 runner 中未使用的
argparse 导入，更新旧说明。保留仍被校验、助手或旧保障单测使用的底层函数，不为清理而重写。
新增内容为新来源示例、实现架构图、修复路由与 CLI 边界测试及验证记录；不新增执行器、
状态协议或 catalog。原工作区架构草图保留，仓库实现版为 `docs/pipeline/integrated-flow.mmd`。

契约修正核对补齐两处必要保障：以现有 canonical 指纹比较严格类型契约，避免 Python
整数/浮点相等导致版本不增或普通环境修复绕过锁；catalog 新修订历史保留 pending_runtime、
中断/恢复记录与当时的内容/执行/主机/资格观察。新增回归与最后真实修正复验共同覆盖。

真实运行暴露了检查 `evidence` 被作者写成数组时的未处理类型错误。补充字符串类型检查，
使其成为明确的来源证据格式诊断，并补回归；作者提示明确要求单个来源 ID。同时修正
阶段一残留的“尚无 Docker 执行器”提示，说明真实执行由后续 runtime 阶段完成。
首次运行中模型已自行修复元数据并重新独立审阅，未人工修改 Skill 或断言；这是格式修复，
不能冒充真实环境依赖修复或业务内容修复。该运行开始时使用基线作者提示，后续修改已记录。

首次完整运行 `20261025T234212-7e883f8c` 在冻结来源校验失败，未进入正式区：Windows
Path 的大小写排序与来源清单字符串排序不一致。修复仅在来源清单比较时规范顺序，仍逐项
比较路径、哈希和字节数，保留重复项检查效果；没有放松 manifest、修改来源或旧契约。
新增含 README.md/api.py 的目录来源回归及字节漂移拒绝断言。失败输出与 Native 调用
记录保存在 `validation/stage5/failed-first-*`，随后从原始输入启动全新正常 CLI 创建。

第二次 `20261025T235441-a7f98a6f` 已真实构建并执行，但 Native `json_equals` 被 Docker
适配误接到旧严格类型 subset：正确的 10.0/40.0 因预期写作 10/40 被拒绝，且嵌套对象
原本要求完全相等，subset 反而可能放过额外字段。修复使用原 Native 精确 JSON 比较语义，
旧 expected_json_lines 和 acceptance 的严格类型/容差逻辑保持不变。新增数值等价、
嵌套额外字段拒绝、错误值/字符串拒绝及旧 subset 不变的回归。没有修改任何锁定断言。

该执行器错误曾触发真实内容反馈、作者和第二次独立审阅；定位后显式终止本次专属 CLI
及模型子进程，保存 `interrupted-second-*` 原始产物/调用。这不是成功的内容修复闭环。
作者曾自行归因数值类型差异，并把八个元数据数值期望写成浮点形式（交付文件未改）。
该尝试不作为修复成功证据，也不复用这些调整后的检查。第三次从原始来源
重新正常 build，不使用前两次的 Skill、计划或通过状态。

同一 Native 检查语义核对补齐 `artifacts` 的原非空要求：执行与历史证据重算均拒绝空文件，
不能通过伪造状态绕过。只影响映射的 Native 检查，保留旧 runner 的其他契约。此项在第三次
运行的内容审阅期间修改，未修改任何模型生成文件/断言；记录运行中代码维护这一干预，
不宣称整个实验期间仓库没有变更。最终全量回归在该修复后重新执行。

第三次 `20261026T000542-e190638f` 真实构建并执行 13 项，6 项 Native 检查均通过；旧
planner 的三个业务用例却把浮点结果写成了严格整数 `allowed_values` 谓词，导致 execution_failed。
这是规划验收契约问题，不是资源不足，也没有通过放宽旧 typed subset 来掩盖。停止该次
作者重试，归档 `interrupted-third-*`，用已有 runtime-import 保存到样例库 candidates。
当时内容资格被执行反馈撤销，不能 runtime-resume 绕过；需要有来源依据的新契约和独立
审阅后重验。随后按用户追加要求完成上面记录的显式修正；仍不宣称自动完成 oracle 修正。

随后以独立的新源码 `examples/base-count/resources` 启动正常 CLI。它计算 DNA 字面
碱基整数计数，初始文档明确限定 ACGT/文件输入/非法输入和固定结果，不含预制 Skill 或
计划。这不是修改稀释源码让错误期望通过，而是另一个候选能力的真实创建实验。该次
生成不再修改生产代码，不复用任何旧交付或通过状态。两个来源的事实分别报告。

## 验证分类与限制

新鲜端到端输入分别在 `examples/dilution/resources` 与 `examples/base-count/resources`：原始 Python 源码、说明、数据。
输入不是预制 Skill；模型生成前已固定 10+40、12+0、非法输入、文件读写等预期。
通过正常 CLI、production profile 自动选择模型，无预设环境计划，无人工修改生成产物。
实际日志和结果见 `validation/stage5`；最终观察结果在本文件后续记录中明确列出。

修复路由故障注入测试验证：环境失败不重新作者/内容审阅；内容失败再次经过作者与独立
审阅；锁定契约随反馈传递。另有已有断言不可弱化、内容撤销不可环境恢复、错误输出不能
冒充资源问题的单测。**这些是机制测试，不是真实模型自动多轮修复成功证据。**

阶段三已有真实 RDKit、非法 SMILES、文件 IO、镜像 tag 改指向/丢失与错误业务输出证据。
阶段四已有真实持久恢复、临时目录清理、构建/执行中断、故障注入 catalog 回滚和 ZIP 重验。
本阶段不把它们称为新来源自动创建，也不继承其旧产物通过状态作为新示例的资格。

纯文本正式资格、草稿拒绝、需求未知、候选默认隔离、逐候选 partial、来源漂移和锁定断言
通过全量机制回归覆盖。真实完整自动多候选批次和模型自主提出并完成 oracle 修正未验证；
显式来源提案加真实独立审阅的契约修正已如上验证。
同机跨路径及 ZIP 已验证；第二台主机未实测。远程 GPU、外部资源挂载、凭据传递与服务
探测仍明确阻塞；预留请求绑定接口不代表远程服务实现。CPU 算术样例不能证明 GPU 或
一般科学正确性。不安装宿主软件依赖、不推送、不发布、不合并远端 PR。

可复现构建/安装/恢复/迁移命令见 `examples/base-count/README.md`；稀释自动尝试失败与显式修正边界在其
独立 README 中明确保留。完整目录和状态含义见
`docs/pipeline/runtime-recovery.md`；历史执行事实不能代替查询时的当前镜像与主机核验。

## 联合回归

基线 191 项成功（Windows 跳过 2 项 POSIX）。最终生产代码修复后全量回归 199 项，
197 通过、2 项 Windows 跳过，见 `validation/stage5/regression-final.log`。没有删除原关键
断言。最后修复后的 Linux 隔离容器 9 项事务/POSIX/JSON/产物语义测试全部通过，含 Windows
跳过项，见 linux-final-tests.log（较早的 7 项通过记录仍保留）；
该容器测试不是业务验收。中间 194 和 195 项结果分别保留为 interim-tests.log 和
pre-json-fix-tests.log；另有 pre-artifact-fix-tests.log 的 196 项中间结果，不冒充最终回归。

| 关键行为 | 回归与真实证据类别 |
| --- | --- |
| 发现、补充材料、直接文件回执、独立审阅与候选继续 | test_discovery/test_native/test_research；新来源 CLI 单候选真实实验另记 |
| 阅读型正式区、草稿/未知拒绝、候选显式访问、partial | test_delivery_protocol/test_skill_library；不是新增真实模型多候选批次 |
| 资源不足与不支持分开、确定错误不调用模型 | test_runtime_build/test_runtime_recovery；阶段四真实缺 Docker 保存恢复 |
| 环境与内容反馈分流、锁定断言和重新审阅 | 新修复路由注入测试及现有不可弱化/oracle 独立审查测试；自动模型业务修复不宣称覆盖 |
| 错误结果、真实入口、输入输出、超时/清理 | 22 项迁移旧保障、test_runtime_execution；阶段三 RDKit 真实证据及新例另记 |
| 镜像/tag、来源/输入/契约漂移 | 迁移及新增核验测试；阶段三真实镜像漂移，阶段四新引擎拒绝机制测试 |
| 运行恢复不重新编写、临时清理、同内容新证据、原子回滚 | test_runtime_recovery、阶段四真实恢复记录；本阶段只读复核两份旧库仍有效 |
| 新发现的来源排序/错误证据类型 | 两项新增回归；字节变化仍拒绝，未放松冻结完整性 |
| 清理后的 CLI 边界 | 新 help 测试：保留草稿/库入口，移除失效宿主执行开关 |
| 契约类型版本/锁、历史失败引用与诊断门禁 | 新 typed-contract/history 回归；真实 v2→v3、独立审阅、13 项执行、直接失败引用核验 |

`stage4-readonly-recheck.json` 是本阶段对旧证据与当前镜像的只读重核结果，不是重复业务
执行；没有改写阶段四 catalog，也没有将其产物作为新示例输入。
