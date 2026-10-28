# 第五阶段后专项：契约一致性、失败归因与自动修正

## 5fa25cb 后的两项真实验证补齐

本轮从干净的 `integration/contract-repair` / `5fa25cb` 开始，无后续提交或适用 AGENTS.md。
未修改 pipeline 程序、未重构、未开始 partner 同源对照。证据目录为
`validation/repair-completion/`；上一轮实验及失败产物保留。

**内容缺陷自动修复已完成真实验证。** 原 content-v2 只有运行快照，没有可供作者继续的
Native checkpoint，故在新隔离实验中把它的原缺陷包、正确测试和现有环境计划注入原
pipeline 首次候选位置，并复用已保存的 discovery plan。注入只制造失败起点；随后全部
使用实际主流程，没有模拟模型回答、Docker 回执或入库。运行
`20261026T114306-6e7aa6ab` 实际经历：Docker 10 项中 5 项失败 → 真实模型来源诊断
确认 content（无契约改动提案）→ 1 次真实作者调用 → 1 次独立审阅 → 10/10 全量通过
→ catalog accepted。作者与审阅使用不同会话，未重新发现。

只有 `scripts/base_count.py` 的 `sequence.count(base) + 1` 被作者模型修复为原来源的
`sequence.count(base)`；SKILL.md/支持文件未变。完整 acceptance 指纹修复前后均为
`8d1d0b92dd447452650f701f9785e343c771154b4a3e991f43776fad07d26c95`，锁定 cases、policy、
输入、负例和范围不变。正式修订
`rev-fa53420636aaa25df7fa2fb9d98c46cb2f2b85609bad06ed79e0a80c2f547dce`，镜像
`sha256:d63ecd37a7138f30851cb8e2e8ad3dbd61a17ceaf08c8f8889247ca1746152c3`。
默认查询与安装已真实通过。这是明确的故障注入实验，不是自然发生的新创建成功，
也不是历史契约修正的替代证明。原 content-v2 候选没有被修改或晋升。

正常 DNA 的本轮运行恢复结果记录在 `validation/repair-completion/normal-resume.log`
与 `summary.json`；恢复前来源、交付与作者检查指纹已单独保存，未人工提供环境计划。
**本项仍未完成。** 本轮通过原 runtime-prepare 发起一次真实规划，900 秒到限后返回
runtime_blocked，没有环境计划、镜像构建或业务验收。原始模型日志只有 thread.started /
turn.started 和一般启动警告，没有更具体的网络故障，不能据此断言本次也是此前 TLS 错误。
新阻塞修订为 `rev-1438d5997bfd4b3d5c7a70ec737948bbe9b9283bd97a865bd046fca865377dad`。
来源、交付文件和作者检查指纹均与本轮开始一致，未重新发现或编写；默认库查询隐藏，
安装被拒绝。该候选和本次超时输入/日志已持久保留，停止重复无进展调用，不以内容修复
成功替代正常创建成功，也未切换模型或流程来拼接成功结论。

| 本轮补齐项 | 结果 |
| --- | --- |
| 原新创建 DNA 的显式运行恢复 | 未完成：模型规划 900 秒超时，源码/来源/作者检查不变，候选保留且不放行 |
| 内容缺陷自动修复（明确故障注入） | 已完成：真实诊断、作者、独立审阅、10/10 Docker 重验及正式晋升；完整验收契约不变 |

可复现命令及实验依赖、全部人工干预边界见
`validation/repair-completion/README.md`。真实作者/审阅调用、源码 diff、锁定契约指纹、
失败与通过执行、当前镜像及晋升证据均已持久化。没有修改生产程序，因此沿用基线的
全量回归作为历史证据，不把旧测试数声称为本次新跑结果；本次以真实调用和执行核验为准。

以下保留 **5fa25cb 时的历史结论**，未将旧失败或当时未完成状态改写成成功。

基线 `3bd217227420e2dfa2e933e186c469b30e949ab7`，开始时工作区干净、无后续提交，
未发现适用 AGENTS.md。在现有独立集成工作区建立 `integration/contract-repair`，
没有回退、覆盖其他工作或修改原 Docker 工作区。没有新 CLI、第二套调度器、执行器或 catalog。

## 最终结论

**自动契约修正的持久恢复链路已真实验证；本次正常新创建未完成，不能宣布全部端到端验收完成。**

