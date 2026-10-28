# 合并版最终验收：给 agent 的执行提示词（本仓库版）

> 用途：把上一轮写给 Codex 的验收提示词改成能直接交给当前 agent 在这个仓库执行的版本。
> 改动理由见文末“与原提示词的差异”。复制下面两个分隔线之间的内容即可使用。

---

## 角色与目标

你是本仓库的验收执行者。目标只有一个：判明“合并版（partner pipeline 架构 + 我们的 Docker 构建/业务验收/恢复能力）能否通过**一次修复后的正常新创建真实全链路**”，并给出有边界的结论。

不要从零重做合并，不要重复已完成的迁移，不要把历史报告里的成功当成当前版本的验收。先核对事实，再做缺失的验证。

本次允许你：读代码、跑机制测试、跑真实模型调用（需按第 0 节申请配额）、跑真实 Docker、在隔离目录做破坏性场景、本地提交。
本次禁止你：推送/发布/合并远端 PR、修改 partner 原版、删除历史归档或用户文件、弱化任何来源或验收约束、用 mock/宿主执行/DNA 任务替代本次化学验收。

## 0. 授权与配额（先确认，再花钱）

1. 真实模型调用按“批”申请：每批最多 3 次串行、每次外层上限 600 秒、`progress_timeout` 240 秒；同一时刻只跑一个。开跑前用一句话说明本批目的与次数，等我回“批准”。失败后**不自动追加**。
2. 真实 Docker 构建/执行业务不受上面次数限制，但每次都在隔离目录内，且不得删除共享业务镜像。
3. 任何会改变全局配置、代理、认证、模型、服务层级、传输默认值或超时的操作，都要先问。
4. 权限/关键决策不明时先问，不要猜。

## 1. 工作区与现状（第一步必须核对）

- 本地集成项目：`E:\Users\27343\Docker\chem-agent-toolkit-integration`，分支 `integration/planner-timeout`。本提示词编写时 HEAD=`6962dc2`，工作区干净。
- 另有既有隔离工作区 `E:\Users\27343\Docker\chem-agent-toolkit-planner-experiment`（分支 `experiment/planner-protocol-v1`），非本次对象，不要在里面改东西。
- 参考对象（只读）：partner 基线 `e117c434f54d11fd24e3e5566f187a8f4a41a87f`，原目录 `E:\Users\27343\Downloads\chem-agent-toolkit-partner-pipeline`，隔离 clone `E:\Users\27343\Docker\chem-agent-toolkit-recap-partner`。旧 Docker 基线 `d5b77dc`、旧项目 `E:\Users\27343\Docker\chem-agent-toolkit_newpipeline` 只作对照，不得成为运行依赖。原运行库 `E:\Users\27343\Docker\me-b` 保留。
- 开工时先跑 `git status --short`、`git log --oneline -8`、`git branch --show-current`，以及 `git worktree list`。若有新提交或未提交改动：说明差异，不静默回退、不覆盖、不混入别人的改动。仓库内没有 AGENTS.md（已多次核对），若出现则以它为准。
- 已经发生的事（不要重复调查，但要复核结论是否仍成立）：
  - 三次受控真实调用的授权**已用完**：一次因本机 TUN/代理未生效连不上后端（`workspace routing discovery timed out`），网络恢复后 HTTP/SSE 与 WebSocket 均在约 150 秒内完成传输；WebSocket 那份答案被计划语义校验拒绝（`Outcome assertion role must match the promised purpose: completion`）。
  - WebSocket 的流空闲超时会被**任意入站文本帧**重置（本地回环已证明），HTTP/SSE 不会。因此“静默 600 秒”是监督盲区，不是模型慢。
  - `model_call.run` 现在有进度看门狗：`progress_timeout` 默认 240 秒，被总超时截断，进度＝stdout 生命周期事件**或**入站字节增长；触发时 `status=stalled`、写 `stall.json`、`code=model_stalled`。
  - `agent/backend.py` 的 agent 阶段只做**观测**（receipt 里的 `progress_observation`），默认不终止；要终止须显式设 `limits.agent_progress_timeout`。
  - 下一批受控实验的显式传输是 **HTTP/SSE**（自定义 provider + `supports_websockets=false`），**不改生产默认值**。

