# 验收实验记录：DeepSeek 后端 + pipeline with Docker（run 2 – run 53）

记录日期：2026-10-28

### run47 前置检查补记（2026-10-28）

- 接手 HEAD：`b64d055`；Docker Server `29.8.2`。封套已有未提交修改：原生阶段切回 `codex_cli`。操作者明确选择保留该修改，结构化阶段继续 DeepSeek；不能把 run47 称为全阶段 DeepSeek 批次。
- 原始全量测试在 Docker 可用时意外进入真实入口关联 CLI 调用，未能完成。诊断栈定位到 `test_author_prompt_update_reuses_discovery_but_rebuilds_files` → `prepare` → `associate` → `model_call.run`。停止相关测试及子进程后修复夹具；这不是 run47，也不是额外业务探针，但违反了免费检查应无模型调用的预期，必须单列披露。CLI 审计仅能证明进程/生命周期已启动，不能据此声称实际计费为零或推算供应商调用数。
- 修复：`DiscoveryTests`（含其他套件复用的夹具）显式模拟 Docker 不可用，增加禁止真实 Docker 探测及运行时模型调用的回归；两项旧计数去除不该发生的运行时调用。生产代码、验收契约与封套预算未修改。
- 诊断日志：`E:\Users\27343\Docker\acceptance-run47-preflight-tests.log`；经 `redact()` 保留的关联审计：`E:\Users\27343\Docker\acceptance-run47-preflight-evidence\`；修复后全量回归日志：`E:\Users\27343\Docker\acceptance-run47-preflight-fixed.log`。
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
分支：`pipeline-with-docker`（本地 79 个提交，未合并上游；HEAD 以 `git log --oneline -1` 为准）
只读基线：`E:\Users\27343\Docker\chem-agent-toolkit-integration` @ `78003de4`
配套文档：`docs/integration/pipeline-with-docker-status.md`（现状与卡点分析）、`docs/integration/next-agent-prompt.md`（交接提示词）

---

## 0. 一句话结论

**追加复查（run48/49）未取得新的端到端通过**：run48 暴露并已修复规划补丁的类型审计崩溃；run49 停在文件 fixture 绑定/覆盖诊断，未到 Docker，轮后已补具名诊断。run47 的单轮成功证据仍成立，但不能将它外推成全部 skill 场景稳定成功。最新详情见 §11 及 `docker-acceptance-review-20261028.md`。

**run47 已取得混合后端端到端执行通过的证据**：`ready`、8 次计入预算的调用、规划 `prepared`、本地 digest 兜底生效、Docker 构建成功、执行报告 12/12 `passed`（含真实计算与空串/空白/畸形 SMILES 拒绝）。轮后回归与自检结果见 §10。

原生发现/编写/审阅及独立关联审阅按操作者本次选择使用 Codex CLI，结构化关联/规划使用 DeepSeek；**不能称为全阶段 DeepSeek 通过**。前置测试意外启动真实 CLI 的隔离缺陷及修复见上方补记；不能声称整个会话严格零额外调用。以下 run46 的网络风险与交接计划保留为历史记录，以 §10 的本轮证据为准。

---

## 1. 实验环境与固定约定

| 项 | 值 |
| --- | --- |
| 模型后端 | `model.backend=deepseek_api`，`api_model=deepseek-v4-pro`，官方端点 `https://api.deepseek.com`（不走代理，直连可达，401 探测即有响应） |
| 凭据 | 副本内 `.env`（`DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL`）。**任何输出都不得包含密钥**；证据落盘前经过 `redact()`，历史轮次“凭据形状命中 0” |
| 结构化阶段 | 入口关联、环境规划、契约诊断 → DeepSeek（`json_object` + 本地 `jsonschema` 校验） |
| 原生阶段 | 发现/编写/审阅 → 同为 DeepSeek 单次调用（`model.backend=deepseek_api`）。Codex CLI 账号自 run 13 起被限流（“try again at Nov 2nd, 2026 1:59 PM”），切回 `codex_cli` 可恢复 CLI 轮次 |
| Docker | Docker Desktop 29.8.2，`Docker Desktop.exe` 位于 `E:\DockerDesktop\`。**未运行**时 run 40 直接 `docker_unavailable` |
| 网络 | `github.com` 与 `raw.githubusercontent.com` 需要本地代理 `127.0.0.1:7897`（git 仅按命令加 `-c http.proxy=...`，未改全局配置）；`registry-1.docker.io` **当前不可达**（run 46 实测 TLS 超时）；容器内 PyPI 的可达性**尚未验证** |
| 离线回归 | `python -m unittest discover -s tests -q` → **554 OK (3 skipped)**（2026-10-28 实测） |
| 自检脚本 | `verify_prompt_contract.py`、`verify_acceptance_prompt.py check`、`verify_planner.py check` 三者全绿（提示/schema/provenance 已 freeze 到当前代码） |

### 批次封套（`validation/deepseek-api/acceptance-normal-input.json`）

```
limits.model_calls           16      # 每轮最多 16 次计入预算的模型调用
limits.model_timeout         600     # 单次调用上限（秒）
limits.total_seconds         3600    # 单轮上限（秒）
limits.max_candidates        1
limits.max_builds            1
limits.repair_rounds         2       # 3 个 author/review 候选（本轮实验从 1 提到 2）
model.api_retries            1       # 传输失败后最多 1 次模型请求重试（连接未建立不计入，另有连接重试）
model.api_connect_retries    1       # 只在 TCP/TLS 从未建立时重试（不可能触达模型）
runtime_defaults.options.pin_base_image   true
runtime_defaults.options.total_seconds    2400   # 运行准备阶段上限
runtime_defaults.options.api_max_output_tokens 65536
```

纪律（本实验全程遵守，下一轮继续遵守）：

- 一轮失败就**停**，不重启、不续跑、不“再试一次同样配置”；
- 不在轮内临时改代码（会污染归因）；
- 每轮产物独立目录，绝不复用；
- 修复必须**离线可回归**（单元测试），再花下一次真实调用。

---

## 2. 一轮怎么跑

```powershell
# 1) 跑之前：Docker 必须起来
docker version --format '{{.Server.Version}}'      # 期望 29.x
docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}}' | Select-String python