| 实验 | 最终事实 |
| --- | --- |
| A 新创建 | 真实发现/编写/独立审阅完成；600 秒与显式恢复 900 秒规划调用均超时，后者保留 WebSocket/TLS 中断记录。0 项业务执行，仍候选，默认隐藏、安装拒绝 |
| B 历史错误恢复 | 无人工提案，真实自动诊断/提案/独立批准，v2→v3；Docker 暂缺后显式恢复，13/13 通过，accepted |
| B 执行后补验（注入） | 实际 execution_failed/unknown 后自动来源诊断与批准，v3→v4，13/13 通过，accepted |
| C 环境（注入） | 实际 build_failed，真实模型只修环境，10/10 通过；源码与锁定 acceptance 不变 |
| C 内容（注入） | 10 项真实执行中 5 项失败，真实模型确认内容缺陷；正确契约未改，仍候选。未完成真实作者修复成功循环 |

最后一次程序修改后：Windows 全量 **215 项，213 通过、2 项平台跳过**；Linux 补验
**15 项通过**，包含 Windows 跳过的 POSIX 项。随后/同期以最终代码重新真实执行 B、
B 注入与 C 环境的全部 13/13/10 项检查，核对当前镜像、旧失败引用和 catalog 资格。
模型诊断/批准的原始审计保留；最后补齐的 production 无限 deadline 与审阅预算接线有
机制回归，未把它表述为另一次真实模型审阅实验。

## 复核事实与实现映射

直接核对了 stage5 的旧 freeze、原始 execution/report.json、源脚本、提案与独立审阅，
而非只采用报告结论。三个稀释用例的精确 stdout 是浮点 JSON，allowed_values 是整数。
源码的 argparse type=float、批量 float(...)、乘除和减法独立支持浮点输出；README 的
数学数值没有要求 JSON 整数。旧实际报告 execution_failed、repair_lane=content。

通道有一个关键差别：两个 scalar 用例的谓词读取 stdout，第三个 batch 用例读取
result.json。因此程序可直接证明前两个内部矛盾，不能跨文件/stdout 宣布第三个矛盾。
第三个错误需要来源语义诊断。原内容审阅在 runtime planner 之前，未审阅后生成的完整契约。

| 原入口 | 已有能力 / 实际缺口 | 最小改动与验证 |
| --- | --- | --- |
| acceptance.contracts / planner.validate_plan | 引用、结构、覆盖与锁；未检查联合可满足性 | 同调用同通道精确 stdout 与 JSON/JSONL 路径或精确文本比较；严格类型不变。锁定断言变更仍先拒绝 |
| execution.classification / validate | 原始容器观察；非环境业务失败直接归 content | 普通业务失败先 unknown，保留 observations 和诊断依据；确定环境错误仍回环境分支 |
| runtime.model_call | 已有隔离、无工具结构化模型调用 | diagnosis.py 只增加来源归因、受限差异数据及精确引用核验，不执行、不发布 |
| prepare_revision 的显式 oracle-correction | 来源引用、独立 reviewer、新版本、全量执行、adopt | 提取共享 approve_correction；自动路径同样调用，禁止绕过审阅 |
| pipeline 原 runtime 反馈循环 | 环境/内容分流及逐候选继续 | unknown/contract 接一次来源诊断；确认内容才回原作者/独立审阅；拒绝或未明停止该候选 |
| runtime-resume / runtime-prepare | 持久恢复、锁、镜像核验 | 复用自动诊断；仅运行阶段，不启动发现或作者。options-only prepare 只在需要诊断时走此分支 |
| store.adopt / history / commit | 统一资格、双区及事务 | 增加 runtime_diagnosis 持久引用与历史迁移，不另写晋升；来源确诊内容失败撤销内容资格 |
| planner.patch_plan / plan | 已有环境补丁协议 | remove 不解析无意义 value_json；具体指针错误反馈原规划循环，重复同错误停止；不擅自修指针 |
| planner.patch_plan（本轮更新） | JSON 文本字段只能整段替换；被拒草稿的修复连自身过度承诺也不能撤回 | 见下方「补丁协议更新」：嵌套指针、外部范围锚定、unknown 的诚实表达 |

正常 build 中尚未冻结的内部矛盾仍经原 propose 校验反馈修正；已冻结契约只能走
版本化独立审阅。新校验不是业务执行，也不证明任一断言符合来源。

## 补丁协议更新（仅离线改动，本轮 0 次真实模型调用）

