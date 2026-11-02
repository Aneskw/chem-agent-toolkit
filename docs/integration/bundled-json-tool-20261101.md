# P2：文件相对 JSON 资源的精确工具复用

基线 `942d57e`；最终核验日期 2026-11-02。本轮只扩展一种能力：有限形式的 `__file__` 相对包内 JSON 读取。
本轮新增有限资源读取协议、普通编写/审阅执行布局 handoff，以及更具体的引用错误诊断。
最终证据索引为 `validation/deepseek-api/bundled-json-tool-results-20261102.json`。
**P2 本轮有限范围已完成**：普通 CLI A 14/14、恢复后新目录 B 20/20，共 34/34。
B 自动命中同一 ToolArtifact，环境规划、环境构建、工具构建均为 0，仍有独立审阅、
2 次当前验收专用模型调用及独立新执行。A/B 当前资格均通过；失败轮没有获得资格。
`8e25655` 是此前受 Docker 故障阻止的快照，不再代表最终结果；原失败及阻止证据完整保留。

## 范围选择与实现

核对 `shared_tool.describe()`：多模块 .py、本地包与数据早已全量进入 request.files。
新增支持不能称为“首次支持多模块/数据”。原 v1 对任何 `__file__` Name 明确拒绝，
原样入口常用的模块目录定位因此不能共享；旧样例的测试程序也使用该惯例。
本轮新增独立 `shared_tool_image_v3` / `closed-python-json-data-v1`，v1/v2 边界不变。

固定语法、声明、身份、错误及迁移见 [资源协议](../pipeline/bundled-json-tool-protocol.md)。
核心为 `runtime/bundled_data.py`；必须声明 module/path/sha256，文件存在且实际原字节 hash
相同、有效 UTF-8 JSON、每个声明都有该模块中的固定读取，才接受。闭包仍含全部 package
支持文件及 sources，仅排除生成 SKILL.md；声明也进入请求键。运行时核验两份镜像树、
当前包与来源、入口、当前依赖和本次锁定合同，不从资源身份推导业务资格。

模块、数据、依赖/接口任一变化返回新请求或具名拒绝；未知路径、编码、别名/反射式 Path、
中间路径变量、父级跳转、写入、任意其他 __file__ 用途均不推断兼容。不是任意 Python
闭包证明，不增加通用动态加载、任意 subprocess 或外部挂载资源。

## 新整合来源的真实性与边界

`validation/deepseek-api/bundled-json-input/source` 是**新增整合来源样例**，不是历史原包。
原 `chem-agent-toolkit_newpipeline/tools-skills/rdkit/chem-rdkit-descriptors` 只读；
scripts/calc_descriptors.py 和 requirements.txt 复制后原字节不变。新 scripts/triage.py
调用该真实 RDKit 模块计算分子描述符，并用同目录 data/rules.json 的分子量阈值进行筛选。
没有伪造化学结果或把旧执行输出当本次证明。规则 id 为 demonstration-screen-50-v1，
50.0 是此调用方样例的操作阈值，不是药物相似性、安全性或通用科学标准。

新入口只声明 --smiles/--help：CCO 46.069、供/受体各 1、selected=true；苯酚 94.113、
selected=false；两者返回实际 policy_id 与 maximum。非法和空输入保持原错误及 exit 2。
新入口不声称支持文件输入。原计算模块的 --input/--output 接口和 P0 原绑定未改变；
没有把旧 Skill 的文件合同缩成新入口合同来获取通过。

两份配置只有文案/批次标签不同，明确运行要求、依赖、平台、接口、资源声明、源字节相同。
沿用 Codex CLI 发现/编写/独立审阅，DeepSeek API 关联/规划/验收；原 16 次阶段调用封套、
超时、token、重试与依赖 pins 保留。没有 plan/acceptance_plan/tool_artifact 注入；实际生成
使用普通 CLI，record_public_cli.py 仅记录原命令、退出码和经 redact 的输出。

## 失败与修复纪律

- `bundled-json-postflight-20261101-01`：新登记测试 fixture 遗留闭包外 sources/tool/main.py
  引用，产品正确拒绝，45 项中一项错误；改测试材料，未放宽闭包门禁。
- `bundled-json-postflight-20261101-02`：修正后 743 项中 740 通过、3 跳过，三个提示自检通过。
  这是引用诊断补齐前的结果，不作为最终代码证明。
- `bundled-json-cli-20261101-01`：A 已独立审阅通过，但模型在组合规划中反复把生成文案
  引作原 README；目的声明和正则错误也被具名拒绝。7 次准入调用，最终 planning_no_progress，
  零构建、零业务执行、资格 false。未 resume/restart，没有改原来源或删失败义务。
