# Codex 最终验收续接（2026-10-26）

本报告续接 `final-acceptance.md`，不改写上轮失败和历史结论。**最终结论：修复、跨平台回归及本轮第一份正式产物的最终代码重验/安装/迁移完成；最终代码的正常新创建在 planner 600 秒处受阻，不能宣称首版最终验收通过。** 没有继续无变化重试或延长超时。

## 基线与访问

实际起点 `798f7e3`，分支 `integration/planner-timeout`，工作区干净，没有后续提交；仓库及父目录未发现 AGENTS.md。复用独立集成目录，没有重新合并、修改 partner、覆盖用户工作或推送远端。

真实 Python 为 `C:/Users/27343/AppData/Local/Python/pythoncore-3.14-64/python.exe`，版本 3.14.3。默认沙箱仍阻止固定 URL（WinError 10013）、Docker Linux 命名管道和 Codex 状态数据库/app-server 初始化。经平台具体操作审批后，相同预检成功：两个官方来源重新下载并匹配输入 SHA-256；Docker 为 linux/x86_64；gpt-6-astra 真实结构化调用返回 `{"ok":true}`，有成功完成事件。没有变更全局权限、认证或用户配置，也没有安装宿主依赖。证据：`validation/final-continuation/{default,approved}/`。

本轮 tool-free 实际继承 medium reasoning effort / default service tier；历史记录的 low 不是本轮生效配置。native 仍是 ignore-user-config + 显式模型，不宣称两条传输配置等价。

## 局部修复与独立审查

生产修改为 `creation_pipeline/agent/backend.py` 的局部传输修复，以及后续 `runtime/entry.py` 一处引用提示澄清；保留原生会话、来源机制和独立 reviewer 会话。没有重写 runtime/planner、catalog、业务契约或断言。native 修复提交 `38bffa6`。

1. native 回合带 `error` 但同时有答案及完成事件，旧代码仍接受。新增反例先失败（`native-before.log`），现在明确拒绝。
2. stdin 写入移入受监督工作线程，使显式超时覆盖不读取输入的子进程；读取/写入错误传播。启动失败持久化，复用现有 WindowsProcessJob / POSIX 进程组进行清理。测试覆盖不读 stdin、读取异常、启动失败、原父进程退出后后代持管道。
3. 本轮差异的真实独立模型审查最初被自动审批拒绝：未明确授权仓库代码外发。用户随后明确批准 backend.py、validation/runtime.py、WindowsProcessJob、test_native.py 和差异的限定范围，同一脚本获准执行；没有绕过。记录见 `approval-review.json`、`independent-native-review-result.json` 和审计目录。
4. 独立审查提出两个确切边界：线程启动间取消导致 join 未启动线程；POSIX 脱离进程组的子进程持管道导致同步 close 阻塞。均先复现，见 `native-review-before.log` 和 `native-detached-before.log`（后者实际等待约 12 秒超过 8 秒断言）。修复仅 join 已启动线程、让工作线程持有并最终关闭自己的流、持久化清理异常且保留原取消异常。脱离 POSIX 进程组的任意进程不在完整终止保证内；现在有界失败并记录 `stream_threads_finished=false`，不假称已清理。测试专用容器会清理其隔离后代。

独立模型给出的是 findings，不是通过 verdict；后续关闭依据为本地反例及 Windows/Linux 回归，不伪造第二次模型复审。没有扩大为全面历史重审。

同步修正 configuration.md 的传输政策，以及 design.md 两句遗留的不支持 Docker/tool-free 表述；单一主流程拓扑不变。

最后程序提交为 `8c1cac8`（引用提示及严格拒绝反例）；此前 native 提交为 `38bffa6`。第三轮启动时生产文件与 `8c1cac8` 一致，实际哈希在 release/effective-settings.json；后续只添加文档与证据。

## 验证范围

修复第一阶段：Windows 针对性 26 项通过；全量 245 项（243 通过、2 POSIX 跳过）；Linux 44 项通过。首次 Linux 失败来自测试包装未复制 docs，原日志保留，补齐资源后原断言通过。

独立审查修复后的最终 Linux：46/46 通过，含 native、tool-free、相关执行机制，使用历史测试镜像 `sha256:ac1b99015f7dd2609c7074a7bbab583d2b6bcdf0ae92d113cb443814f2b95b8b`，禁网、仓库只读，代码和测试复制到容器 tmpfs。不是业务镜像。Windows 机制全量在子进程 PATH 屏蔽 Docker；模型为 fixtures，不能当作真实业务结果。

