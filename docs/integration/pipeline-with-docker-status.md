# 现状报告：pipeline + Docker（DeepSeek 副本）

日期：2026-10-28
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

离线回归：`python -m unittest discover -s tests -q` → **540 OK (3 skipped)**。

## 2. 已经被真实实验证实的部分

**第 36 次运行首次跑完“发现 → 编写 → 独立审阅 → 入口绑定 → 环境规划 → Docker 构建 → 业务验收”全链路到执行阶段**：

| 阶段 | 结果 |
| --- | --- |
| 来源准备 / 发现 / 编写 / 独立审阅 | ✅ |
| 入口绑定 | ✅ 作者声明 `scripts/recap_leaves.py` |
| 环境规划（含三态契约、覆盖率、grounded 引文） | ✅ `prepared`，材料冻结 |
| `pin_base_image` | ✅ 解析并冻结 digest，`base-image.json` 生成 |
| Docker 构建 | ✅ `image sha256:42fc066e5…`，容器内 `python=3.11.18 rdkit=2026.09.1` |
| 业务验收 | ⚠️ 5/6 通过；1 个拒绝用例失败 |

失败用例是**门禁正确捕获的真实缺陷**：用例传入空串 `""`，期望脚本以 exit 1 拒绝；但 RDKit 把空串解析为“空分子”，脚本于是输出 `{"leaves": [], "count": 0}` 并 exit 0——即 SKILL.md 承诺的“无效 SMILES 退出 1”并未对空白输入实现。已据此强化作者提示：**文档里承诺的拒绝必须由交付代码显式实现，不能依赖上游解析器**（`7cc6ff9`）。

其余轮次（13–39）的失败几乎都发生在规划阶段，且每次只暴露一个契约缺口。

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
| 22/16 | 引用用证据定位符 `e1` 当 `source_id`；`runtime_requirement` 返回字符串 | 字段语义 |

以上每一项都已被**离线修复并加入回归**，但这也说明：模型并不是“不会写计划”，而是**难以在一次回答里同时命中 8 组精确契约**。

### 3.4 结构性判断

1. **契约数量 > 单轮修复带宽**：与其继续逐个打补丁，不如把验收契约分级（先让“能跑的最小计划”通过 Docker，再分级收紧），或把规划拆成环境/契约/用例三段，每段单独校验与修复。
2. **一次返回全部错误**：把 fail-fast 改成“收集所有 gate 错误一次性反馈”，可让每个修复轮价值翻倍——这是当前投入产出比最高的改动。
3. **让执行先行**：当前是“先把断言写死再执行”；对这类 CLI 工具，先允许 `none_documented`/空检查跑通一次，再据真实输出补断言，可显著降低规划难度（但会与“不从输出倒推预期”的原则冲突，需要独立审阅把关）。

## 4. 最小剩余工作

1. 新开一轮真实实验（建议 12–16 次调用，`api_retries=1`、`api_connect_retries=1`），使用当前代码；
2. 若仍卡在规划：优先实现“**一次收集所有 gate 错误**”的反馈（预计 1 个提交，可离线回归），再重跑；
3. 规划通过后，重点观察 `pin_base_image` 与业务验收：第 36 轮已证明 Docker 与验收链路本身可用，剩余问题集中在“交付代码是否实现其文档承诺的拒绝行为”。

## 5. 复现

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m unittest discover -s tests -q                      # 540 OK (3 skipped)
python validation/deepseek-api/verify_prompt_contract.py     # 提示与校验器一致性
python validation/deepseek-api/verify_acceptance_prompt.py check
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
```

证据：`validation/deepseek-api/evidence/real-batch-run{8..39}-20261027/`（每轮 prompt/response/report/receipt，凭据形状命中 0）。
其中 `real-batch-run36` 含**首次成功 Docker 构建与业务验收报告**。