1. **嵌套指针**：`/acceptance_json/<pointer>` 和 `/tests/<i>/case_json/<pointer>` 先解码该
   JSON 文本字段、在内部应用后续指针、再重新编码回文本。改一条 check、一个 selector
   或一个 fixture 断言不再需要重发整段文档。锁定计划仍整体禁止触碰 `/tests` 与
   `/acceptance_json`；一次补丁仍是全有或全无（失败不产生部分结果，输入计划不被就地修改）。
2. **撤回范围（带范围保护）**：锁定修复只能增长，不得删除已接受的用途/操作/用例；
   被拒绝草稿的修复可以撤回**该草稿自己**过度承诺的用例、用途、检查或 selector，
   但外部范围锚定不受影响：调用方提供的必需用例名（`required`）、已接受用例内容、
   上游 fixture 与配置/作者检查都不能被删除或改写，全量重写与补丁走同一检查。
   每次真实撤回写入 `planning/<n>/scope-delta-<k>.json`（含撤回项与被拒提案），
   缩范围可见、不静默。
3. **资源评估的诚实表达**：`status=unknown` 不再要求引用（那会逼模型编造证据），
   但必须在 `unresolved` 写明未定项；执行策略不变，`local.py` 的 `resources_unknown`
   仍阻止 Docker 执行。`status=complete` 仍要求读源精确引用。

这三项都只改变规划协议与报错表达，没有放宽任何验收门禁；补丁后仍要过完整
`PLAN_SCHEMA` 校验和原有 `validate_plan` 语义门禁。

## 非法输入：三态分类与"要求"和"已验证"分离（仅离线改动，0 次真实模型调用）

原来的 `invalid_input` 只有 `required`/`not_applicable` 两态，且只有全局一个值：
上游没写拒绝规则时，模型只能在"编造拒绝预期"和"声称不适用"之间二选一。现在：

| 状态 | 使用条件 | 验收义务 |
| --- | --- | --- |
| `required` | 用户、交付接口（wrapper 自己的错误分支也算）或来源明确规定 | 必须有具名 check 与**真实**拒绝用例并通过 |
| `none_documented` | 已检查材料与任何承诺都未给出契约 | 记录 `reason`/`scope`/`limitation`/`checked` 材料指纹/独立确认；作为 `validation_gaps` 报告 |
| `not_applicable` | 该操作没有调用者可提供的业务输入 | 仅需正常功能验证 |

判定按 operation 进行（无 operations 时按整个工具），策略级 `invalid_input` 取最强状态。

1. **判断依据不只上游源码**：`preparation.input_anchors` 从**已冻结**数据取锚点——
   作者/配置/审阅声明的拒绝检查（`expected_exit != 0`）、独立审阅过的执行要求引文、
   调用方 `requirements` 文本。命中即 `forbids_none_documented`，此时有调用者输入的操作
   只能是 `required`；`required` 的引用可以指向**交付的 entry 文件**，上游沉默不能豁免
   交付自己的承诺。
2. **`none_documented` 不要求伪造"证明不存在"的引文**：它不要求 `source_quote`，而是要求
   `checked:[{source_path, sha256}]`（逐个校验读取与指纹）、`scope`、`reason`、`limitation`
   和绑定到该材料集的独立确认 `review:{status, reviewer, materials_sha256}`；`context`
   引文只能作上下文，悬空或无关引文直接拒绝。`preparation.confirm_gaps` 还要求存在
   独立审阅产物，否则 `invalid_input_review_missing` 阻塞——普通创建路径拿不到该确认，
   所以它**不能**被用来把一个真实义务洗成"无契约"。
3. **"规定的检查已覆盖"与"业务要求已满足"分开**：`acceptance_coverage` 现在同时输出
   `coverage_complete`、`validation_gaps`、`blockers`；`complete = coverage_complete 且
   无 blockers`。`none_documented` 只免除"凭空编造负向预期"，会显示为验证缺口；用户/交付
   要求了却无法建立可验证契约时进入 `blockers` 并阻塞，不允许用缺口替代。
4. **修复轮不得随意降级**：锁定计划仍完全不能改 `acceptance_json`；被拒草稿的降级必须带上
   上述记录字段，否则 `patch_plan` 直接拒绝（"cannot downgrade … without recorded evidence"），
   真实降级写入 `scope-delta-*/input_states`，外部要求与已批准契约只能走正式变更流程。
5. **RECAP 案例**：历史已接受的计划是 `required`（引用交付 `entry/skill.py` 的
   `if len(sys.argv) > 2 or not smiles.strip():`，check `nonempty_text`，拒绝用例退出码 1），
   `verify_original_case check` 仍显示该计划在**未放宽**的门禁下通过。因此 RECAP 不靠新增
   `none_documented` 过关；没有用户输入的固定示例程序则可以正当声明 `not_applicable`，
   不必凭空承担不存在的输入接口。