- 修复 `acceptance.grounding_problem`：原错误只显示提交片段，现附实际指定来源中最相近的
  原文行（至多 1000 字符）。候选明确标为 diagnostic only，不是获批断言；严格引用条件
  不变，不自动回填或改计划。离线回归证明原引用仍被拒、输入和来源文件不变。
- `bundled-json-cli-20261101-02`：使用完全相同两份配置和来源、全新环境/工具登记目录，
  启动独立新轮。不是恢复上一轮，也未扩大预算。

补自动布局上下文前的日志 `bundled-json-postflight-20261101-03`：**744 项，741 通过、3 跳过**；
针对性集合 94 项（含原有输入/共享/平台测试），三个提示自检、平台契约检查全过。
其后补充自动上下文和 Path 间接重绑定拒绝；最终代码在 `bundled-json-postflight-20261102-04`
完成 **748 项：745 通过、3 跳过，无失败/错误**，针对性集合 **98 项通过**。
相对基线 734 项新增 14 项有效回归；三个提示自检和平台契约校验 exit 0。
完整回归约 468.78 秒（unittest 内部 467.445 秒），无新模型请求。
未修改提示/schema，无需 freeze。覆盖数据/模块变动、未声明/缺失/非法资源、旧 v1
拒绝、新 v3 登记解析、依赖/接口变化、旧版本保留、文案无关性和诊断不代填。

## 普通入口与证据

```powershell
$root="E:/Users/27343/Docker/bundled-json-cli-20261102-04"
$broot="E:/Users/27343/Docker/bundled-json-cli-20261102-06"
$env:CHEM_AGENT_SHARED_TOOLS="$root/shared-tools"
$env:CHEM_AGENT_SHARED_ENVIRONMENTS="$root/shared-environments"
python -m creation_pipeline build "$root/skill-a.json" --preflight
python -m creation_pipeline build "$root/skill-a.json" --state-dir "$root/a/state" --library-dir "$root/a/library" --keep-debug
# A 完整核验后才启动 B；失败目录不复用。
python -m creation_pipeline build "$broot/skill-b.json" --preflight
python -m creation_pipeline build "$broot/skill-b.json" --state-dir "$broot/b/state" --library-dir "$broot/b/library" --keep-debug
```

`audit_bundled_json_cli.py` 只读核对原字节、当前 qualify/库资格、独立 native session、
真实直接入口输出和原模型/构建计数；负例只在隔离 context 副本中形成新请求，针对真实登记的
具体旧版本调用 select，记录字段/路径 expected/actual，不改原记录或授予新资格。
这些解析负例不是新的模型生成批次，也不冒充普通 CLI 新生成；双 Skill 的生成则均使用 CLI。

普通配置各轮实际结果（最终成功配对仅 04/A 与 06/B）：

| 轮次 | 结果 | 准入模型阶段 | 环境规划 | 环境/工具构建 | 资格与限制 |
| --- | --- | --- | --- | --- | --- |
| 04/A `20261102T002955-86ac3232` | 14/14，ready | 5：发现/编写/独审各 1，组合规划 2 | 2 | 1/1 | 故障时暂不可用；恢复后当前资格复核通过，绑定与原字节不变 |
| 04/B `20261102T004457-30403bce` | 验收计划请求中断 | 7 个已完成 stage，另 1 个已发请求无结果 | 已进入命中后的验收专用阶段 | 无执行完成凭据 | 没有 summary、执行报告或资格；不计成功 |
| 05/B `20261102T101729-103ae39a` | 独审通过，runtime_blocked | 3：发现/编写/独审各 1 | 0 | 未进入构建 | docker_unavailable；验收模型 0，实际执行 0，资格 false；这些 0 不是成功复用性能 |
| 06/B `20261102T112835-7e380d2b` | 20/20，ready | 5：发现/编写/独审各 1，验收专用 2 | 0 | 0/0 | 自动精确命中 A 同一 artifact；当前独立资格通过 |

A 具体 artifact_id 为 `d40620eb9a2face843c14d80f899f9304ff28be3f356c16b7141c7147dfb2be9`，
request_key 为 `b526d9105559a4bcdafbc4b5a9e1468d454fe5a3fb7c14f91c73f9a2f4c627ac`。
本机 image_id 为 `sha256:2025a3abbaa26559349a684e1d80a98a3fd6de0bc99ab2b13ec3bb6a67a5b3e3`，
不是 OCI manifest digest。05/B 的请求键相同，但无 daemon 身份时不能认定可用命中。
候选中的 different_daemon 是 engine_id 缺失时的既有粗诊断，不是观察到了另一个 daemon；
主阻止原因及路径为 docker_unavailable / dockerDesktopLinuxEngine pipe 缺失。

