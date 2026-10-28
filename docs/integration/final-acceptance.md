# 最终独立审查与验收：部分完成，真实验收受阻

日期：2026-10-26（Asia/Shanghai）。本报告不授予“首版代码合并验收通过”。

后续 Codex 执行记录见 [最终验收续接](final-continuation.md)：具体操作审批已解决访问阻塞；新增局部修复、跨平台补验及本轮正式产物迁移验证已完成，但最终版本正常新创建仍因规划传输超时未通过。以下原报告与旧证据保留其原有版本和范围。

## 基线、边界和执行环境

开始时实际 HEAD 为 `57f5e28`，分支 `integration/planner-timeout`，`git status --short` 为空；没有后续提交。仓库及父目录未发现适用 AGENTS.md。复用已有独立集成目录，未重新合并、回退或修改 partner 原目录。partner 对照对象 `e117c434f54d11fd24e3e5566f187a8f4a41a87f` 可从本仓库读取；旧 Docker 对象 `d5b77dc5d91711567af1960530d03739a5c442bf` 从旧仓库只读读取。

仓库没有配置 Git 作者身份，首次提交因此未成功；后续仅对单条提交命令设置 `Codex <codex@localhost>`，没有更改用户或全局 Git 配置。

本次生产修改仅为 `runtime/entry.py` 与 `runtime/model_call.py`，另有对应测试、文档和验证记录。生产修复已本地提交为 `6daa88207238787b23502722affbfbfeccaefe38`。最终 Git 提交/工作区状态见 `validation/final-acceptance/delivery-status.json`。未推送、发布或合并远端 PR。未删除历史归档、原失败产物或共享业务镜像；没有安装宿主软件。

当前 PATH 的 Python 是无法启动的 WindowsApps 别名；使用已安装 Python 3.14.3 的真实路径。使用历史记录确认的已安装 Codex CLI `0.164.0-alpha.11.1`。临时目录改为当前获准写入的 `E:/Users/27343/Docker/final-review-tmp`，没有更改生产代码的临时目录政策。没有访问、复制或保存凭据值。

## 独立审查发现与处理

| 编号/严重度 | 位置、触发条件 | 影响和处理 | 证据 |
|---|---|---|---|
| F1 / P1 完整性 | `runtime/entry.py:markdown_entry`；四反引号或波浪线外层字面代码块包含三反引号 Python 示例 | 旧正则把字面文档误识别为实际入口，违反既定 nested-fence 边界。新增外层围栏状态检查，保持原字节提取、指纹与单块要求。独立语义审阅可能再拒绝，但不能替代确定性入口检查 | `entry-counterexample-before-usable-temp.log` 真实失败；新增反例测试修复后通过 |
| F2 / P1 运行完整性 | `runtime/model_call.py:run`；stdout/stderr 读取或审计写入线程出错 | 原线程异常不传播，主线程仍返回 CompletedProcess；已经收集的答案可能被继续使用，且没有完整审计。改为记录 `io_failed` 并拒绝答案；线程内打开、读写、关闭均纳入处理 | `transport-counterexample-before.json`、`supplement.log`；注入日志写失败测试 |
| F3 / P2 进程与诊断 | 同一函数；启动失败、取消、父进程退出而后代仍持有管道 | 原启动失败只有 request；取消会被 finally 写成 exited；父进程已退出时后代没有可靠清理。新增 start_failed/cancelled，复用已有 WindowsProcessJob 和 POSIX 进程组清理，不增加第二套执行器 | 启动失败、取消、后代持管道、超时四项真实本地子进程机制测试；不是化学验收 |
| F4 / P1 完成性 | `runtime/model_call.py:call`；有 JSON 答案、退出码 0，但无 turn.completed 或存在 turn.failed/error | 原来仅凭答案和退出码可能接受未完成回合。现在必须有成功完成事件且没有失败事件；按传输故障分类，不能靠 planner 改计划修复 | `test_answer_without_successful_turn_is_transport_failure` 覆盖三种事件序列，工具拒绝测试仍通过 |

这些严重度描述触发后的影响，不声称真实 RECAP 历史运行曾触发上述错误。F1/F2 有旧代码反例；F3/F4 通过代码分支与机制测试验证。历史 600 秒超时根因仍未唯一定位，不能归因某个插件。

