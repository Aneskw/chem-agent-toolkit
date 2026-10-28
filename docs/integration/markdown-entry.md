# Markdown 交付与 Docker 接口专项

本次实现和验证基于 `integration/recap-comparison` 的 `71f887e`，开始时工作区干净、没有后续提交、未发现适用 AGENTS.md。新工作分支为 `integration/markdown-entry`。没有修改 partner 原版，没有运行 DNA，也没有改写旧验证目录。

**结论：A 历史 RECAP Markdown 候选恢复完成，真实 Docker 9/9 通过并 accepted；B 正常新创建完成内容与入口关联审阅，但 planner 在 600 秒超时，仍为 candidates。不能宣称两项实验或完整新创建全部通过。**

## 复用和增量

| 现有接口 | 复用保障 | 必要增量/对应验证 |
|---|---|---|
| preparation.bind/handoff | 原样脚本唯一身份、源文件复制及指纹 | entry.py 分离关联与入口；唯一完整 Markdown Python 块的字节定位、提取、模型提案和独立批准 |
| review_snapshot / generation.author.review | 独立 Native reviewer、源码和需求核对 | binding_verified；明确审阅调用契约与来源语义，不接受提案者自证 |
| mapped_checks | 把原作者检查映射进容器 | 原检查不改；允许其直接读取最终 Markdown，仍纳入锁定测试。提取脚本不是另一份业务实现 |
| planner / preparation / service | 环境计划校验、JSON patch、无进展停止、runtime-prepare | 实际提取入口作为 script；语法错误标出用例名；恢复最后一个未验收的拒绝方案，避免从头重规划 |
| seal/verify / LocalExecutor / locked_inputs | 文件冻结、实际镜像文件身份、完整适用测试、当前资格 | 每次重验检查文档/定位/代码字节对应；跨平台清单仅规范排序，不忽略任何路径、hash、大小或重复项 |
| pipeline.build --plan | 原主流程、作者修复、独立重审、逐候选处理 | 未变的已审阅受阻候选可复用；选定 catalog 中较新拒绝优先于旧计划通过；修复期间锁定原作者检查 |
| Sources / source_identity | 原来源与快照体系 | 承载仓库身份与上游身份分开；固定 GitHub raw commit URL 提供上游 repo/commit/path/hash；旧引用不猜测为上游版本 |
| store/catalog | accepted/candidates、事务、历史、恢复 | 没有新增库管理或晋升逻辑；通过原接口晋升、记录更新与隔离 |

协议详见 [delivered-entry.md](../pipeline/delivered-entry.md)，架构图为 [integrated-flow.mmd](../pipeline/integrated-flow.mmd)。未删除旧实现或历史归档。

## 支持与完整性边界

自动 Markdown 入口只支持最终 SKILL.md 中一个完整、无缩进的 ```python 或 ```py 围栏块。程序记录文档 hash、块 hash、字节起止、起始行及规则版本，原样写入 `entry/skill.py`。CRLF 也逐字保留，不补 import、不拼接多块、不插入函数调用。函数使用必须有来源支持的明确调用说明和适用检查。

语法错误、未声明上下文属于可确认的内容缺陷；多块/交互/动态执行等属于协议能力限制；关联证据不明或语义审阅拒绝属于未解决输入。Docker 暂缺在模型关联之前检查，保留资源类别。无法判定时不猜测为内容错误。显式总时间与单次调用限制继续约束新关联/审阅调用，production 不增加隐含总配额。

模型提案结构、来源路径、引用、指纹先由程序核验，语义再由独立 reviewer 核验。程序提取物进入现有环境/修订/冻结契约；执行前重建匹配关系，实际镜像中同时核验提取文件和完整交付文件。文档正文、代码、支持文件、来源、环境或契约变化仍使相关资格失效。

作者原有三个检查读取实际交付 SKILL.md 的代码块，分别检查终端结果/层级、合法空 leaf、非法输入。本次未以另写 RECAP 实现代替它们。

## 来源身份修正

原问题来自 Sources.add 对本地子目录执行 `git rev-parse HEAD`，把包含下载文件的集成仓库提交写进 resolved_ref，作者随后误用。现在子目录元数据是 `carrier_repository`；模型视图对无上游仓库依据的本地/旧引用给出明确含义，不再把它呈现为已核验工具版本。

A 保留历史来源记录，依据实际 inventory/snapshot 身份审阅。作者真实修改了唯一一个来源说明段落：删除 `cf7a9c5` 及 dirty 上游暗示，改为 snapshot `0cc5e8415624d4472eeee8462afacf5dc5c88d6de96bf8860acaaf338281e436`，声明上游版本未知。旧产物未改；差异在 `a-author-source.diff`。

