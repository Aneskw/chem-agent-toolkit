# P0 收尾：必需交付路径不能被业务通过替代

状态：**P0 本机保守支持范围已完成**。最终代码全套回归及三个提示自检通过；
普通 CLI 的错误布局负例被拒绝，新 A/B 当前资格独立通过，B 完整工具命中。
机器索引见 [delivery-layout-results-20261101.json](../../validation/deepseek-api/delivery-layout-results-20261101.json)。

原描述符配置明确要求 `Deliver exactly SKILL.md, scripts/calc_descriptors.py and requirements.txt`。
旧交付却把依赖文件放在 `resources/requirements.txt`。原因有两层：默认指引和作者回执门禁
只允许 `SKILL.md` 位于包根，与用户要求冲突；交付资格只冻结文件、来源、执行要求、绑定、
环境和验收，未冻结调用方的必需文件清单。脚本数值和文件业务测试通过不能证明交付路径正确。
此前两批的业务结果是历史事实，不能作为满足原始完整交付要求的证明。

新 `artifacts/layout.py` 从原始调用方配置编译通用路径契约，没有硬编码描述符、RDKit 或
`requirements.txt`。显式清单及根文件要求优先于默认目录规则；明确额外文件也会被拒绝。
原始文本、字段及引用与解析后的要求一并进入 delivery protocol 2 的 `inputs.layout`、
独立 fingerprint 和 revision。作者回执、结构检查、环境准备前、执行请求及最终 qualify
均保留确定性门禁。无执行交付也先检查路径，独立审阅或旧 passed 标记均不能豁免。

路径错误返回具体 path、expected、actual、其他同名路径、实际文件清单及原字段/引用。
准备前的失配使用 `delivery_layout_mismatch`，指向内容修复并撤销内容通过，模型环境规划
调用为 0。默认安全路径、凭据排除和五类目录限制仍保留；只有调用方明确要求的路径可作例外。

协议、有限文本语法、结构化接口和旧版边界见
[必需交付路径协议](../pipeline/delivery-layout-contract.md)，架构见
[集成流程](../pipeline/integrated-flow.mmd)。未实现任意自然语言解析、必需目录、通配符或负向
路径规则；不涉及远端平台或 OCI 分发。

普通 `check OUTPUT_OR_PACKAGE --config ORIGINAL_CONFIG.json` 可以按原需求审计历史输出，
不改原包、不调用模型、不授予新资格。新输出已有冻结契约时同时检查冻结要求和外部配置，
后者不能放宽前者。协议 1 保持读取和原资格规则；缺少原文的历史交付不自动升级为路径通过。
迁移需要原配置审计，或以原要求重新生成、独立审阅并执行新修订，不改写旧 freeze。

实验证据目录：

- `E:/Users/27343/Docker/descriptor-layout-cli-20261101-01`：初次离线回归失败及首次历史布局负例。
  新门禁最初误把无调用方路径要求的低层 runtime 材料强制要求为 Skill 包，导致 58 失败、
  1 错误；已改为只记录调用方明确提出的路径，原 `SKILL.md` 结构检查未删除。没有付费生成。
- `E:/Users/27343/Docker/descriptor-layout-cli-20261101-02`：719 项回归通过、历史布局负例和旧模式
  重验。新生成 A 的布局正确、源码和依赖文件原字节一致、独立内容审阅通过，但组合规划
  3 次调用后因 `planning_no_progress` 阻止；无 Docker 构建或业务执行，资格为 false。
  模型把单文件 hash 写成材料列表摘要，旧错误未提供期望摘要；6 次准入调用全部保留。
- `E:/Users/27343/Docker/descriptor-layout-cli-20261101-03`：720 项回归通过。A 的当前路径、
  独立审阅及首次组合规划通过；4 次准入调用。模型把来源没有精确 RAM/CPU 数值表达为
  `resource_assessment.status=unknown`，运行时如实 `resources_unknown` 阻止。两类 build
  均为 0，没有业务执行或资格。未恢复此轮，原材料和锁定用例保留。
- `E:/Users/27343/Docker/descriptor-layout-cli-20261101-04`：澄清规划提示后的独立新轮。
  原配置未改。A 构建 1 个环境、1 个工具镜像，5 次准入调用，真实 Docker **10/11**；
  `valid_file_persisted_rows` 失败：模型把苯酚原输入 `c1ccccc1O` 当成 canonical 输出，
  工具实际输出 `Oc1ccccc1`。资格 false，按 stop_on_runtime_failure 停止，不恢复、不删除用例。
- `E:/Users/27343/Docker/descriptor-layout-cli-20261101-05`：资源引用闭包检查后的独立新轮。
  只补充固定 RDKit 版本的官方 golden 来源及保留上述失败用例的约束；原 prompt、首个来源、
  原运行要求、源码、依赖/接口、后端和每批预算保持原样。模型继续独立编制验收。
  没有提供 plan/acceptance_plan，没有向真实 pipeline 注入内部状态，没有恢复失败轮。