待核查：partner 原有 `agent/backend.py` 的原生会话与 tool-free caller 是两个传输路径。其同步 stdin 写入、读取线程异常、后代进程异常退出尚缺与本次新测试同等的故障注入覆盖。本次没有据此声称真实运行已发生挂死，也没有把 tool-free 通过扩大为 native transport 全部已验证。有效 provider/profile/平台组合、认证成功及模型服务返回仍需在可用环境实测。

## 迁移完整性与单一架构

| 分类/能力 | 当前实现与复用关系 | 机制测试与真实证据/缺口 |
|---|---|---|
| 保留：来源准备、补充材料 | `resources/acquisition.py`, `intake.py`, `supplements.py`, `workspace.py`；acquisition/supplements 对 partner 无差异，intake 增加身份分离 | `test_sources`, `test_research`；历史 RECAP 发现材料；本次固定来源本地字节核对成功，但网络重新获取受阻 |
| 保留：发现、直接文件编写、基础检查、独立审阅、逐候选处理 | `pipeline.build`, `generation/*`, `agent/*`, `validation/checks.py`；agent/discovery 保留 partner 实现，author/checks/pipeline 接入统一契约与 Docker | `test_discovery`, `test_native`, `test_skill_library`；历史阶段五与 RECAP 作者/审阅记录；本次未进入模型阶段 |
| 适配迁移：规划/断言/接口与覆盖 | 旧 runtime_model → `runtime/planner.py`；runtime_acceptance → `acceptance.py`/`coverage.py`；strict_acceptance → `strict.py` | `test_runtime_build`, `test_migrated_execution`, `test_contract_diagnosis`；旧 RECAP 恢复/故障注入证据 |
| 适配迁移：容器执行和生命周期 | 旧 runtime_package → `runner.py`；旧 lifecycle 核心 → `execution.py`, `local.py`, `recovery.py`, `service.py` | `test_runtime_execution`, `test_runtime_recovery`；阶段三真实 RDKit 与镜像扰动、阶段四迁移、B 历史 11/11；当前 Docker 受阻 |
| 必要新增：统一资格、冻结、双区 catalog 事务 | `contracts.py`, `artifacts/evidence.py`, `store.py`；`library.py` 仅导出 store；`package.py` 另一个安装入口也调用 qualify | `test_delivery_protocol`, `test_skill_library`；同内容证据更新、回滚、显式候选隔离和 partial 均有机制覆盖 |
| 必要新增：Markdown 入口关联 | `entry.py`、preparation handoff、独立 `review_snapshot`、execution 镜像内容检查 | Markdown 测试含 CRLF、完整字节/定位漂移、来源引用、独立拒绝、函数定义、缺失上下文；历史 A/B 可读证据重新核验；新代码真实执行待补 |
| 必要新增：诊断与版本化契约修正 | `diagnosis.py`, service approve_correction/automatic_correction；来源引文、独立批准、新版本、全量重验 | `test_contract_diagnosis`、真实稀释契约修正和 cf7a9c5 内容故障注入；不是自然新创建证据 |
| 未迁入/删除范围 | 旧主流程、旧 bindings/checkpoint/ZIP 发布协议未成为新版兼容层；本次不删除仍被调用的成熟逻辑或历史文件 | 生产路径扫描无旧项目或验证目录依赖；本次没有额外实现删除 |

`migration-code-comparison.json` 以 AST 比较旧 Git 对象与当前代码：runner 有 9 个同名顶层符号完全一致、5 个适配；planner 为 11/5；strict 为 1/0。该比较用于确认复用，不代替语义审查。partner 文件差异另存 `partner-file-diff.txt`。

主入口仍为 `python -m creation_pipeline` → cli → pipeline.build；运行阶段通过 preparation/service/LocalExecutor 接入。恢复子命令是同一 service 的不同动作，不是旧创建流程。目录中的历史 skills 不注册为 accepted；evaluation 不承担创建/发布。默认库查询和两种安装路径都经过正式资格门槛；不存在通过原目录名或历史 ready 标志自动批准的路径。

作者回执在 `artifacts/delivery.py` 完成直接文件交付；最终 `evidence.seal` 冻结 package/source/record/runtime material；动态 attempt 和 catalog 当前资格在冻结内容之外。这三者不能相互替代。架构图 `docs/pipeline/integrated-flow.mmd` 与这一调用关系一致，本次没有改变拓扑或既定政策。

