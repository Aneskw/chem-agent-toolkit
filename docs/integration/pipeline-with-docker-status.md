# 现状报告：pipeline + Docker（DeepSeek 副本）

日期：2026-10-28

**追加复查更新（run48/49）**：两轮原有描述符 skill 实验均未到 Docker。run48 的补丁审计 TypeError 已修复（`3f8f78d`）；run49 停在文件 fixture 绑定导致的覆盖缺口，已补充具名诊断及离线回归。run47 真实通过仍成立，但尚不能声称新增 skill 场景也已端到端通过或流水线已普遍稳定。详见 `docker-acceptance-review-20261028.md`。

**最新结果（run47）**：按操作者选择，原生阶段使用 Codex CLI，结构化阶段使用 DeepSeek；该混合配置已得到 `ready`、8 次调用、规划 `prepared`、本地 digest 固定、Docker 构建成功和业务执行 12/12 `passed` 的证据（含真实计算与非法输入拒绝）。详见 `acceptance-experiment-log.md` §10。以下分析保留 run46 的历史背景，不能据此覆盖最新结果；也不能将 run47 表述为全阶段 DeepSeek 通过。前置离线测试曾意外进入真实 CLI，已修复夹具隔离并单列披露。
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
分支：`pipeline-with-docker`（源自 `integration/deepseek-api-backend`，本地提交，未合并上游）
源目录（只读基线）：`chem-agent-toolkit-integration` @ `78003de4`

---

## 1. 已经实现并通过离线回归的能力

| 能力 | 说明 | 关键提交 |
| --- | --- | --- |
| DeepSeek 结构化后端 | 入口关联、环境规划、契约诊断走官方 `https://api.deepseek.com`，`response_format=json_object` + **本地 jsonschema 校验**，无提供方回退 | 早期 `deepseek_api` 迁移 |
| 原生阶段可切 DeepSeek | `model.backend=codex_cli`（默认，原样保留）或 `deepseek_api`（单次有界调用，作者阶段回传 `files`，宿主机落盘后仍走原 `delivery.finish`） | `4b1c535` |
| 三态非法输入契约 | `required` / `none_documented` / `not_applicable`，按 operation 判定；材料指纹、独立确认、外部锚点、降级证据、`coverage_complete`/`validation_gaps`/`blockers` 分离 | `e2e925d` 起 |
| 补丁协议 | 嵌套 JSON Pointer（`/acceptance_json/<ptr>`）、`remove` 不再强制 `value_json`、计划路径与补丁路径统一接受对象编码 | `b4a6fc6`、`3d95b0d`、`4978e7b` |
| 基础镜像固定 | `pin_base_image`：拉取并解析 repository digest，渲染 `FROM repo@sha256:…`，摘要随环境冻结，执行前校验本机存在 | `7f48cf4` |
| 传输韧性 | 连接阶段重试（**不可能触达模型**，单独计数）、可选 1 次请求重试、下载传输失败重传（HTTP 状态错误不重试） | `a8ded37`、`746d7dc`、`c6f7ecd` |
| 提示协议自检 | `verify_prompt_contract.py` 检查 POLICY / schema description / 冻结副本逐项一致；`verify_acceptance_prompt.py` 记录发送指纹 | `a8fad7f`、`d569bb0` |
| 交付与审查语义 | 作者声明的入口、块索引（含 1-based 单块可见归一化）、上游路径别名、作者检查进入规划上下文、许可证意见不影响绑定判定 | `2bebb12`、`4b1c535` 等 |
| 健壮性 | 非法 policy 字段类型、非法正则、缺失操作 check 等均为**可修复的计划拒绝**，不再让整批崩溃 | `6808ab1`、`fe9017f` |
| 诊断可操作性 | 覆盖率拒绝指名用例/check/pattern，grounding 拒绝指名用例与未读路径或首行引文；位置参数允许 presence-only selector | `fe4921e`、`0e230b5`、`eaeec1a` |
| 交付状态语义 | 带 `resolution` 的 blocking issue 记为已修复；非 `ready` 停止时写明未运行的必需检查；拉取失败时复用本地 RepoDigest | `cf39db4`、`6097fb5` |