6. **提示协议同步**：三态规则只有一处权威文本 `planner.INPUT_CONTRACT_SPEC`，同时渲染进
   POLICY 正文与 `acceptance_json` 的 schema description（DeepSeek 走 system prompt，Codex
   走 `--output-schema`），两者不可能各说各话；修复协议 `planner.patch_protocol()` 是生产
   与审计共用的真实函数。`validation/deepseek-api/verify_prompt_contract.py` 离线重建
   POLICY、补丁协议、两份 schema、**冻结的** `frozen/prompt-0.txt` 与 `frozen/schema.json`
   并核对：每个校验器要求的字段与状态都必须出现，旧的"两态/整段替换"表述必须消失，
   修复反馈必须点名缺失证据。`tests/pipeline/test_prompt_contract.py` 把同一审计接入测试套件，
   规则与提示一旦脱节即失败。

## 自动修正边界

提案绑定原修订、acceptance/source 指纹、逐用例旧值/新值、来源路径与精确引文，
解释为何不能改源码及哪些范围不变。模型只能返回数据，不能编辑包、catalog 或历史。
自动编辑仅限既有用例的预期字段；保持调用、输入、负例、用途、覆盖、断言种类、容差
和 allowed_values 数量。不同来源的整数结果不统一转浮点。

独立 Native reviewer 与提案者是不同会话，必须同时确认内容、执行需求及
oracle_changes_verified。批准后复用 prepare/rebind/seal/execute_prepared/adopt，
重新执行所有适用锁定测试，不仅失败项。模型提案、独立审阅的完整审计随新材料冻结；
诊断副本、原始失败和 catalog history 持久保存。

来源不足、拒绝、未明、同输入重复诊断均停止且不晋升。production 无新增总体次数配额；
保留单次超时、显式上下文/时间限制和主流程调用预算。普通断言失败不表示源码已错；
review_required 的 CLI 退出码为 1，不能被 shell 当作验收成功。

## 实验记录（最终数值见 validation/contract-repair/summary.json）

### A：新的正常创建

`normal-input.json` 指向原始 base-count 源码与固定说明，不是预制 Skill。
从新运行目录 `20261026T104258-6f22d453` 经正常 CLI、真实模型发现、编写与独立审阅。
首次 runtime planner 600 秒超时，原始 blocked 输出保存在 normal-initial-output。
之后同一候选通过 options-only runtime-prepare 明确恢复，单次超时 900 秒。
没有人工改生成的 Skill、检查或环境计划，不重新发现/编写。
恢复调用也在 900 秒超时。其保留的 stderr/stdout 记录 WebSocket idle timeout、TLS
peer closed connection 与模型列表刷新超时；没有返回环境计划。停止无进展重试，候选
仍 runtime_blocked，未构建/执行/晋升。默认查询不可见、安装拒绝。**本次正常完整创建
未完成**，不以 stage5 的 DNA 成功、其他历史恢复或故障注入代替。

### B：原历史错误契约自动修正

`history-library` 从 stage5 原始失败输出 runtime-import；不继承旧执行资格。
未传人工修正提案，真实模型自主依据源代码发现并提出三处严格类型修正；独立模型批准。
首次独立审阅因 Windows 长路径失败，保留 history-auto.log 与完整提案；缩短诊断目录后
继续同一候选。新版本形成后发现本机 Docker Desktop 未启动，准确记录 runtime_blocked。
启动已安装的 Docker 后 runtime-resume，仅运行阶段完成全部 **13 项真实验收**并入正式区。
旧文件/来源不变；旧契约、失败记录与新版本均可从 catalog 历史定位。

一致性预检在来源诊断输入中识别两个 scalar 冲突，故 B 本身不证明新的执行后归因路径。
首次长路径失败后的再诊断因目录缩短和证据入口修复没有携带旧 observations；来源文本
仍足以独立推出修正，原始失败保存在历史。后续实现从 history 中恢复原观察引用。

### B 的执行后补验：明确的契约故障注入

`inject_fault.py post-contract` 从原失败快照建立新修订，只在实验输入中把精确 stdout
换成字段出现检查，保留三个错误 typed 谓词，使它内部可满足但仍与来源不符。
这是人工构造的错误起点，绝不是自动修复时放松断言。原快照未改。
真实 Docker 全部执行后失败、lane=unknown；随后正常 runtime-resume 真实模型诊断、
自动提案、独立批准、全量 **13 项重验通过**并晋升。自动修正严格保持注入后锁定的
调用/负例/范围及其他断言，没有重新加入或删改断言来制造通过。