B 输入使用与前轮完全相同的官方字节，改为可核验的固定 URL + SHA-256：RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8` 的 Recap.py 和 license.txt。上游元数据直接进入资源/作者/审阅/规划交接。B 新生成 Skill 正确写出该官方提交及链接，没有写集成仓库提交。来源固定不等于证明任何未来安装版本兼容。

## 实验 A：历史候选恢复

初始候选来自上一轮保存的合并版输出，导入隔离 `E:/Users/27343/Docker/me-a`，未继承旧执行通过状态。

1. `runtime-prepare` 真实模型提出 API 关联；独立审阅确认关联，但拒绝旧文档的来源表述。
2. 一次从旧保存计划开始的续跑得到不同审阅结论。主动停止并保留了该尝试；**未用后一次通过覆盖先前拒绝**。随后补齐现有主流程对较新 catalog 拒绝意见的承接。
3. `build --plan ... --library-dir me-a` 复用旧发现和交付内容，真实调用作者修正来源说明，再独立审阅。没有发现调用。作者未修改 Python 业务块或原作者检查。
4. 真实 planner 的初稿含 Python 字符串换行转义错误。修复第一例后另一例出现同类错误，原无进展判定因诊断未带用例名而提前停止。修复诊断定位，并让原 `runtime-prepare` 使用保存的拒绝方案继续原 patch 协议。所有转义/JSON 类型修正由真实模型完成，程序未手工改方案或正确预期。
5. 真实 Docker 构建、全部锁定测试通过，原 store/catalog 晋升 accepted。最后一次程序修改后，又用 `runtime-validate` 核验同一真实镜像并完整重跑。

最终修订：`rev-35d8bfc8d73c54fb508c58847e6883a2290b8ef78cce77c48a6181a24f6cea0b`。

真实镜像：`sha256:5fec1479fc3475c5d22dc879423f3fd113d7a6390270cb6066145106cc3efab9`。

运行记录显示 Python 3.11.17、RDKit 2026.09.1。planner 选择了容器内 pip 安装未限定版本的 RDKit，记录了实际依赖版本和镜像 ID；本次不是“用上游固定 commit 编译出完全同版二进制”的证明。今后重建不能直接继承此次通过状态，须重新核验镜像与完整业务。

**9/9 真实通过**：

- imports/版本记录；
- 确定性提取的实际交付入口及其三片段结果；
- 固定原始 Recap.py 自带单元测试；
- planner 的交付示例、合法空结果、输入 guard 三项检查；
- 原作者的示例/层级、合法空结果、非法输入三项检查。

原作者三个检查与完整 test_definitions 指纹不变；Python 块字节指纹不变；来源 inventory 不变。SKILL.md 文档指纹因真实作者修正来源段落改变；绑定、环境、验收契约建立了新版本。全部前后指纹在 `a-fingerprints.json`；历史修订与失败证据保留在 catalog.history、a-runtime-library 的 evidence/preparations 和旧对照目录中。

默认 library 查询返回正式项，真实 install 成功；最终重验 `business_acceptance=passed`、`accepted=true`。这是**历史恢复并含必要内容修订**，不是不中断全新创建，也不是新证明的运行后业务缺陷/冻结 oracle 修正闭环。

## 实验 B：固定化学来源正常新创建

正常 CLI 新 run `20261026T132637-8b6d7bc8`，独立 state `me-r`、库 `me-b`。没有输入历史 Skill、完整答案、预制 adapter、测试计划或 Dockerfile，也没有要求作者输出脚本。

真实发现、作者、内容审阅、来源关联提案及独立批准完成，实际交付仍是 Markdown Python 块。作者阶段自行处理了许可证位置和检查字符串转义问题；源码文件未由开发助手修改。内容与入口审阅均通过后进入原 planner。

planner 单次调用在 **600 秒**超时。持久记录只有 `thread.started`、`turn.started`，没有结构化方案/工具事件/完成事件。进程观测确认对应 codex 子进程存在、父进程和启动时间；记录了完整 prompt、实际 CLI 参数、stdout/stderr、timeout.json。非敏感配置为 gpt-6-astra、reasoning effort low；Native 采用 ignore-user-config，而原 tool-free caller 继承用户配置，这个差异已记录，但没有证据认定它就是根因。

相同 tool-free 调用链在 A 的关联和 planner 中能返回结果，故不能宣称整体模型服务不可用；也不能由开始事件证明上游已经完成请求处理。没有日志支持将此归为网络故障或化学业务错误。根因仍未查明。未原样重试、未只延长超时、未手工给计划绕过，也未换业务任务。

B 修订 `rev-2b405edc86958b3d155a650495c5985fca33bf561c90978f5a664fb545336a3d` 保留于 candidates，默认查询隐藏、显式候选访问成功、安装拒绝。**未构建业务镜像、未执行业务测试、未晋升。** A 的成功不能替代 B。

## 机制、故障与真实证据分类

- Windows 最终全量：230 项，228 通过、2 项平台跳过。Linux 恢复/入口补验：29/29 通过。
- 新机制覆盖：唯一块逐字提取、CRLF、错误定位、多块/交互拒绝、未定义上下文、显式时间限制、提案 schema/引用/独立审阅拒绝、冻结与材料漂移、具体用例语法诊断、保存计划复用与较新拒绝优先。
- 原脚本、锁定断言、资格与镜像漂移、候选隔离、事务回滚、多候选 partial 等既有回归继续运行。没有删除关键断言来消除失败。
- Linux 初次缺 git/jsonschema/可写测试区，另构建测试专用容器解决，没有安装宿主依赖。随后发现路径大小写排序差异，规范清单比较顺序后，原“新主机不得继承资格”断言通过。未改历史清单、未忽略文件/hash/大小。
- 一次提权全量测试因 Docker 可见使原测试夹具进入真实模型，已停止并保留记录。最终机制回归仅在测试子进程 PATH 排除 DockerDesktop，避免把偶然真实调用当作单测；Docker/model 故障由明确 doubles 测机制，真实化学证据由 A/B 独立提供。
- 本轮未做人工业务故障注入。模型真实生成的文件位置/检查调用问题、A 的来源表述修订及未锁定 planner 提案修正，不能宣传成运行后内容失败或冻结契约自动修复的新增证明。
- 测试专用镜像构建不是 RECAP 业务构建证据；业务镜像身份只以上述 A 记录为准。

## 证据、文件与复现

所有本轮材料在仓库 `validation/markdown-entry/`，约 8 MB，原始工作目录也保留。归档不改写冻结路径或历史记录；复制的库需要显式迁移核验后才能在新路径获得当前资格。

```text
validation/markdown-entry/
  input.json auto-spec.json commands.json interventions.json
  a-runtime-library/          # A catalog、所有历史/准备/镜像/业务证据
  a-repair-state/             # 真实作者修订及独立审阅、无发现调用
  a-interrupted-state/        # 已停止的审阅分歧尝试，不能算成功
  b-state/ b-library/         # B 新创建、入口审阅及600秒超时
  a-fingerprints.json a-author-source.diff summary.json
  planner-process-observation.json model-config-observation.json
  a-latest-code-revalidation.log cli-results.json
  final-windows.log final-linux.log linux/
  evidence-inventory.json