受阻快照共 35 个已启动准入阶段、34 个完成 receipt：失败 A 两轮 12，中间 A 7，
普通配置 A 5，中断 B 已完成 7/已启动 8，主机阻止 B 3。恢复后 06/B 新增 5 次，
全轮累计 **40 个已启动阶段、39 个完成 receipt**；最终 A/B 配对单列 **10 次**。
06/B 首份验收草案的 README 引用不逐字匹配，被门禁拒绝；第二份在原预算内自动修正后锁定执行。
没有手工 plan、改原来源、继承旧 tests/passed 或降低业务要求。每批 16 次封套未变；
这些是 host 准入阶段数，不等于 Codex 内部 turns、API 请求数或计费调用数。
阶段 receipt、usage、重试尝试与实际命令分别保留，不声称所有模型调用为零。

第三轮 `bundled-json-cli-20261102-03` 的 A 在补充协议来源后完成 15/15、7 次准入调用。
原失败程序在只读挂载的完整当前冻结 Skill 包上重验通过：代码和四个期望摘要未改，
只把目录参数从工具镜像路径改为 `/input`，原记录保持失败。这是单列基础设施核验，不授予资格。
该轮揭示普通原生上下文缺少共享执行布局，不作为最终普通配置的双 Skill 证明。

随后主机 `candidate_context` 自动向编写和独立审阅提供相同的 tool_execution_layout：
当前 Skill 完整包与 ToolArtifact 不是同一个对象，host 仍严格检查完整 Skill 布局，镜像检查
实现文件集，不制造 SKILL.md。没有把它作为化学事实或执行证明，也不暴露资源凭据。
该 handoff 修复不增加另一项工具能力；Path 异常/模式/属性重绑定也补上确定性拒绝。
第四轮 `bundled-json-cli-20261102-04` 使用最初普通配置和原业务来源，无额外协议来源，
以同一原封套重新生成 A。该轮 B 在 acceptance-planning/4 请求后进程中断；观察时无活跃 Python
进程、CLI result、完成 summary 或执行报告，原因未知。3 个 native receipt、4 个已完成验收
receipt 和第 5 个已发请求保留；不把该请求记成完成，也不把此 B 计为通过。
第五目录 `bundled-json-cli-20261102-05` 只重新生成 B，配置原字节不变，继续使用第四轮登记目录；
没有复制 pipeline 内部状态、resume/restart 或继承资格。各轮候选使用独立 state/library。
第三轮的协议补充文件作为历史证据保留，不是最终配置的人工步骤。

2026-11-02 10:27 本机只读 CLI runtime-inspect 观察 A historical_execution=passed、
qualification.accepted=false/deferred=true，原因是当前 Docker API 不可用。Docker Desktop
正常启动失败，错误指向 `C:/Users/27343/AppData/Local/docker-secrets-engine/engine.sock`。
该零字节 reparse IPC 文件无法访问；单独改名、父目录可逆改名、普通移除都被 Windows 拒绝，
没有成功移动或删除它。进一步解除 reparse 标记被自动审批以“目标语义未知，可能损坏文件系统
或 Docker 状态，超出有限修复授权”拒绝；没有绕过，也没有修改 ACL、全局配置、镜像或缓存。
当时需用户在桌面修复 Docker；这和此前 B 的进程中断是否同因未知，不推断因果。
05/B 启动前仅重新做了配置 preflight，没有再次探测 Docker，导致 3 个 native 阶段后才被阻止。
这是本轮实验纪律的缺口，不是必要的模型探针；后续新轮必须先做零模型的 daemon/镜像检查，
配置 preflight 不能代替该检查，也不能用手工 plan 绕过主机阻止。

`offline-preservation-audit.json` 确认当前产品源码、来源、旧 P0 绑定目录原字节不变，
A bundle 完整、登记制品等于 A 内嵌的具体制品记录。它**不证明当前镜像可用**。
此前四个真实 registry 解析变更负例及 A 的当前资格复核在 daemon 停止前已通过；
之后仅可复核元数据与原字节。不能用这些记录恢复 B 资格或把旧 passed 写入当前结果。

当时的待补项已在恢复后的 -06 新轮完成，见下述核验。04/B、05/B 均未 resume/restart。
daemon/镜像身份不同仍应明确 miss；不能为完成配对而改 registry、替换具体版本或继承资格。