离线回归：`python -m unittest discover -s tests -q` → **554 OK (3 skipped)**。

## 2. 已经被真实实验证实的部分

**第 36 次运行首次跑完“发现 → 编写 → 独立审阅 → 入口绑定 → 环境规划 → Docker 构建 → 业务验收”全链路到执行阶段**：

| 阶段 | 结果 |
| --- | --- |
| 来源准备 / 发现 / 编写 / 独立审阅 | ✅ |
| 入口绑定 | ✅ 作者声明 `scripts/recap_leaves.py` |
| 环境规划（含三态契约、覆盖率、grounded 引文） | ✅ `prepared`，材料冻结 |
| `pin_base_image` | ✅ 解析并冻结 digest，`base-image.json` 生成 |
| Docker 构建 | ✅ `image sha256:42fc066e5…`，容器内 `python=3.11.18 rdkit=2026.09.1` |
| 业务验收 | ⚠️ 执行报告 8 条记录：7 通过、1 失败（`invalid_smiles_empty_rejection`） |

失败用例是**门禁正确捕获的真实缺陷**：用例传入空串 `""`，期望脚本以 exit 1 拒绝；但 RDKit 把空串解析为“空分子”，脚本于是输出 `{"leaves": [], "count": 0}` 并 exit 0——即 SKILL.md 承诺的“无效 SMILES 退出 1”并未对空白输入实现。已据此强化作者提示：**文档里承诺的拒绝必须由交付代码显式实现，不能依赖上游解析器**（`7cc6ff9`）。

其余轮次（13–39）的失败几乎都发生在规划阶段，且每次只暴露一个契约缺口。

### 2.1 第 41–46 轮：从“协议没走通”到“规划全部通过、卡在环境网络”

恢复验收后连续跑了六轮（每轮一个独立授权批次，失败即停、不重启不续跑）。每一轮暴露的都不是重复缺陷，而是下一层：

| 轮次 | 调用 | 停在哪 | 门禁说了什么 | 据此做的修复 |
| --- | --- | --- | --- | --- |
| 41 | 11 | 规划，`planning_no_progress` | 4 条通用覆盖率原因，且与上一轮逐字相同 | 覆盖率诊断指名用例、check id 与 pattern，并说明 check 是有效性谓词（`fe4921e`） |
| 42 | 5 | 编写/审阅，`failed` | 独立审阅连续两轮各发现真实文档缺陷（默认小片段过滤路径未写、`nats-nDummies` 算成 2） | 候选轮次 1→2（`ad428ee`），仍守 16 次调用封套 |
| 43 | 8 | 规划，`planning_no_progress` | 只声明一个 operation，selector 却写 `equals:"smiles"`，任何用例都配不上 | 位置参数允许 presence-only selector（`eaeec1a`） |
| 44 | 8 | 规划，`plan_unresolved` | `Case acceptance requires a verbatim quotation` 不指名用例；模型只能重复请求材料 | grounding 诊断指名用例、未读路径、首行引文，并提示环境探针不得带 acceptance（`0e230b5`） |
| 45 | 5 | 编写，`draft` | 作者把“已修复”的 blocking issue 写进 issues，`blocking_issues` 仍 `not_run` → `classify=draft` → 静默停止 | 带 `resolution` 的 blocking issue 记为已修复记录；非 `ready` 停止时写出未运行的必需检查（`cf39db4`） |
| 46 | 11 | **规划全部通过**，`base_image_unresolved` | `registry-1.docker.io` TLS handshake timeout，而本机已有同名镜像的 RepoDigest | 拉取失败时复用本地 RepoDigest 并标注 `resolved_from=local_cache`（`6097fb5`） |