材料摘要错误现在指名 `input_contract.review.materials_sha256`、expected、actual、checked
路径/sha256，并说明列表摘要与单文件 hash 不同。只提供主机计算的摘要用于模型修正声明，
不代填确认，不改变分类、来源、测试或独立审阅条件。离线仅在内存中诊断旧失败计划，没有
改旧文件、发布计划或授予资格；继续校验仍能报告下一项原有缺陷，未借此绕过后续检查。

资源提示明确既有非负数值字段的含义：0 表示所选入口与有限验收范围未识别到额外来源下限，
不是零消耗或任意工作量保证。必须引用实际入口、依赖及用法，不可把主机容量/容器预算
伪装成来源事实；未测峰值留在局限中，真正不能评估的必需资源仍保持 unknown 并阻止执行。
未更改枚举、数值边界、引用校验、资源门禁或任何业务断言；仅明确模型如何表达已有信息。

`-04` 还暴露了可复用环境引用生成的 `package/SKILL.md` 的问题：该文件被工具请求闭包排除，
跨文案后引用不一定成立。`shared_tool.check_plan` 现在确定性要求资源引用来自 request.files
内的稳定源码/来源；错误给出字段、actual 和允许路径，规划可在原预算内修正。已核对旧描述符
与 Open Babel 制品均引用稳定来源，记录不变且仍受支持；`-04` 的新记录则明确不再具备复用资格，
没有删除镜像或覆盖旧记录，也没有把失败 Skill 的状态写入工具制品。