## 重点边界核查

- Markdown：只支持唯一、完整、无缩进的 Python/py 三反引号块；不拼接多块，不强迫作者加脚本。函数定义允许绑定，后续必须有实际函数调用与覆盖证据，单独 import 不等于业务通过。缺失全局上下文、交互/dynamic 执行及多脚本歧义保留阻塞/内容诊断；不是全 Python 语义或所有 Markdown 结构的静态证明。
- 来源：`upstream` 记录固定原仓库版本；inventory/snapshot 记录实际输入；carrier_repository 仅承载仓库身份。已核对固定 Recap.py 与 license.txt 哈希及 RecapDecompose/GetLeaves 源码，历史 SKILL 没有作为新生成输入。
- 较新拒绝：saved-plan continuation 在同一目标 catalog 中检查同文件/同来源的 association 独立拒绝，并回到作者反馈；对应测试通过。不同库之间没有全局撤销服务，不宣称存在。
- 冻结断言：未通过规划的 rejection 作为 feedback，不能假扮 previous_plan。已有 acceptance cases 通过 locked_cases 比较；映射作者检查也逐项比较。来源独立批准才可走 oracle-correction 新修订。环境修复不放宽既有断言。
- 跨平台清单：evidence.verify 和 LocalExecutor.inputs 的排序只改变比较顺序，保留完整 path/bytes/hash 及重复项，不用集合消去文件；已有漂移测试通过。其他严格列表比较可能对跨 OS 的排序更保守，不能宣称任意跨 OS/第二台主机实测。
- 配置：tool-free 仍继承 model/provider/auth，显式关闭宿主工具发现与通知；只把非敏感模型设置写入观测。native 会话仍使用 partner 的 ignore-user-config 政策，二者并不等价。CLI 实际启动到初始化失败已有记录，未验证本次 API 认证成功。
- 无进展：propose 重复诊断、planner 重复补丁、diagnosis 已尝试标记和 pipeline runtime_seen 保留停止条件；production 无新增总配额。资源不足/未知不被当作无需执行。
- 重建：实际 image ID 绑定与 tag 核对不等于 bit-for-bit 重建。默认 pin_base_image=false；浮动基础 tag、下载服务与未锁定传递依赖仍可变化。旧 B 的 wheel 为 RDKit 2024.09.6，不等于从固定来源提交编译。

## 本次真实正常创建：未成功，未恢复

使用 `validation/final-acceptance/input.json`（原固定 URL、SHA-256、业务范围，仅改变 batch label）和全新 `E:/Users/27343/Docker/final-recap-normal-1`。没有人工提供 Skill、adapter、业务脚本、Dockerfile、计划或预期。`business-checklist.md` 在运行前复制固定；源字节独立核对见 `fixed-source-verification.json`，包括终端/层级 3/4/5、CCCOCCC 合法空结果，以及包装层非法输入边界。

正常 CLI build `20261026T150231-d5103082` 在来源获取阶段返回 `blocked`：两个 URL 均为 WinError 10013。entities 为空、model_calls=0、无 accepted 产物。没有进入发现/作者/审阅/规划/构建/业务验收，因此不能称为“创建全链路通过”，也没有新增内容/环境/契约自动修复成功证据。`normal-state/` 保存此次原始运行状态副本；最初准备脚本因历史下载文件使用 document.py/document.txt 而非 URL basename 停止，修正查找后才执行上述唯一正常 build，没有重复模型或规划尝试。

独立 Docker probe：Linux engine 命名管道访问 permission denied。一次 30 秒上限的真实 Codex 传输 smoke（不是化学任务）在约 0.09 秒退出 1，数据库/app-server 初始化 permission denied，无模型答案；没有重试或更换认证。该 30 秒只用于显式 smoke，不修改 production 的 planner 600 秒限制。

完整配置和生效默认值见 `effective-settings.json`：gpt-6-astra；production 原生总量限制为 null；runtime model/build/test 默认 600/600/60 秒，memory=1g、cpus=2、pids=128，其他明确限制逐项保存。真实模型调用成功、实际新镜像及新测试结果均不存在。正常 build 与 CLI smoke 发生在最后完成事件检查之前，但都未获得来源/模型答案；最后修改后没有原样重试这些确定的权限阻塞。最终成功模型回合及化学重验仍待补。

