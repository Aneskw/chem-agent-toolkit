# 交接提示词：接着完成 DeepSeek + Docker 验收实验

用法：把下面 ```text 代码块里的内容整段作为下一位 agent 的任务提示词发过去。前提是它能在本机执行命令（`pwsh`）、访问 `E:\Users\27343\Docker`。

```text
你接手的是一个「技能创建流水线 + Docker 验收」实验的收尾工作。请先读这三份文档，再动手：

1. docs/integration/acceptance-experiment-log.md   ← 46 轮实验结果、失败分类、证据位置（必读）
2. docs/integration/pipeline-with-docker-status.md ← 已实现能力与 planner 困境分析
3. validation/deepseek-api/acceptance-normal-input.json ← 本轮批次的封套（16 次调用、repair_rounds=2、pin_base_image=true）

## 代码与环境（已就绪，不要重建）

- 工作副本：E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi（分支 pipeline-with-docker，工作树干净；HEAD 用 `git log --oneline -1` 确认）
- 只读基线（**禁止修改、禁止推送**）：E:\Users\27343\Docker\chem-agent-toolkit-integration
- 凭据在副本内 .env（DEEPSEEK_API_KEY / DEEPSEEK_MODEL / DEEPSEEK_BASE_URL）。**任何输出、提交、日志都不得包含密钥**；证据落盘已有 redact()，不要绕过它。
- 结构化阶段（入口关联、环境规划、契约诊断）与原生阶段（发现/编写/审阅）目前都走 DeepSeek 官方 API（model.backend=deepseek_api，deepseek-v4-pro）。
- Docker Desktop 需要处于运行状态（E:\DockerDesktop\Docker Desktop.exe）。本机已缓存 python:3.11-slim，repo digest = python@sha256:ae952e0a57138a4317b9b61caaa19a8217c2f356803f8d7e63aad08769950937。
- 网络：raw.githubusercontent.com 需要本地代理 127.0.0.1:7897（只在需要的命令上临时加，不要改全局 git 配置）；api.deepseek.com 直连可用；**registry-1.docker.io 当前不可达（run 46 实测 TLS 超时）**；容器内 PyPI 是否可达尚未验证。

## 当前状态（不要高估）

- 验收**尚未端到端通过**。
- 第 36 轮已证明 Docker 构建 + 业务验收链路本身可用（镜像 sha256:42fc066e503ca8b2…，执行报告 8 条记录 7 通过，唯一失败是非法输入拒绝用例未实现）。
- 第 46 轮已证明**规划器能通过全部门禁**（4 次尝试、4 条不同诊断 → prepared，产出 6 条用例与环境计划）。
- 第 46 轮的阻塞点是环境网络：pin_base_image 因 registry-1.docker.io TLS 超时失败。为此加了「拉取失败时复用本地 RepoDigest」的兜底（提交 6097fb5），**但只过了单测，还没被真实批次验证**。

## 你的任务（按顺序）

### 第 1 步：跑一轮真实批次（run47）

先做免费检查，再花钱：

    cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
    docker version --format '{{.Server.Version}}'          # 必须成功，否则先启动 Docker Desktop
    python -m unittest discover -s tests -q                # 期望 554 OK (3 skipped)
    python validation/deepseek-api/verify_prompt_contract.py
    python validation/deepseek-api/verify_acceptance_prompt.py check
    python validation/deepseek-api/verify_planner.py check

然后**只跑一轮**：

    $dir="E:\Users\27343\Docker\acceptance-deepseek-run47-20261028"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $env:PYTHONIOENCODING='utf-8'
    python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
      --state-dir "$dir\state" --library-dir "$dir\library" 2>&1 | Tee-Object -FilePath "$dir\run47.log"

纪律（违反会让结论失效）：
- 失败就停，**不重启、不续跑、不在同一轮内改代码**；
- 不复用任何旧目录；不用 --state-dir 指向 run46 之类；
- 不额外做「探针调用」去消耗预算；单轮上限 16 次调用 / 3600 s。