# 2) 离线回归 + 三个自检（免费，先确认代码没坏）
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m unittest discover -s tests -q
python validation/deepseek-api/verify_prompt_contract.py
python validation/deepseek-api/verify_acceptance_prompt.py check
python validation/deepseek-api/verify_planner.py check

# 3) 跑一轮（目录名递增：run47、run48…）
$dir="E:\Users\27343\Docker\acceptance-deepseek-run47-20261028"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$env:PYTHONIOENCODING='utf-8'
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir "$dir\state" --library-dir "$dir\library" 2>&1 | Tee-Object -FilePath "$dir\run47.log"
```

单轮耗时参考：5–11 次调用约 18–40 分钟（单次调用 80–460 s，长尾是规划/审阅的推理）。

---

## 3. 全量结果表（run 2 – run 53，共 52 轮；另有 4 次前置的 `final-acceptance-*` 批次）

`calls` 是本次构建实际计入预算的调用数；`stop code` 取自该轮 `runtime/<candidate>/<env>/receipt.json` 的 `gaps[0]`。带 “—” 的行在当时没有写出 receipt（崩溃/中断/早期阶段失败），原因栏取自 `records/*.json` 或该轮 `run<N>.log`。

| run | 状态 | 调用 | stop code | 停因 |
| --- | --- | --- | --- | --- |
| 2 | blocked | 6 | `model_stream_interrupted` | 读响应时连接重置（OSError） |
| 3 | blocked | 8 | `explicit_budget` | 显式调用/时间预算用尽 |
| 4 | blocked | 1 | — | 单次调用即停（早期形态） |
| 5 | blocked | 8 | `explicit_budget` | 预算用尽 |
| 6 | failed | 8 | — | 早期阶段失败 |
| 7 | blocked | 10 | `plan_unresolved` | 反复无效补丁：`json_equals` 用数组导致 patched plan schema error |
| 8 | failed | 3 | — | `Unsupported file role: LICENSES.txt`（打包布局） |
| 9 | blocked | 7 | `model_schema_mismatch` | `operations/1` 缺 `value_json` |
| 10 | blocked | 4 | `binding_unresolved` | 关联缺少逐字来源引文与实际调用 |
| 11 | blocked | 8 | `planning_no_progress` | 每个 input operation 必须带具名 check |
| 12 | blocked | 6 | `model_schema_mismatch` | `acceptance_json` 里 `invalid_input: true` |
| 13 | failed | 3 | — | Codex CLI 用量上限（到 2026-11-02 才能用） |
| 14 | failed | 0 | — | 管线守卫拒绝非 `codex_cli` 后端（0 次调用） |
| 15 | failed | 4 | — | 执行检查只有 exit code，缺结果断言 |
| 16 | blocked | 5 | `requirements_unknown` | 需先建立来源约束的执行范围 |
| 17 | blocked | 5 | `entry_unsupported` | 多个 ```python 块，入口不唯一 |
| 18 | blocked | 7 | `entry_declaration_missing` | 声明第 1 块但只有 1 块（索引基准） |
| 19 | blocked | 7 | `model_connection_failed` | `ConnectionResetError` |
| 20 | failed | 2 | — | 把证据定位符 `e1` 当成 `source_id` |
| 21 | failed | 3 | — | SMARTS 的 `](` 被当成 markdown 链接 |
| 22 | blocked | 3 | `requirements_unknown` | 同 16 |
| 23 | failed | 4 | — | `ConnectionResetError` |
| 24 | failed | 3 | — | `json_equals` 必须是对象（3 条检查同时失败） |
| 25 | blocked | 12 | `explicit_budget` | 预算用尽 |
| 26 | blocked | 6 | `plan_unresolved` | `tests[].case_json` 文本不是合法 JSON |
| 27 | blocked | 0 | — | 两个来源下载均 SSL `UNEXPECTED_EOF_WHILE_READING`（0 次调用） |
| 28 | blocked | 12 | `planning_no_progress` | 覆盖率不完整（无可校验谓词） |
| 29 | blocked | 9 | `plan_unresolved` | `case_json` JSON 文本坏 |
| 30 | blocked | 8 | `planning_no_progress` | 环境/接口验证缺失；环境探针被判成 candidate |
| 31 | blocked | 6 | `plan_unresolved` | `case_json` JSON 文本坏 |
| 32 | （中断） | 3 | — | 监控调用打断，无结论 |
| 33 | blocked | 5 | `model_stream_interrupted` | 流中途 `ConnectionResetError`（WinError 10054） |
| 34 | failed | 8 | — | `TypeError: cannot use 'dict' as a set element`（policy 字段类型） |
| 35 | blocked | 10 | `planning_no_progress` | 引文非逐字（换行差异） |
| 36 | failed | 12 | — | **首次 Docker 构建成功**；执行报告 8 条、7 通过、1 失败（`invalid_smiles_empty_rejection`） |
| 37 | blocked | 5 | `binding_review_required` | 独立审阅未批准来源关联（许可证意见误清 binding） |
| 38 | blocked | 7 | `planning_no_progress` | required operation 无具名 check |
| 39 | （崩溃） | — | — | `re.PatternError`（正则中置全局旗标）逃出批次 |
| 40 | blocked | 5 | `docker_unavailable` | 启动时 Docker 未就绪；本轮被人为中断 |
| 41 | blocked | 11 | `planning_no_progress` | 覆盖率 4 条通用原因；根因是有效性谓词写反 |
| 42 | failed | 5 | — | 两轮独立审阅各发现真实文档缺陷，候选轮次用尽 |
| 43 | blocked | 8 | `planning_no_progress` | 单 operation 用 `equals:"smiles"` 当 selector，任何用例都配不上 |
| 44 | blocked | 8 | `plan_unresolved` | grounding 报错不指名用例 → 模型重复请求材料 |
| 45 | draft | 5 | — | 已修复的 blocking issue 仍被判阻塞 → `classify=draft` 静默停止 |
| 46 | blocked | 11 | `base_image_unresolved` | **规划全部通过**；`registry-1.docker.io` TLS 超时 |
| 47 | ready | 8 | —（gaps 为空） | **混合后端执行 12/12 passed**；规划 3 次尝试；本地 digest 兜底、Docker 构建与 pip 安装成功 |
| 48 | failed | 6 | —（导出前异常） | 原有描述符 skill；第三次规划补丁的 operation checks 对象在作用域审计中触发 TypeError，未到 Docker |
| 49 | blocked | 8 | `planning_no_progress` | 同一描述符来源；检查绑定 blank.smi，正常文件用例使用 one-valid.smi，诊断未指明具体排除原因而反复缺覆盖；未到 Docker |
| 50 | blocked | 4 | `model_timeout` | 描述符 A；原生三阶段完成，首次 DeepSeek 规划流在 600 秒内未结束（HTTP 200）；未到 Docker |
| 51 | draft | 3 | —（content_review not_run） | 审阅确认来源与脚本正确，却要求未来 Docker 报告；阶段循环，已补内容/运行职责边界提示；未到规划 |
| 52 | blocked | 6 | `planning_no_progress` | 内容审阅通过，low 规划三次均完成；blank_line 引文拼接但诊断泛化，重复拒绝；已改为具名聚合诊断并补有效性谓词/文件绑定示例 |
| 53 | blocked | 12 | `planning_no_progress` | 多个用例断言缺独立来源逐个被拒，后反复出现未具名空文本结果；最终 persisted_output_success 未断言写出文件内容，尚未到 Docker；轮后集中反馈独立用例错误 |

> 第 2–40 行的“停因”是从该轮 `state/outputs/*/records/*.json`、`runtime/*/*/receipt.json` 与 `run<N>.log` 重建的；如果要精确追某一行，直接看该轮目录里的 `run<N>.log` 尾部和 `materials/planning/<n>/rejection.json`。

前置的 4 次 `final-acceptance-*` 批次（DeepSeek 后端接入之前）：`20261026T165723Z` 因“markdown 块与交付脚本都可能是入口”停在 `entry_ambiguous`；`b2` 早期失败；`b3`/`b4` 均在 `model_unavailable`（模型操作超时、进程树被终止）。它们解释了为什么后来要先把入口声明规则与超时归属做扎实。

---

## 4. 失败分类与对应修复

### 4.1 早期的协议/语义类（run 2–40，均已离线修好并加回归）

| 类别 | 轮次 | 修复 |
| --- | --- | --- |
| 三态非法输入契约（`required`/`none_documented`/`not_applicable`、材料指纹、独立确认、外部锚点、降级证据） | 11/16/22/28/30/38 | `e2e925d` 起；覆盖率与 gaps 分离 |
| 补丁协议（嵌套 JSON Pointer、`remove` 无 value、对象编码） | 7/26/29/31 | `b4a6fc6`、`3d95b0d`、`4978e7b` |
| 基础镜像固定 | 早于 36 | `7f48cf4` |
| 传输韧性（连接重试、单次请求重试、下载重传） | 2/19/23/27/33 | `a8ded37`、`746d7dc`、`c6f7ecd` |
| 提示/校验器一致性（POLICY、schema description、冻结副本） | 全程 | `a8fad7f`、`d569bb0` |
| 交付与审阅语义（入口声明、块索引 1-based 归一化、上游路径别名、作者检查进入规划上下文、许可证意见不影响绑定） | 10/17/18/20/21/37 | `2bebb12`、`4b1c535` 等 |
| 健壮性（policy 字段类型、非法正则、缺 check 的操作） | 34/39/28/38 | `6808ab1`、`fe9017f`、`020c6a6` |

### 4.2 本轮（41–46）的六个修复

| 轮次 | 暴露的问题 | 修复（commit） | 判定语义是否改变 |
| --- | --- | --- | --- |
| 41 | 覆盖率拒绝只说“缺正常输入”，实际是一个 `^C1CC$` 的有效性谓词写反了 | 拒绝文本指名用例、check id、pattern，并说明“check 是有效性谓词，无效输入必须不满足 `violates` 指名的谓词” | 否，仍是不通过 |
| 42 | 独立审阅连续两轮各发现真实文档缺陷（默认小片段过滤路径漏写、`nats-nDummies` 算成 2），候选轮次只有 1 个 | 封套 `repair_rounds` 1→2（16 次调用上限不变） | 否 |
| 43 | 只声明一个 operation，selector 写 `equals:"smiles"`；位置参数的 CLI 没有字面 token 可选 | 位置参数允许 presence-only selector `{args:[{index:0}]}`，且仅在恰好一个 operation 时合法；字面 token 仍必须出现在来源引文中 | 否（新增合法形态） |
| 44 | `Case acceptance requires a verbatim quotation from read source` 不指名用例；真正的问题是一个环境探针带了 acceptance，模型只能重复请求材料 | grounding 拒绝指名用例、未读路径或首行引文，并提示“环境探针不得携带业务 acceptance” | 否 |
| 45 | 作者把**已修复**的 blocking issue 写进 `issues`，`blocking_issues` 仍 `not_run` → `classify=draft` → 静默停止 | 带 `resolution` 的 blocking issue 记为“已修复记录”（非必需 pass）；非 `ready` 停止时把未运行的必需检查写进 `stopped_reason` | 否 |
| 46 | 规划通过后 `pin_base_image` 失败：Docker Hub TLS 超时，而本机已有同名 digest | 拉取失败时复用本地 RepoDigest 并标注 `resolved_from=local_cache`；没有本地 digest 时仍然阻塞 | 否（仍要求 digest） |

对应提交：`fe4921e`（覆盖率诊断）、`106f709`（文档）、`ad428ee`（候选轮次）、`eaeec1a`（位置参数 selector）、`0e230b5`（grounding 诊断）、`cf39db4`（blocking issue 状态语义）、`6097fb5`（本地 digest 兜底）、`0c2ba17`（文档）。

---

## 5. 已经被真实验证的事实

1. **Docker 构建 + 业务验收链路可用**（run 36）：镜像 `sha256:42fc066e503ca8b21664602825ad0b3a6122228ef00ea96c49f1d0ef5b14411f`，容器内环境探针实测 `python=3.11.18 rdkit=2026.09.1`（exit 0）。该轮 `execution/report.json` 共 8 条记录、**7 通过 1 失败**；唯一失败的是 `invalid_smiles_empty_rejection`：期望“空串 SMILES → exit 1 + 诊断 JSON”，实际 exit 0 且输出 `{"leaves": [], "count": 0}`——这是**真实缺陷**（SKILL.md 承诺的拒绝没有对空白输入实现，RDKit 把空串解析成空分子），已据此外加强作者提示（`7cc6ff9`）。
2. **规划器可以通过全部门禁**（run 46）：4 次尝试、4 条**互不相同**的诊断（`required 输入策略必须指明约束` → `invalid_input 必须等于按 operation 的聚合状态` → `required 但无具名 check` → 通过），最终 `prepared`、材料冻结、6 条验收用例、环境计划 `python:3.11-slim` + `pip install -r requirements.txt`。
3. **诊断质量决定收敛速度**：41 轮之前，大批失败伴随“诊断不指名对象”；41–44 把四类诊断改成指名后，46 轮一次走完 8 组契约。
4. **离线回归 554 OK (3 skipped)**；三个自检脚本全绿（提示与 schema 的 freeze 已与当前代码一致）。
5. 本机已缓存 `python:3.11-slim`，repo digest `python@sha256:ae952e0a57138a4317b9b61caaa19a8217c2f356803f8d7e63aad08769950937`（`6097fb5` 之后，即使 registry 不可达也能固定到这个 digest）。

---

## 6. 尚未验证的部分 / 已知风险

1. `6097fb5`（本地 digest 兜底）**只过了单测，没有真实批次确认**。
2. **容器内 `pip install -r requirements.txt` 是否可达 PyPI 未验证**。run 36 构建成功说明当时网络可用；run 46 时 Docker Hub 已 TLS 超时，PyPI 大概率同样不可用。
3. Docker Desktop **没有**配置代理；如需要，应在 Docker Desktop 的 Proxies 设置里指向 `127.0.0.1:7897`（改 `settings-store.json` 需要重启 Docker Desktop，属于环境改动，需与操作者确认）。
4. 42/45 的修复依赖模型行为（是否仍把已修复问题写成 blocking），**没有重复验证**。
5. 规划在 16 次调用封套里剩多少余量是波动的：run 42 用 5 次（内容阶段就结束），run 46 用 11 次（4 次规划）。若某轮审阅又跑两轮，规划只剩 ~9 次。
6. `repair_rounds=2` 是本轮才放宽的；若下一轮出现“第 3 个候选仍被发现新缺陷”，需要决定是继续放宽还是加强作者提示（见 §9）。

---

## 7. 证据在哪里、怎么复核

- **仓库内**：`validation/deepseek-api/evidence/real-batch-run{2..22}-20261027/`（每轮 prompt / response / report / receipt，已随提交入库）。
- **仓库外（第 23 轮起）**：`E:\Users\27343\Docker\acceptance-deepseek-run<N>-<date>\`
  - `run<N>.log`：整轮标准输出（PS 5.1 默认 UTF-16，用 `Get-Content -Encoding Unicode` 读）
  - `state/outputs/<build_id>/summary.json`：`status`、`model_calls`、`model_metrics`（每次调用的 token/耗时/`prompt_sha256`）
  - `state/outputs/<build_id>/records/<skill>.json`：`checks`、`issues`、`repair_history`、`stopped_reason`
  - `state/runs/<build_id>/runtime-preparation/.../materials/planning/<n>/rejection.json`：第 n 次规划尝试的**完整诊断文本**（这是最有价值的单文件）
  - `state/outputs/<build_id>/runtime/<candidate>/<env>/receipt.json`：`gaps[0].code/detail`（停止码）
- **关键轮次的坐标**：
  - run 36：`acceptance-deepseek-run36-20261028` — `image.id`（`sha256:42fc066e5…`）、`build-log.json`、`execution/report.json`（22 KB）
  - run 41/43/44：`materials/planning/<n>/rejection.json` 里能逐字看到“通用原因 → 具名诊断”的差别
  - run 46：`runtime/<candidate>/<env>/receipt.json` 的 `base_image_unresolved :: ... TLS handshake timeout`；同轮 `materials/planning/3/environment_plan.json` 是**第一份通过全部门禁的计划**

---

## 8. 代码与分支状态

- 分支 `pipeline-with-docker`，工作树干净；本地 79 个提交（HEAD 以 `git log --oneline -1` 为准，最新是文档提交）。
- 已推到 fork 的是**单提交 squash 分支** `upload-pipeline-with-docker`（`e3a3a07`，基于上游 `main` `1e7cada`，树等价于 `38d2509`）。**它比本地分支落后 8 个提交**（`fe4921e` 起的六个修复 + 两个文档提交）。
- 上游 `Aneskw/chem-agent-toolkit` 对 `s273436149` 无写权限；历史与上游无共同祖先，只能以 squash 分支 + PR 的形式提交。
- 重新上传（需要操作者确认后执行；用 `commit-tree` 造单提交，避免把 79 个提交的历史带出去）：

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$tree   = git rev-parse pipeline-with-docker^{tree}
$parent = git rev-parse origin/main
$commit = git commit-tree $tree -p $parent -m "pipeline with docker: DeepSeek planner/association/diagnosis, actionable gate diagnostics, pinned base image"
git branch -f upload-v2 $commit
git diff --stat origin/main upload-v2 | Select-Object -Last 1     # 先确认差异符合预期
git -c http.proxy=http://127.0.0.1:7897 push fork upload-v2:upload-pipeline-with-docker --force-with-lease
```