第 46 轮是**恢复验收后第一次通过全部规划门禁**：4 次规划尝试，每次诊断都不同（`required 输入策略必须指明约束` → `invalid_input 必须等于按 operation 的聚合状态` → `required 但无具名 check` → 通过），最终 `prepared`、材料冻结、产出 6 条验收用例与 `python:3.11-slim` / `pip install -r requirements.txt` 的环境计划。它随后停在 `pin_base_image` 的**环境网络**上，而不是协议上。

这一节的结论很重要：**规划器并非不可救**。第 41 轮之前，30 多轮里绝大多数失败都伴随“诊断不指名对象”，模型只能盲修；把诊断改成指名（并且允许位置参数这种真实存在的调用形态）之后，第 46 轮一次性走完了 8 组契约。剩下的瓶颈是 Docker Hub / PyPI 的连通性。

`6097fb5` 只做了离线验证（新增 1 个单测，`554 OK (3 skipped)`），**还没有真实批次确认**：下一轮若 Docker 构建阶段又因容器内 `pip install` 无外网失败，那就是 PyPI 侧的网络问题，需要在 Docker Desktop 里配置代理（`127.0.0.1:7897`）而不是继续改代码。



## 3. 当前卡点：planner 的困境（重点）

### 3.1 一次结构化输出要同时满足互不相关的多组精确契约

规划器被要求在**一次 JSON 回答**里同时满足：

1. `PLAN_SCHEMA` 类型约束（含 11 类枚举、封闭对象）；
2. operation selector 必须是**来源引文中逐字出现**的字面 token；
3. `input_contract` 三态一致（聚合状态、required 必须有具名 check + 拒绝用例）；
4. check 的 `channel/key/pattern` 必须是**可编译正则**并真正能区分有效/无效输入；
5. 覆盖率：每个 purpose、每个 operation、每个 check、持久化要求都要有对应用例；
6. 每条断言都要 **grounded**（逐字引文，允许空白差异但不允许改写）；
7. 案例 `acceptance` 需要 purpose/assertion/violates/invalid_input_reason 齐备；
8. 与作者已声明检查共存且不冲突。

这些契约**彼此正交**，但共用一次输出预算与一次修复轮。实践中模型经常“解决了一个、踩中另一个”。

### 3.2 每次失败只回一个错误，而修复轮很贵

- `validate_plan`/`contracts`/`coverage` 都是 fail-fast：只抛第一个错误；
- 一轮 12–16 次调用里，作者阶段（discovery+author+review）就要 3–5 次，规划只剩 2–4 次；
- 同一错误重复即触发“无进展”停止（这是正确的防浪费规则，但也压缩了收敛空间）；
- 因此**修复轮的有效带宽只有 1–2 次**，一次只够修一个契约。

### 3.3 实测失败模式清单（同一条计划链路上的连续踩坑）

| 运行 | 规划阶段的阻塞 | 性质 |
| --- | --- | --- |
| 3/5/7 | selector 字面 token、`value_json` 非法 | 提示/编码 |
| 26/29/31 | `case_json` 手写转义坏掉 | 编码 |
| 28/38 | `required` 但无具名 check | 契约理解 |
| 30 | 环境探针标成 `candidate`，不计入 supported | 契约语义 |
| 34 | `invalid_input` 返回成对象 → `TypeError` 崩溃 | 类型健壮性 |
| 35 | 引文非逐字（换行差异） | 证据严格性 |
| 39 | 正则含中置全局旗标 → `re.PatternError` 崩溃 | 类型健壮性 |
| 41 | 有效性谓词写反（check 只匹配无效输入）→ 4 条通用覆盖率原因、修不到点 | 契约语义 + 诊断可操作性 |
| 42 | 两轮独立审阅各发现真实文档缺陷（默认过滤路径、原子数算错） | 内容质量 / 候选轮次预算 |
| 43 | 位置参数却用 `equals:"smiles"` 当 selector，任何用例都配不上 | 协议缺口（位置参数无法被选择） |
| 44 | grounding 报错不指名用例，模型只能重复请求材料 → `plan_unresolved` | 诊断可操作性 |
| 45 | 已修复的 blocking issue 仍被视为阻塞 → `draft` 静默停止 | 状态语义 |
| 46 | 规划全部通过，`pin_base_image` 因 Docker Hub TLS 超时失败 | 环境网络（非协议） |
| 22/16 | 引用用证据定位符 `e1` 当 `source_id`；`runtime_requirement` 返回字符串 | 字段语义 |

