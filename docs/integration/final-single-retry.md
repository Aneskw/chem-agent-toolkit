# 最终代码的单次串行 RECAP 新创建（2026-10-26）

**结论：本次正常新创建未成功，最终验收仍未通过。** 预检通过，但 planner 在原有 600 秒限制到期时未返回有效方案；候选保留为 runtime_blocked，业务验收 not_run。本次仅执行用户明确授权的一次正常创建；不重新合并，不修改生产代码，不做候选恢复或其它模型审查，不重跑已有充分机制验证。失败后未追加任何模型调用、构建或恢复。

## 基线与实验边界

实际起点为 `integration/planner-timeout` / `28879cf`，起始工作区干净，没有后续提交；仓库及父目录未发现适用 AGENTS.md。生产修改仍为 `38bffa6`、`8c1cac8`。运行前核对全部 production Python 文件 SHA-256，与上一轮 release/effective-settings.json 完全一致。

先读取 `final-continuation.md`，复用该版本的 Windows 248 项（245 通过、3 POSIX 跳过）、Linux 63/63，以及独立审查和迁移政策证据。不把旧产物的执行或迁移视为这次新产物通过。

重跑依据是用户提出的暂时性连接异常假设。历史证据确有接近同时的断流，第二轮恢复的 planner stderr 在北京时间 16:09:03.418 明确记录 WebSocket `tls handshake eof`。本次只检验当前条件下能否完成，不预先判定网络恢复，也不将串行执行的结果当作此前并发造成故障的因果证明。

## 预检和实际配置

沿用平台允许的具体操作审批，没有改变全局权限、认证或用户配置。预检先完成，再启动正式创建，没有并发模型任务。

- 真实 Python：`C:/Users/27343/AppData/Local/Python/pythoncore-3.14-64/python.exe`，3.14.3；没有使用 WindowsApps 别名。
- 固定来源重新通过 URL 下载：RDKit commit `237a1d9027c800784afed8788540f38a3aa595f8` 的 Recap.py 为 20,662 字节，SHA-256 `d4f9b96945c2c92c095d758a7f460360dc1a73fb75831bfdb8482f8f9aaec3fc`；license.txt 为 1,580 字节，SHA-256 `daeb8d194502cbcf34c05c39541a0d02be65bc9bada5b891c1974cd24e9fca30`。
- Docker engine 探测成功，`linux/x86_64`。
- 一次最小真实 gpt-6-astra 结构化调用约 15.241 秒返回 `{"ok":true}`，有完成事件；不是业务验收。
- 审计/临时目录实际写入并读取，正式运行目录另做逐字读写验证。

正式输入从 `validation/final-continuation/release/input.json` 读取，程序断言除 batch.label 外整个对象不变。新 label/state/library 为 `final-recap-codex-4`。model 仍为 gpt-6-astra；tool-free 继承 medium reasoning effort / default service tier，native 保留既有 ignore-user-config 政策。planner 单次 600 秒不变；production 无新增整体配额。完整配置、隔离参数、文件哈希和开始/退出命令存于 `validation/final-single-retry/`。

## 正常流程记录

唯一正常 build：`20261026T163755-8844c416`。来源准备、发现、编写、独立内容审阅、入口关联与独立关联审阅已执行。作者自主交付 `scripts/terminal_fragments.py`；没有要求作者必须输出脚本，也没有人工补 adapter、Skill、计划、Dockerfile 或断言。

发生一次正常流程内包装修正：根目录 `NOTICE.txt` 被文件角色规则拒绝，原作者将通知转到 `references/attribution.md` 并更新链接。该修正不是运行后化学业务失败修复，不能据此新增业务修复闭环声明。所有作者反馈和回执原样保留。

实际入口接受 `--smiles`，调用 RDKit 的 `RecapDecompose` 和 `GetLeaves`，以 JSON 返回终端片段、count 与实际 RDKit 版本；有效空结果成功，空白/非法输入与依赖/处理失败分开。作者检查覆盖实际脚本示例、合法空结果、空白与非法 SMILES。静态核对和审阅不代替容器业务验证。

本次实际启动命令（已用目录不得覆盖重跑）：