---

## 9. 交接要点

**下一步只做一件事**：再跑一轮（`run47`），确认 `6097fb5` 是否把 `pin_base_image` 放过去、以及容器内 `pip` 是否有网。

- 如果 `pin_base_image` 通过、`pip` 也通 → 观察 Docker 构建与业务验收，这一轮极有可能拿到端到端通过（或暴露出“交付代码是否实现其文档承诺的拒绝行为”这类**真实内容缺陷**，那也要如实记录，不要放宽门禁）。
- 如果构建阶段 `pip` 报网络错误 → **停手，改环境**（Docker Desktop 代理 / `pip` 索引），不要动验收代码。
- 如果规划又失败 → 先看该轮 `rejection.json`：诊断是否指名了对象？如果不是，按本实验的既定原则先修诊断（可离线回归），再考虑放宽 `model_calls`。

**不要做**：

- 不要为了通过而放宽验收契约（`none_documented` 换 `required`、删用例、把断言改弱）；
- 不要在失败轮上 restart/resume；不要在同一轮里改代码；
- 不要 push/merge 上游；不要打印或复制密钥；不要动只读源仓库；
- 不要把“规划通过”说成“验收通过”——业务验收要求该轮执行报告全部 `passed`（历史最好 8 条 7 通过）。

## 10. run47：混合后端完整执行证据（2026-10-28）