2026-11-02 11:27 用户确认恢复；`bundled-json-cli-20261102-06` 在付费阶段前完成零模型、零构建
核验，daemon 仍为 `a7981e1d-64c3-431d-8287-8dad803ceaf6`，原具体工具镜像可用，A 与两份旧 P0
绑定当前资格通过、文件不变。没有继续执行此前被拒绝的修复动作。新 B 配置与最初配置相同，
仅共享原 registry，不复制旧计划、内部状态、执行或资格；新证据写入 -06，不改旧实验目录。
审计脚本的 `--output-root` 只改变证据保存位置，并额外核对跨 Skill 的独立 session/attempt，
没有修改产品运行时或资格规则。

恢复后的三个提示自检及平台契约复查通过，见 -06/post-recovery-checks-02；首次两个检查只因
沙箱 C 临时目录写入/清理权限失败，保留 -06/post-recovery-checks 原日志，改回既有工作区 TEMP
后在新目录重查通过，未 freeze。748 项完整回归、98 项针对性集合仍引用 -04 已通过结果；
逐文件 SHA 确认恢复前后产品代码相同，本次未重复全套回归，不把旧结果当作改动后新测试。

- `audit-ab.json`：34/34、同一 artifact/image、不同 Skill 文案和 revision、不同编写/独审 session、
  不同执行 attempt；当前包/镜像/来源完整、四类直接入口业务输出正确、A/B 与两份旧 P0 资格通过。
- `operations/check-current-b`：公开 check 按原调用方配置核验交付布局通过。
  `operations/inspect-restored-a` 与 `inspect-current-b` 的公开当前资格查询均 accepted=true。
- `failure-isolation-after.json`：工具与环境 registry 全部原字节不变；两份旧 P0 绑定不变且仍合格；
  之前两个失败 A 和主机阻止 B 共三份 Skill 当前仍不合格。原始来源和已回归产品代码不变。
- `original-package-check-b.json`：原失败程序及四个期望摘要，在当前 B 的只读完整冻结包上通过，
  仅纠正目录 argv；与 A 的同类复核共两条最终配对基础设施证据，不计入 34 条生成验收。
  中间轮另有一条同类基础设施复核，三条均不改变旧失败用例或授予资格。

原四类解析负例沿用 -04/negative-probes.json：在隔离 context 中分别变更模块、JSON 原字节并更新
声明 hash、依赖和接口；对真实具体旧版本都得到 selected_request_mismatch，含字段 expected/actual。
没有为这些负例新增模型生成或授予资格。数据 hash 未更新、声明缺失、动态路径等另有离线回归。

## 时间与存储观测边界

`-06/timing-observations.json` 保存实际回执的各模型阶段耗时、全部用例与固定四种直接业务输入的
容器 wall，以及 CLI 总 wall；容器 wall 包含启动/清理，不是化学计算内核时间。

| 观测 | 04/A | 06/B |
| --- | ---: | ---: |
| CLI wall 秒 | 689.965 | 783.517 |
| 组合环境/验收模型秒 | 168.987 | 0 |
| 当前验收专用模型秒 | 0 | 348.042 |
| 全部用例容器 wall 秒 | 31.461（14 条） | 35.419（20 条） |
| 环境/工具 build 调用 | 1/1 | 0/0 |

B 总时间更长；不同模型响应、独立测试数量、生成文案和相隔多小时的主机状态使总时长不可作为
受控加速比。这里确定的是省去环境 planner 和两类 build，必要模型阶段总数双方均为 5。
来源、依赖、接口、资源身份、平台与要求相同，业务输入相同；不把不同阶段 wall 相加作同一口径。
实际物理 Docker 存储差分本轮未测；registry 不变及无新 build 不等于测得磁盘节省。
此前 P1 三路径受控测量仍见 [测量报告](shared-tool-path-metrics-20261101.md)，与本轮计数分开。

新 registry 不代表 Docker 冷启动；保留已有镜像及 BuildKit 缓存，不把 build 次数当实际依赖
安装次数。当前任务不作跨工作量性能/磁盘节省声明。没有远端分发、OCI 平台或常驻 worker。
平台契约增加 v3/policy 与必需数据声明，SkillBinding/ExecutionAttempt 字段未扩展。
本轮新增真实验证限普通 CLI 配对、当前资格和精确解析负例；不将旧 v1/v2 安装/导入/迁移实验
重新标成 v3 真实交付矩阵。v3 交付需支持该 ABI 的本机运行时和具体制品；未知 ABI 或缺失制品
不能降级或继承资格。通用动态加载、任意 subprocess、远端仓库和 OCI 分发仍不支持。