## 2. 必读（按顺序，别从历史报告里抄结论）

`docs/integration/recap-planner-handoff-summary.md` → `docs/integration/pipeline-timeout-architecture.md` → `docs/integration/markdown-entry.md` → `docs/integration/contract-repair.md` → `docs/integration/final-acceptance.md` → `docs/integration/final-continuation.md` → `docs/integration/final-single-retry.md` → `docs/integration/stage-one..five.md` → `docs/integration/recap-comparison.md` → `docs/integration/planner-timeout.md`。

证据目录：`validation/` 下各子目录（`markdown-entry`、`contract-repair`、`final-*`、`recap-comparison`、`timeout-deep-debug` 等）。**只有真实模型/Docker 记录算业务证据，机制测试与 doubles 必须标注为机制测试。**

## 3. 环境预检（不通过就先报阻塞，不要硬跑）

```powershell
codex doctor --json                     # 看 network.provider_reachability / network.websocket_reachability 是否 ok
docker version --format '{{.Server.Version}}'   # Docker daemon 是否可用，记录版本
python --version                        # 期望 3.14.x
python -m unittest discover -s tests -t . -q    # 当前基线：285 项、3 跳过、应全绿
python -m creation_pipeline --help      # 确认 CLI 子命令与文档一致
```

后端不可达时：先判断是本机代理/TUN 状态（`codex doctor` 的 `network.env` 里 `respect system proxy` 与推理地址结果），把结论写进报告，**不要**把网络失败当成代码缺陷，也不要靠延长超时绕过。Docker 不可用时：把依赖 Docker 的项标为阻塞，先完成审查与其他可做项，最后给 `partial`。

## 4. 任务一：独立代码与迁移审查（先做，不停在计划）

先给出一页审查清单（每项写：结论、位置、证据、严重程度），随后逐项核查：

1. partner 保留能力 / 旧 runtime 迁移能力 / 新增能力分别落在哪些文件与提交，对应机制测试与真实证据各是什么，缺哪些。
2. 是否仍只有**一套**主入口、状态协议、恢复流程和 catalog（`pipeline.py`、`records.py`、`artifacts/store.py`、`runtime/service.py`）。
3. 是否存在旧项目目录、旧产物或历史通过状态被当成运行依赖。
4. 库入口是否都遵守正式资格过滤（默认查询/推荐/安装只看 accepted；candidates 必须显式选择）。
5. 冻结交付、作者回执、动态运行记录是否分开持久化（`artifacts/evidence.py`、`runtime/execution.py`）。
6. 重点复核近期改动：
   - Markdown 代码块定位/提取/字节指纹/来源关联/实际执行入口（`runtime/entry.py`、`preparation.py`）；
   - 多代码块、歧义代码块、上下文不完整、函数调用边界；
   - 上游版本 vs 输入快照 vs 承载仓库身份；
   - 较新审阅是否真的约束旧计划恢复；
   - **未验收拒绝方案的恢复是否可能改到已冻结断言**；
   - 跨平台 manifest 是否严格比较全部文件、大小与 hash；
   - `model_call` 的配置隔离、认证/provider 保留、CLI 兼容参数；
   - 子进程超时/取消/启动失败/管道读取异常/进程树清理；
   - 日志脱敏、持久化、失败分类（`model_unavailable` / `model_stalled` / 内容缺陷 / 契约 / 未明）、无进展停止；
   - 环境计划的依赖版本、基础镜像身份与可复现边界。
7. 主动找反例：能绕过资格的路径、未覆盖分支、只看报告与实现一致不算结论。未证实的标“待核查”，不要写成确定缺陷。

审查发现的问题：先修影响本次验收或完整性的，不做无关重构；修完跑受影响的机制测试。优先级低的问题写进报告的“未解决/待核查”一节。

## 5. 任务二：修复后正常新创建的真实验收（核心）

任务固定为 RDKit RECAP 终端分子片段（不收窄成描述符/DNA/更简单任务）。