以上每一项都已被**离线修复并加入回归**，但这也说明：模型并不是“不会写计划”，而是**难以在一次回答里同时命中 8 组精确契约**。

### 3.4 结构性判断

1. **契约数量 > 单轮修复带宽**：与其继续逐个打补丁，不如把验收契约分级（先让“能跑的最小计划”通过 Docker，再分级收紧），或把规划拆成环境/契约/用例三段，每段单独校验与修复。
2. **一次返回全部错误**：把 fail-fast 改成“收集所有 gate 错误一次性反馈”，可让每个修复轮价值翻倍——这是当前投入产出比最高的改动。
3. **让执行先行**：当前是“先把断言写死再执行”；对这类 CLI 工具，先允许 `none_documented`/空检查跑通一次，再据真实输出补断言，可显著降低规划难度（但会与“不从输出倒推预期”的原则冲突，需要独立审阅把关）。
4. **诊断必须指名对象**：第 41 轮证明，泛化原因（“缺正常输入”）会把模型推向错误方向（继续加用例），而真正的缺陷是一个写反的谓词。把用例名、check id、pattern 和修复方向写进拒绝文本，是比增加调用预算更便宜的改进。

## 4. 最小剩余工作

1. 再跑一轮真实批次，确认 `6097fb5` 的本地 digest 兜底真的把 `pin_base_image` 放过去；这是唯一还没被真实运行验证的修复；
2. 若 Docker 构建再失败，先看是不是**容器内** `pip install` 没有外网（PyPI 侧）：那是环境问题，应在 Docker Desktop 里配置代理 `127.0.0.1:7897`，不要继续改代码；
3. 规划已不再是一轮一坑：第 46 轮连续修了 4 次就把 8 组契约全部命中。若后续仍反复，优先做“一次收集所有 gate 错误”（当前覆盖率门禁已聚合，其余仍是 fail-fast），其次把规划拆成环境/契约/用例三段；
4. 业务验收：第 36 轮已证明 Docker 与验收链路可用（8 条记录 7 通过，唯一失败是拒绝用例未实现），剩余问题是“交付代码是否实现其文档承诺的拒绝行为”，第 42 轮的审阅发现表明内容质量门禁是有效的。

## 5. 复现

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m unittest discover -s tests -q                      # 554 OK (3 skipped)
python validation/deepseek-api/verify_prompt_contract.py     # 提示与校验器一致性
python validation/deepseek-api/verify_acceptance_prompt.py check
python validation/deepseek-api/verify_planner.py check
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
```

证据：

- 仓库内 `validation/deepseek-api/evidence/real-batch-run{2..22}-20261027/`（该区间已随提交入库，每轮 prompt/response/report/receipt，凭据形状命中 0）；
- 第 23 轮起每轮产物在副本外的同级目录 `E:\Users\27343\Docker\acceptance-deepseek-run<N>-<date>\`（`state/` 审计目录 + `run<N>.log`），未入库以免把运行时状态塞进仓库；
- 第 36 轮目录 `acceptance-deepseek-run36-20261028` 内含**首次成功 Docker 构建**的 `image.id`（`sha256:42fc066e5…`）、`build-log.json` 与 22 KB 的业务验收 `execution/report.json`；
- 第 41/43/44/46 轮目录内的 `materials/planning/<n>/rejection.json` 与 `runtime/<candidate>/<env>/receipt.json` 可以逐字核对本节 §2.1 的每一次诊断与停止码；第 46 轮的 `base-image` 失败记录是 `base_image_unresolved :: ... TLS handshake timeout`。