### 第 2 步：读结果（按这个顺序，别猜）

    $out = <state\outputs\<build_id>>
    Get-Content $out\summary.json                       # status、model_calls、每次调用的耗时/token
    Get-Content $out\records\*.json                     # checks / issues / repair_history / stopped_reason
    Get-ChildItem $out\runtime -Recurse -Filter receipt.json   # gaps[0].code / detail（停止码）
    Get-ChildItem <state\runs\<build_id>\runtime-preparation -Recurse -Filter rejection.json  # 每次规划尝试的完整诊断

预期与分支处理：

A. `base_image_unresolved` 又出现（且本机有缓存镜像）→ 说明 6097fb5 没生效或走错分支：先确认 `docker image inspect python:3.11-slim --format '{{json .RepoDigests}}'` 有 digest，再查 `creation_pipeline/runtime/local.py` 的 `resolve_base_image` 是否走到 `_local_base_image`。

B. 通过 pin_base_image，但 Docker 构建在 `RUN python3 -m pip install -r /opt/skill/requirements.txt` 失败（TLS/超时）→ **这是环境网络，不是代码缺陷**：停下来，把 Docker Desktop 的代理设成 127.0.0.1:7897（或给 pip 配可信索引），**不要为了过而改验收契约或删依赖**。改环境前先向操作者说明你要改什么。

C. 规划阶段又失败 → 先检查诊断是否**指名了对象**（具体用例名、check id、pattern、未读路径、首行引文）。如果不指名，就按本实验的既定原则**先修诊断**（拒绝文本就是下一轮的修复提示词），修完加单元测试、跑全量、提交，然后再花下一次真实调用。不要先想着加预算。

D. Docker 构建成功但业务验收有失败用例 → 逐个看 `execution/report.json`：如果失败反映的是**交付代码没实现它文档承诺的行为**（第 36 轮的空串 SMILES 就是这类），这是**真实缺陷**，应记录并驱动作者阶段修复，**不允许**把用例改弱或删掉。

### 第 3 步：每轮结束必做

1. `python -m unittest discover -s tests -q`（当前基线 554 OK / 3 skipped）；
2. 三个自检脚本（如果改了提示或 schema，先 freeze 再 check：`verify_planner.py freeze` → `verify_acceptance_prompt.py freeze` → 再 check，顺序错了会报 provenance 漂移）；
3. 提交（一个修复一个提交，提交信息写清「哪一轮、诊断原文、为什么这样修」）；
4. 更新 `docs/integration/acceptance-experiment-log.md`：追加这一轮的 run 行（状态 / 调用数 / 停止码 / 停因）与新的修复；
5. 汇报给操作者：本轮结论 + 证据路径 + 下一轮建议（不要只说"失败了"）。

## 完成标准（Definition of Done）

全部满足才算验收通过，缺一条都不算：

1. 规划门禁通过（`prepared`，材料冻结，`pin_base_image` 固定到 digest）；
2. Docker 镜像构建成功（有 `image.id`）；
3. 业务验收**全部通过**：该轮 `execution/report.json` 里每条记录都是 `passed`（历史最好成绩是第 36 轮的 8 条记录 7 通过 1 失败，失败项是非法输入拒绝用例未实现），且必须包含至少一条非法输入拒绝用例与一条真实计算用例；
4. 离线回归与三个自检全绿；
5. 实验记录文档更新到该轮。

## 禁止事项

- 不要 push / merge / 发 PR 到上游仓库（需要操作者明确要求）；
- 不要放宽验收契约来换取通过（改 `none_documented`、删用例、把断言改弱、跳过 rejected 用例都算）；
- 不要在失败轮上 resume / restart；
- 不要打印、复制、提交密钥；
- 不要修改只读基线仓库；
- 不要声称"全链路通过"，除非上面 5 条硬证据都在。
```