- 来源（已核验，直接复用 `validation/markdown-entry/input.json` 的 URL 与 SHA-256）：
  - `rdkit/Chem/Recap.py`（commit `237a1d9027c800784afed8788540f38a3aa595f8`），sha256 `d4f9b96945c2c92c095d758a7f460360dc1a73fb75831bfdb8482f8f9aaec3fc`
  - `license.txt`，sha256 `daeb8d194502cbcf34c05c39541a0d02be65bc9bada5b891c1974cd24e9fca30`
- 历史 `SKILL.md` 只作对照，不作为新生成答案输入。
- 全新隔离运行目录与验证库，放在仓库外，例如 `E:\Users\27343\Docker\final-acceptance-<UTCts>\{state,library}`，路径写进报告。
- 正常入口（不要用 `validation/timeout-deep-debug/controlled_call.py` 这种诊断脚本冒充验收）：

```powershell
python -m creation_pipeline build <new-input.json> `
  --state-dir  E:\Users\27343\Docker\final-acceptance-<UTCts>\state `
  --library-dir E:\Users\27343\Docker\final-acceptance-<UTCts>\library `
  --keep-debug
```

`new-input.json` 基于 `validation/markdown-entry/input.json`，只允许改动 `batch.label` 与目录相关字段；`execution.profile` 保持 `production`，不新增隐含配额。

要求：

- 真实模型 + 真实 Docker；记录实际生效的模型、reasoning、service tier、`model_timeout`/`progress_timeout`、传输、Docker 与镜像摘要。
- 不手工补 SKILL/adapter/业务代码/Dockerfile/计划/测试预期；不为了让验收器通过而要求作者生成脚本。
- 验收依据必须来自运行前固定的来源（`RecapDecompose`/`GetLeaves`、终端 vs 完整层级、合法空结果、声明范围内的非法输入、真实交付入口与支持文件覆盖）。
- 来源固定 ≠ 安装二进制与来源同版：准确写清实际依赖版本与镜像身份。
- 正常模型修复是流程的一部分，记录其类型；没触发修复就不要宣传修复能力得到新建验证。
- 若发生显式恢复（`runtime-prepare`/`runtime-resume`/`runtime-import`），保留并完成有价值的工作，但结论必须写成“恢复后的验收”，不能写成“不中断的新创建成功”。
- 若再次 `stalled`/超时：用 `stall.json`、`process.json`（`process_counters`、`io_counters` 时间线）、投影过的 stderr 定位，保存证据；不原样重跑，不只延长超时，不手工给计划绕过。需要新调用按第 0 节重新申请。
- 遇到不可得条件（Docker、网络、资源）：保存阻塞，继续不受影响的审查，最终结论给 `partial`，不要宣称整体通过。

## 6. 任务三：交付与政策核验

```powershell
python -m creation_pipeline library <library>                                  # 默认只应有 accepted
python -m creation_pipeline library <library> --include-candidates             # 候选必须显式查看
python -m creation_pipeline install <catalog-output> --destination <新隔离路径>
```

1. 默认查询返回合格项、默认安装成功；安装到**新的隔离路径**，按交付说明在适用容器环境实际使用（不得依赖临时作者目录、历史验证目录、旧项目运行目录）。
2. 新路径当前资格按既有迁移协议核验（`runtime-relocate`），不直接继承旧路径可运行性。
3. 破坏性场景（镜像丢失/身份变化、来源/交付/契约漂移导致撤销或阻塞）只在隔离副本或专用镜像里验证，不删共享镜像。
4. 按能力复用既有真实证据，只补近期修改影响的或缺失的：脚本入口与 Markdown 入口、有依据无需执行/显式草稿/需求未知、资源阻塞持久化与运行恢复、内容/环境/契约/未明分流、锁定断言与独立批准、多候选 partial、候选默认隔离与晋升、新证据更新与事务回滚、临时目录清理后恢复、同机迁移。
5. 机制测试不能当作真实模型/Docker 证据；复用旧证据要写明版本与适用范围。

## 7. 清理与最终回归

只清理已确认被替代、且迁移能力与测试覆盖充分的实现；保留仍被新版调用的成熟逻辑。不删历史归档、用户文件、原始失败产物。

```powershell
python -m unittest discover -s tests -t . -q
```

最后一次程序修改后：跑全量回归、跑受影响的真实重验、更新 CLI/配置/目录/资格/恢复/迁移/入口边界文档，并核对架构描述与实现一致。若本轮只改文档或验证记录，明确说明为什么不需要重跑昂贵实验。

## 8. 最终报告（9 项，缺一项都不能说通过）

1. 实际验证基线、最终提交号、工作区状态（含 `git status` 结果）。
2. 迁移完整性映射：保留 / 适配迁移 / 新增 / 删除，各附证据位置。
3. 独立审查发现的问题：严重程度、位置、触发条件、修法、未解决与待核查。
4. 正常新创建是否完整成功，有无显式恢复或人工干预；恢复了哪些。
5. 真实模型、Docker、业务入口、镜像摘要、锁定测试与 catalog 证据（附路径）。
6. 实际安装与异路径使用结果。
7. 机制测试、故障注入、历史证据、新真实实验各自证明什么（分开列，不许混算）。
8. 仍未验证或明确不支持的范围，以及是否影响首版验收。
9. 可复现命令、证据位置、最终 `SKILL.md` 直接路径。

只有以下全部成立，才可以给“首版代码合并验收通过（有边界）”：单一架构与能力迁移无阻断遗漏；独立审查无未解决阻断问题；**当前代码**在正常入口完成真实化学任务全链路；正式交付/安装/资格/恢复有对应证据；最后修改后的回归与受影响真实验证通过；未支持范围明确且程序不会错误放行。

否则明确判 `partial` 或 `blocked`，列出最小剩余工作。不夸大：不能仅凭测试数量、历史恢复成功或一次模型回答宣布合并成功。

必要代码、测试、文档、证据本地提交，报告里写提交号。不推送、不发布、不合并远端 PR。完成后停下等我审阅。

## 9. 明确的禁止项（重复强调）

- 不弱化来源、入口、锁定断言、负例或验收范围；不按实际输出倒推预期。
- 不用 mock、宿主执行、CPU 假装 GPU、缩减断言冒充业务验收；doubles 必须标注为机制测试。
- 不手工提供计划、Dockerfile、业务代码或断言；不要求作者为迎合验收器生成脚本。
- 不改全局代理/认证/配置/模型/传输默认值/超时；不关闭 TLS；不做中间人解密。
- 不采集 token、认证头、cookie、完整环境或请求响应正文；诊断只落固定类别与白名单 ID。
- 不静默回退历史提交、不覆盖未提交改动、不删历史证据与用户文件。

---

## 与原提示词的差异（为什么这样改）

| 原提示词 | 本版 | 原因 |
| --- | --- | --- |
| 基线写“提交 57f5e28、工作区干净” | 改为“编写时 HEAD=6962dc2，开工自行核对” | 之后又落了 4 个提交（看门狗、代理、计量、证据），写死会误导 |
| 没有授权配额章节 | 第 0 节：每批最多 3 次、600 秒、240 秒看门狗、失败不自动追加 | 上一轮 3 次授权一次性用完；必须先申请再花 |
| 没有环境预检 | 第 3 节固定 `codex doctor` + `docker version` + 全量测试基线 285/3 跳过 | 上一次的真实失败根因是本机 TUN/代理未生效，比代码问题更常见 |
| 只说“若再次超时利用已有观测定位” | 给出具体工件：`stall.json`、`process.json.process_counters`、投影 stderr，并禁止原样重跑/延长超时 | 已证明 WS 空闲超时会被入站帧重置，静默不等于慢 |
| 未提传输选择 | 明确“下一批受控实验用 HTTP/SSE、不改生产默认” | 你的决定，写进提示词才不会被下一个 agent 改回去 |
| 未提 agent 阶段观测 | 写明 `progress_observation` 只观测、默认不终止 | 你的决定：先收数据，不自动终止 |
| 未限定“诊断脚本≠验收” | 明确 `validation/timeout-deep-debug/controlled_call.py` 是诊断工具，验收必须走 `python -m creation_pipeline build` | 防止用固定归档 prompt 的直接模型调用冒充全链路 |
| 验收任务只写“真实完成全链路” | 补上确切命令、隔离目录位置、input.json 只允许改哪些字段 | 让命令可直接执行、证据可直接比对 |
| 报告要求较抽象 | 9 项逐条保留并加“附提交号/路径/镜像摘要” | 便于你复审时逐项打勾 |