```

可直接对比：

- A 修订后的真实正式 Skill：`validation/markdown-entry/a-runtime-library/accepted/rdkit-recap-terminal-fragments/SKILL.md`。
- B 本次新生成、尚未合格 Skill：`validation/markdown-entry/b-library/candidates/rdkit-recap-terminal-fragments/SKILL.md`。
- 旧 Skill：`validation/recap-comparison/merged-state/runs/20261026T121422-2d6fa481/bundle/skills/rdkit-recap-terminal-fragments/SKILL.md`，原样保留。

实际每次命令与人工干预在 commands.json/interventions.json。以下是现有入口，使用新的目录名避免覆盖证据：

```powershell
# A 的原始起点；旧来源表述会被审阅，不应强制跳过
python -m creation_pipeline runtime-import validation/recap-comparison/merged-state/outputs/20261026T121422-2d6fa481 E:/Users/27343/Docker/recap-recovery-new --candidate rdkit-recap-terminal-fragments
python -m creation_pipeline runtime-prepare E:/Users/27343/Docker/recap-recovery-new --candidate rdkit-recap-terminal-fragments --spec validation/markdown-entry/auto-spec.json
# 若明确是作者缺陷，用现有保存计划和同一库承接审阅意见
python -m creation_pipeline build --plan validation/recap-comparison/merged-state/outputs/20261026T121422-2d6fa481/plan.json --state-dir E:/Users/27343/Docker/recap-repair-new --library-dir E:/Users/27343/Docker/recap-recovery-new --keep-debug
# 保存的未验收方案可继续原 planner；不能借此改冻结断言
python -m creation_pipeline runtime-prepare E:/Users/27343/Docker/recap-recovery-new --candidate rdkit-recap-terminal-fragments --spec validation/markdown-entry/auto-spec.json
# B 正常新创建，不输入历史答案
python -m creation_pipeline build validation/markdown-entry/input.json --state-dir E:/Users/27343/Docker/recap-create-new --library-dir E:/Users/27343/Docker/recap-new-library --keep-debug
# 本次实际成功库的查询、安装与重新验收
python -m creation_pipeline library E:/Users/27343/Docker/me-a
python -m creation_pipeline install E:/Users/27343/Docker/me-a --name rdkit-recap-terminal-fragments --destination ./fresh-recap-install
python -m creation_pipeline runtime-validate E:/Users/27343/Docker/me-a --candidate rdkit-recap-terminal-fragments
```

未完成/未覆盖：B 的真实规划与 Docker 闭环、仅含函数定义且没有顶层示例的独立真实样例、所有 Markdown 结构与多块状态依赖、所有化学任务/所有 partner Skill、第二台主机实测。远程 GPU、外部资源挂载、凭据传递和外部服务保持原明确阻塞边界。没有推送、发布或合并远端 PR。