最后引用提示修改后再次适用全量：Windows **248 项，245 通过、3 POSIX 专属跳过**；Linux **63/63**（增加 Markdown 入口与来源测试）。证据在 `release/regression-windows*`、`release/transport-linux*`。之前 final/ 中 247/244/3 和 Linux 46 属于提示修改前，不能替代最终结果。

上轮迁移映射、候选隔离、冻结断言、资源阻塞、归因、事务回滚、partial、恢复和脚本入口等已有证据按 `final-acceptance.md` 原范围复用；本轮不再复制全面审查。最终回归同时覆盖其现有机制测试。DNA 不重试。

## 真实新创建

第一轮 `final-recap-codex-1` / build `20261026T153406-5622ba43`：正常新版 CLI，原固定来源、相同业务要求，真实模型 7 次，独立内容与入口审阅、规划、构建、9/9 业务检查、accepted 晋升完成。作者按包装反馈把许可证移入 references，未发生运行后业务修复或显式恢复。实际 RDKit 2024.09.6 / Python 3.11.17，镜像 `sha256:a6b1da30b795fe071ab5e8235612f0ead70c855cc83a31666a03e97d1a14f658`。该轮在独立审查后的最后程序修复前已启动，**不计作最终代码全链路证明**。原运行和逐文件校验归档 `first-run/` 保留。

第二轮 `final-recap-codex-2` / build `20261026T154611-ba619bf4`：最终 native 代码正常创建，模型 5 次，内容审阅通过，入口关联模型把两个不连续源码片段拼成一个 quote。程序正确拒绝，状态 runtime_blocked / business_acceptance=not_run，未规划、未构建、未晋升。不是化学失败或 planner 超时。作者 CLI 曾一次自动重连并最终完成，没有人工重启；许可证位置由流程内作者修正。失败现场在 `second-before-recovery/` 逐文件核对归档。

对此只澄清 entry.py 提示：quote 必须是选定源码中的一段连续逐字子串，不拼接、不改空白，补充说明放 reason。不改变 schema、引用判断、业务源码或锁定断言，不引入自动重试。新增非连续引用反例确认即使两个片段各自存在，拼接仍必须拒绝且不能进入独立批准。

第二轮通过现有 runtime-prepare 显式恢复，假设、判定标准和命令见 `second-recovery-command.json`；即使通过也不能当作不中断新创建。最后程序修改后的正常新创建另用 `final-recap-codex-3`，记录位于 `validation/final-continuation/release/`。全部轮次均原固定来源和业务要求，不输入旧 Skill、不人工提供业务代码、测试计划或 Dockerfile。

第二轮恢复结果：新引用通过逐字核验和独立审阅，交付文件清单不变，但 planner 在 600 秒超时；未构建、未执行业务，仍为 candidates/runtime_blocked。完整恢复未成功；`second-after-recovery/` 保留全部材料。

第三轮最终版本 build `20261026T155804-64fbb6f0`：真实模型调用 7 次，来源、发现、编写、内容审阅、Markdown 关联及独立批准完成。planner 从北京时间 16:07:14 开始，在 600.015 秒停止；无有效方案、无成功完成事件。状态 runtime_blocked / business_acceptance=not_run；没有业务镜像、未晋升。默认查询为空，默认安装退出 2，证据为 `final-candidate-*`。这轮没有显式恢复，原正常流程未成功。

第二轮恢复和第三轮 planner 的 stderr 分别在北京时间 16:08:55.784 与 16:08:55.488 记录 peer closed connection without TLS close_notify，随后 CLI 尝试自身传输重连。这是接近同时发生的流传输中断证据，不是来源权限、Codex 初始化或 Docker 拒绝；它提示共享传输事件的可能性，但不能唯一确定网络、服务或其它根因，更不能追溯认定旧历史超时的唯一根因。两次均保留 request/process/events/stdout/stderr 和 timeout，线程清理完成，未接受缺失完成事件的答案；退出码字段本身不是成功依据。

## 本轮正式产物的最终代码重验、安装和迁移

为完成不受模型等待影响的工作，对第一轮本轮新正式产物使用最终代码 `runtime-validate`：**9/9 真实通过**。默认查询返回该正式项，默认安装成功。再把这次安装生成的 `.runtime/NAME` envelope 导入全新 `migrated-library`：状态 not_run、默认查询为空、安装退出 2，说明没有继承旧位置资格。原 `runtime-resume` 核验当前镜像和输入并完整重跑 **9/9**，重新晋升，默认查询及异路径安装成功。