- 本轮开始前代码提交 `4118c0d`（测试隔离修复），封套保留操作者已有的 `codex_cli` 原生阶段修改，未扩大 16 次 / 3600 秒预算。只启动一次，不续跑、不重启、轮内未改代码。
- 构建 `20261028T192922-04c5c49e`，北京时间 19:29:22–20:04:04，约 34 分 42 秒。状态 `ready`，计入预算 8 次：发现、编写、内容审阅、结构化关联、独立关联审阅、规划 3 次。`summary.model_metrics` 的结构化阶段 usage 未合并，不能将其 reported_totals 当完整成本；详细回执在冻结证据中。
- 规划诊断依次为 `Input policy requires scope and an exact quotation from read source`、`Outcome assertion role must match the promised purpose: completion [documented-terminal-fragments]`，第三次通过，`prepared`、材料冻结。第一条诊断仍不指名对象，但本轮已自行修复通过，未为此改契约。
- `base-image.json`：`python:3.11-slim-bookworm` → `python@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89`，`resolved_from=local_cache`。这是 `6097fb5` 的真实批次验证；与之前 `python:3.11-slim` 的缓存摘要不同。
- 构建镜像 `sha256:8163966a3054bf23b595847e9bd82ae0cca99e087181654b05c88c631339f70f`；pip 安装成功，容器实测 RDKit `2026.09.1`。未改 Docker Desktop 代理设置，也不据此宣称 Docker Hub 直连已恢复。
- `execution/report.json`：12 条记录全部 `passed`，7 条规划用例 + 5 条作者检查。真实计算 `documented-terminal-fragments` 输出 3 个文档片段；`valid-empty-decomposition` 输出空列表与 count 0；空白、空串、`C1CC` 均 exit 2 并输出 `invalid_input`。环境、接口、行为验证全部通过，`acceptance.complete=true`、`coverage_complete=true`、无 gaps/blockers。`scientific_correctness=not_evaluated`。
- 原始构建 `receipt.json` 保留 `built` / `not_run`，其含义是构建时尚未业务执行；最终结论来自后续 `execution/report.json` 与记录中的 `runtime.status=execution_passed`，不能只读构建回执推断未执行。
- 轮前及轮后全量回归均为 **555 OK (3 skipped)**（增加 1 条隔离回归）；三个提示契约自检全部通过，无提示/schema 变更，无需重新 freeze。轮后日志：`E:\Users\27343\Docker\acceptance-run47-postflight-tests.log`。额外只读复核 `artifacts.evidence.verify` 验证冻结指纹通过，12 条记录及真实计算/空串拒绝断言全部通过，简明审计：`E:\Users\27343\Docker\acceptance-deepseek-run47-20261028\acceptance-audit.json`。
- 五项完成标准（prepared+固定 digest、image.id、业务全 passed 且含真实计算与拒绝、离线与自检全绿、本文更新）均已有证据；此结论限于本轮混合后端配置。前置隔离事故意味着整个会话不满足“零额外真实调用”的实验纪律，不能将本轮管线内的 8 次计数当作整个会话的供应商请求总量。
- 成功后 `state/runs/<id>` 已被流水线清理；拒绝记录和模型回执已冻结到输出 `evidence/.../runtime/`，不应再从已删除的 runs 目录找证据。