## 安装、异路径与历史证据

本次没有正式产物，所以无法验证“本次正式项默认查询返回、安装成功、按说明在容器实际使用”。不能用旧 B 代替。

另将旧 B 完整复制到专用 `final-historical-copy`，保留原 me-b 和归档不变。实际 CLI 默认查询为空；默认安装退出 2（拒绝不合格候选）；relocate 撤销路径资格；runtime-validate 返回 runtime_blocked/accepted=false，历史通过保留到 runtime_history。见 `historical-copy-commands.json` 和 `copy-*.log`。这验证了当前受限环境下的拒绝/持久化路径，不是异路径业务执行成功；未删除任何镜像。

只读 `verify_archive.py` 当前通过：旧 B 文件清单、来源、作者检查、版本历史、11 个锁定用例及原 accepted CLI 证据哈希一致。历史镜像 `sha256:a617ef6e1ba01ecc79e3d75a7a1ed598822f3582ffbdd53e0ddcf590d781dd48`，历史 RDKit 2024.09.6。它们不是当前镜像可用性的证明。

历史 SKILL 直接位置（仅对照，不是本次产物）：`validation/planner-timeout/library/accepted/rdkit-recap-terminal-fragments/SKILL.md`。本次最终 SKILL.md：不存在。

## 测试类别与最终结论

- 机制测试：最后生产修改后的针对性 25 项通过；最终全量 240 项，238 通过、2 项 POSIX-only 跳过，退出码 0（`regression-final.log` / `regression-final-command.json`）。Docker 在机制套件 PATH 中明确屏蔽，模型使用 fixtures，不能称为真实化学验证。本地 Python 子进程测试只检验传输/清理。
- 故障注入：本次新增外层围栏、日志写失败、启动/取消/后代持管道、未完成事件；历史 cf7a9c5 内容注入与契约修正保持其原始实验性质。
- 历史真实证据：阶段三脚本/RDKit/镜像扰动，阶段四同机迁移恢复，阶段五与 contract-repair，Markdown A、planner-timeout B；分别用于各自版本与范围，不合并成新创建成功。
- 本次真实尝试：固定 URL 网络访问、Codex CLI 初始化、Docker engine probe，以及历史副本资格撤销/阻塞记录。均未完成新的模型+Docker化学全链路。
- Linux/POSIX 新进程清理分支尚未在本次重新执行；Windows 的两个 POSIX-only 用例跳过。旧 Linux 18/18 不覆盖本次 model_call 修改。

最小剩余工作：在允许网络、Codex 认证与运行目录、Docker Linux amd64 engine 访问的执行环境中，对最终代码另建全新目录完成相同 RECAP 正常创建；检查全部锁定业务用例和实际镜像/依赖；完成正式查询、隔离安装与异路径容器实际使用；补本次受影响的 Linux 传输清理验证，并补齐 native 异常传输覆盖。若中途需要显式恢复，保留成果，但仍另需正常不中断的新创建证明。

首版范围仍仅本地 Linux amd64 Docker、CPU、公开依赖及已实现阻塞/恢复。多块状态依赖、远程 GPU、外部挂载、凭据传递、外部服务、第二台主机未实现/未实测，不得自动放行。由于真实创建与最终交付必需条件尚未满足，本次结论为“审查与部分修复完成，最终验收受阻”。

## 可复现入口

```powershell
# 在具备所需权限的环境中，选择另一个从未存在的 STATE/LIBRARY，保留本次失败现场
python -m creation_pipeline build validation/final-acceptance/input.json --state-dir NEW_STATE --library-dir NEW_LIBRARY --keep-debug
python -m creation_pipeline library NEW_LIBRARY
python -m creation_pipeline install NEW_LIBRARY --name ACTUAL_NAME --destination NEW_INSTALL
# 异路径导入/迁移后必须独立重验；不能继承旧执行位置
python -m creation_pipeline runtime-relocate COPIED_LIBRARY --candidate ACTUAL_NAME --revalidate
python -m unittest discover -s tests -v
```

准确运行参数、退出码、日志和状态副本均在 `validation/final-acceptance/`。`run_normal.py` 和 `supplement.py` 为本次记录脚本，默认拒绝覆盖已有目录；复跑应换新目录，不应删除旧证据。复制状态中的原路径只用于定位历史，不能充当新的正式资格。