最后只读挂载 `final-recap-codex-1/migrated-installed/rdkit-recap-terminal-fragments` 到业务容器，在新路径原样读取并核验 Markdown 和 Python 块哈希，执行交付示例，实际返回 `['*C1CC1', '*c1ccc(OC)cn1', '*c1ccccc1*']`。未挂载作者临时目录、历史验证库或旧项目目录；支持文件清单与正式修订一致。实际命令和结果见 `first-lifecycle/installed-use.json`，完整重验及安装证据见 `first-after-lifecycle/`。这是本轮新产物在最终代码上的生命周期验证，**仍不能替代第三轮正常新创建通过**。

正式修订 `rev-5e335e7edb838bba3dfbc29ee9a2d8a9adb57229e72538d7b9e789e36e912e53`；业务镜像 `sha256:a6b1da30b795fe071ab5e8235612f0ead70c855cc83a31666a03e97d1a14f658`。构建日志中的基础镜像为 `docker.io/library/python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89`；实际 Python 3.11.17、RDKit 2024.09.6，numpy 2.4.6、pillow 13.0.0 等分发版本在环境用例 stdout 中记录。固定源码提交不等于从该提交编译 wheel；未锁定的传递依赖和基础 tag 重建仍需新核验。

验收辅助脚本两次记录错误（编码约定、预期错误输出流）已留在 `first-lifecycle/wrapper-failure.json`；均在本地辅助脚本修复，没有修改生产程序、业务文件或测试断言，没有重复已完成的安装变更。它们不是业务失败或产品自动恢复证据。

已在最终代码重验并异路径实际使用的正式 Skill：[SKILL.md](E:/Users/27343/Docker/final-recap-codex-1/migrated-installed/rdkit-recap-terminal-fragments/SKILL.md)。最终版本正常新创建的交付仍是未合格候选：[候选 SKILL.md](E:/Users/27343/Docker/final-recap-codex-3/library/candidates/rdkit-recap-terminal-fragments/SKILL.md)。不存在“第三轮正式 SKILL”。

## 支持范围与证据解释

仍只承诺本地 Linux amd64 Docker、CPU、公开依赖及既有阻塞/恢复。远程 GPU、外部挂载、凭据传递、外部服务、第二台主机和多块依赖未扩展。固定 Recap.py 提交是来源身份，不是 wheel 版本；镜像 ID 绑定与完整重验不能证明所有未来下载的字节级可复现性。

归档复制不继承新路径当前资格。异路径安装使用正式 install 与安装 envelope 导入，再经原 runtime-resume 完整重验；这一步是迁移验证，不是正常创建中的恢复。

## 完成标准与下一步

- 上轮迁移映射没有发现新的阻断性遗漏；本轮仅上述局部修复。
- 近期完整性/传输保障有故障反例、跨平台机制验证，第三轮实际发现/作者/独立审阅也使用最终 native 代码。
- 第一轮本轮新正式产物已在最终代码完整执行、默认查询/安装及异路径实际使用。
- **未满足：最终代码正常新创建完成真实规划→Docker→业务→晋升。** 第三轮没有进入构建/业务执行，不能写成化学业务验收失败。
- 无需用户更改全局权限、认证或安装宿主依赖。原访问权限问题在具体操作审批下已解决；独立代码外发审批也已获用户明确授权并完成，不存在待批准操作。
- 下一步需要模型服务/传输能稳定完成规划调用的执行条件。确认该条件变化后，可恢复保存候选，但最终通过仍需另建全新 state/library 正常创建。不要仅延长 600 秒、手工给计划、换样例或把已有恢复算作新创建。没有根据当前证据要求用户调整插件或认证。

可复现命令（真实 Python 路径见上文；在具备已授权网络、Codex 和 Docker 访问条件的终端执行）：

```powershell
# 本轮第三次正常创建原命令；复跑须换从未存在的目录，保留现场
python -m creation_pipeline build validation/final-continuation/release/input.json --state-dir NEW_STATE --library-dir NEW_LIBRARY --keep-debug
# 只恢复第三轮候选：这不算不中断正常新创建
python -m creation_pipeline runtime-prepare E:/Users/27343/Docker/final-recap-codex-3/library --candidate rdkit-recap-terminal-fragments --spec validation/markdown-entry/auto-spec.json
# 已完成且可独立重验的本轮正式产物
python -m creation_pipeline runtime-validate E:/Users/27343/Docker/final-recap-codex-1/migrated-library --candidate rdkit-recap-terminal-fragments
python -m creation_pipeline library E:/Users/27343/Docker/final-recap-codex-1/migrated-library
```

`validation/final-continuation/summary.json` 核对第三轮生产文件哈希与当前代码完全一致；`*-archive.json` 记录原目录到归档的逐文件字节/哈希核验。没有推送、发布、合并远端 PR、删除共享镜像或历史失败证据。最终本地证据提交号与提交后工作区状态在交付消息报告。