证据根目录：`E:\Users\27343\Docker\acceptance-deepseek-run47-20261028\state\outputs\20261028T192922-04c5c49e`。

| 证据 | 相对上述根目录的路径 |
| --- | --- |
| 状态、调用与时间 | `summary.json` |
| 规划状态与最终执行状态 | `records/rdkit-recap-terminal-fragments.json` |
| digest、冻结计划、完整规划拒绝、模型回执 | `evidence/rdkit-recap-terminal-fragments/b7b153af827c4167aa016d2430cfd44e/runtime/` |
| 镜像 ID、构建日志、12 条执行记录 | `runtime/candidate-0db42e9bf94ddd230ae29a2db252b2c177c4a722a121599877a07a3e51b18ea1/9494789ada5d4fd49ed00afbb20fe7e6/` |

下一步：无需为了本次混合后端验收再跑一轮。若要证明全阶段 DeepSeek，另行使用新轮次和对应封套；不要复用 run47，也不要把本轮结果外推到未测试的后端组合。没有 push、merge 或创建 PR。

## 11. 操作者追加复查与实验（run48 起）

操作者随后授权代码审查和 1–2 个基于原有 skill 的完整实验。发现并修复真实入口执行绑定漏洞（`6e76924`）；run47 的原始入口未利用此漏洞，修复后当前严格资格复核仍通过。run48 又暴露了规划补丁的嵌套类型审计崩溃，不能将其描述为通过。完整审查范围、反例验证、修复依据和追加实验见 `docker-acceptance-review-20261028.md`。最多执行 run48/run49 两个新批次，不恢复失败轮，不放宽契约。

## 12. 再次授权的四场景验收（run50 起，进行中）

操作者在 run49 后明确授权：两轮描述符文件实验先调试到通过，再以两个典型场景验收，遇错修复后新开轮次重跑。此新授权取代 §11 的两个批次数量限制；仍不允许恢复失败轮、放宽断言或推送上游。计划为两个独立描述符成功批次、原子映射审计、ASE XYZ 几何检查；当前成功数 0/4。具体封套、结果与后续配置调整见 `extended-acceptance-campaign.md`，进度机器记录为 `validation/deepseek-api/extended-acceptance-progress.json`。