### C：真实内容与环境故障注入

- `content-v2-library`：交付脚本计数故意加 1，原始来源和正确数值断言不变。
  首次内容注入因引用被修改行而被来源核验拦住，content-injection.log 保留；第二个
  新副本把引文指向未变原始来源。真实 Docker 业务失败后，真实模型确认交付内容缺陷，
  返回 author_repair_and_independent_review，没有生成契约改动或晋升。重复恢复不再调用模型。
  **未宣称完成真实作者修复闭环**；主流程作者/再次审阅接线由故障注入机制测试覆盖。
- `environment-library`：加入明确标注的 RUN exit 37，真实构建失败。首次真实规划返回
  无效 JSON Pointer，记录 runtime_blocked，没有改源码/断言或放行。
  补齐现有补丁解析反馈后，在 `environment-v2-library` 新注入副本真实模型只移除失败步骤，
  真实 Docker 构建及 **10 项业务验收通过**。文件、来源与锁定 acceptance 指纹不变。

这些都标作故障注入，不是自然发生的端到端成功。模型日志中的 report acceptance_version=2
是执行器协议版本，不是 delivery.inputs.acceptance.version；不能混淆两者。

## 验证与未覆盖范围

新增机制测试覆盖严格类型矛盾、JSONL 记录索引、不同通道/调用、不改整数协议、
受限提案/负例/扩容拒绝、无来源拒绝、未知停止、同输入不重试、独立拒绝不执行、
显式预算、补丁错误反馈及停滞、诊断历史迁移、review_required 非成功退出码。
production 无限 deadline 单独回归，独立审阅每次调用计入主流程显式预算，并继承剩余
时间；没有把无限预算转成整数或增加隐含整体配额。
原镜像/输入漂移、当前资格、锁定断言、资源受阻、事务回滚、候选隔离与 partial 保障保留。
最终 Windows 全量回归与 Linux POSIX/事务补验日志分别记录，不把单测当作真实业务验收。

未完成：本次正常新创建因模型连接中断而未完成运行阶段。未覆盖：真实内容缺陷经作者修改、再次独立审阅再通过的完整自动循环；自然发生的
多候选模型自动修复批次；所有可能的跨断言逻辑冲突。检查仅覆盖所述同通道精确值，
不进行通用约束求解、不推断文件与 stdout 相等，也不替代来源和科学正确性审阅。
同机跨路径与 ZIP 沿用阶段四已验证边界；第二台物理主机未实测。
远程 GPU、外部资源挂载、凭据传递、外部服务继续明确阻塞。未安装宿主依赖，未推送发布。

## 复现

在仓库根目录运行，选择新的目录名以保留原证据：

```sh
python -m creation_pipeline build examples/base-count/input.json --state-dir .pipeline/new-run --library-dir validation/new-library --keep-debug
python -m creation_pipeline runtime-import validation/stage5/interrupted-third-output validation/new-history --candidate ideal-dilution-calculator
python -m creation_pipeline runtime-prepare validation/new-history --candidate ideal-dilution-calculator --spec validation/contract-repair/auto-spec.json
python -m creation_pipeline runtime-resume validation/new-history --candidate ideal-dilution-calculator
python -m creation_pipeline library validation/new-history
python -m creation_pipeline runtime-inspect validation/new-history --candidate ideal-dilution-calculator
```

只有 Docker 暂缺、仍待运行时需要后面的 resume；正常通过不重复运行。
不传 `--oracle-correction` 或旧修好计划。明确的人工修正入口仍可用，但不作为自动验证证据。
故障脚本支持第二个参数作为全新实验标签，例如 `inject_fault.py environment another-env`；
必须显式标注故障注入，不能覆盖既有目录。所有日志、干预和汇总都在 validation/contract-repair。

本次实际命令与人工干预清单为 `validation/contract-repair/commands.json`。保留的 A 候选在
模型服务恢复后可直接执行下列命令，无须重新发现/编写；若仍失败须继续保存阻塞：

```sh
python -m creation_pipeline runtime-prepare validation/contract-repair/normal-library --candidate dna-base-counting-cli --spec validation/contract-repair/auto-spec.json
python -m creation_pipeline install validation/contract-repair/history-library --name ideal-dilution-calculator --destination ./new-install
python validation/contract-repair/verify_experiments.py
```