```powershell
python -m creation_pipeline build validation/final-single-retry/input.json --state-dir E:/Users/27343/Docker/final-recap-codex-4/state --library-dir E:/Users/27343/Docker/final-recap-codex-4/library --keep-debug
```

历史报告与失败现场保持原样。没有推送、发布、合并远端 PR 或删除镜像/用户数据。

## 最终结果与失败归类

正常 build 退出 1，status=blocked，1 个候选，model_calls=7（不含预检的一次最小调用）。内容状态 passed，资格 accepted=false；修订为 `rev-6ab0f55745965203027ec263e0311d3c753fc9aa496445735c51e153bf756fd2`。

planner 于北京时间 **16:45:45** 启动，约 **16:55:45** 在 **600.063 秒**停止。request 记录 prompt_bytes=41695、timeout_seconds=600；stdout 仅有 thread.started、turn.started，无方案、turn.completed、usage。process.status=timed_out、io_errors=[]、stream_threads_finished=true；清理后的 returncode=0 不是成功证据，程序正确拒绝并保留阻塞状态。

| 类别 | 本次证据及结论 |
|---|---|
| 权限与来源 | 固定 URL、哈希、目录读写、Docker engine 预检通过，没有本轮权限拒绝 |
| 初始化/基本模型访问 | 最小真实调用及发现、作者、独立审阅、关联成功；不是整体初始化或认证失败 |
| 传输/服务完成性 | planner 未返回完成事件，单次超时；没有足够证据区分服务处理、响应传输或其它底层原因 |
| 返回格式/方案内容 | 没有答案可解析，没有进入方案内容校验；不能称为 JSON 格式错误或无效 Docker 方案 |
| Docker 构建 | 未进入；无本次业务镜像和构建失败 |
| 化学业务执行 | 未执行，business_acceptance=not_run；不能写成业务断言失败 |
| 正式资格及安装 | 未晋升，保留 candidates；没有本次正式产物，未做安装、迁移或实际使用，也没有借旧产物替代 |

本次全部 native/runtime stderr 中未观察到 responses_retry 或 TLS handshake 重连事件。planner stderr 只有既有的 PowerShell shell snapshot 不支持告警。发现回合有 analytics-events 上报失败告警，这是遥测上报，不是模型响应流断开证据。本次没有把它当作 planner 根因。

串行执行仍出现超时，所以不能把此前并发视为已确定根因。也不能因本次没有 TLS 错误就宣布网络/服务已恢复，或证明服务端已经收全并完成请求。此次实验没有唯一定位底层原因，按用户限制不追加诊断重试、不改变传输方式、不延长超时。

## 交付与证据

- 独立证据目录：`E:/Users/27343/Docker/chem-agent-toolkit-integration/validation/final-single-retry/`。
- 原现场：`E:/Users/27343/Docker/final-recap-codex-4/`；全部 202 个现场文件逐文件核对后复制到 `run-snapshot/`，清单为 `archive.json`。复制不继承任何新路径资格。
- 本次生成但**未合格**的 [SKILL.md](E:/Users/27343/Docker/final-recap-codex-4/library/candidates/rdkit-recap-terminal-fragments/SKILL.md)；其实际入口为同目录下 `scripts/terminal_fragments.py`。
- planner 原始证据在 `run-snapshot/state/runs/20261026T163755-8844c416/runtime-preparation/rdkit-recap-terminal-fragments/ec03b83616df43a7960b49cb27c6c77b/materials/planning/0/model-0/`，包含 request/process/events/stdout/stderr/schema/timeout；父目录保存原 prompt。
- `preflight/results.json`、`effective-settings.json`、`normal-build-command.json`、`summary.json` 分别记录预检、配置与哈希、唯一运行退出结果、当前资格与重连扫描。

本次新增内容仅为验收辅助记录脚本、报告及证据；生产文件哈希在运行前和归档时两次一致。已有审查/回归/历史迁移证据保持其原有范围，本次没有新增成功业务验收或成功修复闭环声明。全部工作本地提交；最终提交号和提交后分支/干净状态在交付消息报告。已停止，等待用户审阅。