苯酚期望来自相同 Release_2024_09_6 的官方测试，
见 [MinimalLib 测试](https://github.com/rdkit/rdkit/blob/Release_2024_09_6/Code/MinimalLib/tests/tests.js#L47-L49)
及 [核心 MolToSmiles 测试](https://github.com/rdkit/rdkit/blob/Release_2024_09_6/Code/GraphMol/MolStandardize/testFragment.cpp#L92-L96)。
新增来源保存 ref、文件、Git blob SHA 和小段原文，不使用当前工具输出当独立 oracle。
新约束保留 CCO/苯酚两行、落盘、顺序、输入保护和两个 canonical 字段，另保留原非法/空输入
和混合文件全部义务；没有改原始来源、删除第二行或以乙醇单行替换失败用例。

历史错误 A/B 的 `check --config` 均 exit 1，具体缺少 `requirements.txt`，实际同名文件为
`resources/requirements.txt`；精确列表还单独指出后者为额外交付。历史记录、冻结包和旧工具
目录保留，负例不把它们静默改成新资格。
负例的 `required_delivery_file_missing` 明确返回 `path=requirements.txt`、
`expected.present=true`、`actual.present=false` 和
`actual.other_paths=["resources/requirements.txt"]`；额外文件的
`unexpected_delivery_file` 则返回 `expected.present=false`、`actual.present=true`。
两项均附 `prompt` 与 `runtime_defaults.requirements.0` 的原始要求引用。

新批次从普通配置完整生成，没有手工 acceptance_plan 或继承旧执行资格：

| `-05` 新批次 | A | B |
| --- | ---: | ---: |
| Docker 检查 | 17/17 | 16/16 |
| 当前输出及正式库资格 | 通过 | 独立通过 |
| 发现 / 编写 / 独立审阅 | 1 / 1 / 1 | 1 / 1 / 1 |
| 组合环境与验收规划调用 | 6 | 0 |
| 验收专用模型调用 | 0 | 3 |
| 环境 build / 工具 build 调用 | 1 / 1 | 0 / 0 |
| 全部准入阶段调用 | 9 | 6 |
| CLI 端到端秒数 | 1598.133 | 905.731 |

组合模型的一次调用同时承担环境与验收，不重复记为两次。A 前五个草案、B 前两个草案
均被原有门禁具名拒绝后自然修正，原始 rejection 与回执留存。B 的错误分别是总作用域未声明
文件操作的 `report` 目的、来源引用片段未原样出现；未人工替模型写计划、放宽引用或删除用例。
供应商仍为原生阶段 Codex CLI `gpt-6-astra`，结构化阶段 DeepSeek API `deepseek-v4-pro`。
每批仍为原 16 次准入调用封套，options/预算按原配置。

两轮绑定同一 ToolArtifact
`c3bcaa0b388085b6ee559ce6dcbad418bdebcc5d6028fe7a82fc5d3e1fc8c51c`，
当前本机 Docker image ID 为
`sha256:7b5dcc7e129bd5a37833042084fef1e703ee67bc316d642b0097dafcd23a6b24`，
不把它称为 OCI manifest digest。A build 为 `20261101T213858-8080f16b`，
B 为 `20261101T220629-4ae1f795`；两份 SKILL.md、revision、验收编制与执行尝试均独立。
双行 canonical 义务在 A 的原生 `check-generated-valid_file_persisted_rows` 和 B 的
`file_persisted_rows` 中均保留。两个新输出 `check --config` 均 exit 0，冻结要求与原配置要求
均通过，当前库 `runtime-inspect` 也分别 accepted。旧路径的 ToolArtifact 未被当成新版本命中。

`-02/-03/-04` 失败生成共消耗 15 次准入阶段调用，全部保留，不计入成功批次。
每批仍沿用 16 次调用封套及原供应商/阶段预算，没有额外付费探针。这里的调用数是 pipeline
准入阶段数，不等于 Codex CLI 内部工具轮数、API 底层网络尝试数或供应商账单总量。
`failed-rounds-current-audit.json` 用实际 runtime 上下文重新检查，三轮资格均为 false；
没有把 freeze 时的初始 qualification 声明当作最终观察。

附加只读审计最初只认识 planner 的单条声明式断言，误报缺少两行 canonical 及混合文件续跑。
实际独立生成的原生程序已从落盘文件读取行、断言两个字段、输入保护和顺序，真实报告也保存
其业务子进程 exit 0/2、行内容与 byte_count。审计现同时检查锁定程序的文件读取/调用形态、
断言和观察结果；不执行或改写该程序。原识别失误保存于 `read-only-audit-initial-failures.json`，
另用离线探针确认 stdout 自报、外层失败和非 JSON 结果不能满足此识别路径。
业务用例、锁定契约和执行记录未改。
另一处附加审计曾误要求 B 存在构建 `image.id`：完整命中本来不构建，因此应核验当前冻结
artifact、receipt.tool_artifact、两处 image ID、具体 artifact ID 和零构建计数，再由原有
qualify 核验当前 daemon/image/执行证据。现支持此路径，原误报另存
`read-only-audit-shared-hit-iidfile-failure.json`。离线探针确认错误 image、缺失冻结绑定、
伪造命中与非零构建不能通过。最终 `audit-ab.json` passed:true、33/33。

真实操作使用公开入口（`record_public_cli.py` 仅记录同样的子进程参数、退出码、经 redact 的
stdout/stderr，不调用 prepare/seal 等内部接口）：

```powershell
$root="E:/Users/27343/Docker/descriptor-layout-cli-20261101-05"
$env:CHEM_AGENT_SHARED_TOOLS="$root/shared-tools"
$env:CHEM_AGENT_SHARED_ENVIRONMENTS="$root/shared-environments"
python -m creation_pipeline build "$root/descriptors-a.json" --preflight
python -m creation_pipeline build "$root/descriptors-a.json" --state-dir "$root/a/state" --library-dir "$root/a/library" --keep-debug
# A 完整通过并发布工具后才启动 B。
python -m creation_pipeline build "$root/descriptors-b.json" --state-dir "$root/b/state" --library-dir "$root/b/library" --keep-debug
python -m creation_pipeline check "$output_a" --config "$root/descriptors-a.json"
python -m creation_pipeline check "$output_b" --config "$root/descriptors-b.json"
```

新目录中的 registry 未命中不等于 Docker 冷启动；本轮保留已有镜像和 BuildKit 缓存。
build 数量只统计调用，不冒充依赖实际安装次数；未以镜像虚拟大小推算实际占用。
上述秒数为这两次实际 CLI 全流程耗时，包含不同的模型修正轮数及独立编制的检查工作量，
不作为受控的性能/存储基准；此前三路径测量仍见
[专门的对照报告](shared-tool-path-metrics-20261101.md)。复验应使用新的独立证据根，勿覆盖本轮。

离线最终代码：`python -m unittest discover -s tests -q` **723 项，720 通过、3 跳过**。
新增 22 项回归覆盖通用文件名/嵌套路径、原文引用、错目录和大小写、额外文件、安全与冲突、
默认目录例外、不能篡改已哈希契约、损坏记录、审阅/执行标记不能豁免、CLI 外部配置不能放宽
冻结要求、协议 1 兼容、准备前零模型调用的失配与内容撤销，以及材料列表摘要错误的精确
反馈且不自动回填确认、资源提示澄清但 unknown/引用门禁不变，以及跨文案的资源引用闭包和旧版本可用性。
离线用例阻止真实模型和
Docker 请求。三个提示自检通过；按原顺序 freeze。路径改动未改变 planner 冻结内容；后续
资源澄清仅预期新增 11 行 POLICY，并更新对应 prompt/manifest/provenance，schema 约束未变。
差异有明确来源，没有为消除未知漂移盲目刷新。
最终轮后回归日志在 `-05/postflight/`：723 项用时 171.023 秒，三个 check 各自 exit 0。

旧自包含 Open Babel 原合同从普通 CLI 导入到独立库，先 `not_run`，随后 `runtime-resume`
重新执行 **8/8**，0 新模型。此项是旧合同重验，不是新生成批次，也不是新路径要求的证明。
原 72/72、旧描述符两批、其他轮的安装/重验均未计入本轮新生成统计。
本轮新成功生成是 **2 批、33/33**；失败生成另有 3 轮（两轮 blocked、一轮 10/11），
失败准入 15 次加新成功 15 次，共 **30 次准入阶段调用**。旧合同 8/8 单列，0 新模型。

已实现：明确文件清单/根文件的确定性要求、版本化冻结与多处核验、普通 CLI 正负例、
共享工具命中后的当前审阅/验收/资格、新旧模式回归。未支持的任意自然语言解析、目录/
通配符/负向路径规则及远端/OCI 分发保持前述边界；本轮没有扩展平台或变更这些边界。
