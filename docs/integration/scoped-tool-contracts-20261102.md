# 分离工具兼容要求与当前 Skill 合同：实测

基线 be73aff；本轮保留 Codex 原生发现/编写/独立审阅及 Codex 结构化运行时。
每批仍为 16 admitted stages，每次 600 秒、总 3600 秒、准备 2400 秒；不提高预算，不 push。
新代码与真实配对启动前保存的全部 production .py 摘要完全一致，最终回归测试同一实现。

## 实现与保守边界

原请求将整段 runtime requirements/constraints 放入工具键，流水线还默认复制 prompt；当前
Skill 文案、业务期望与环境兼容因此混合。全部来源字节原本也进入闭包，不能假设 README 无关。

新增显式 v5/request_protocol=2，要求配置同时声明版本化 tool_compatibility 和 skill_contract。
兼容字段覆盖 base/language/version、依赖文件/命令、计划 ENV，继续连同原声明的接口、依赖、
平台、资源能力、闭包和 memory/cpus/pids 参与请求。计划逐字段核验，并观察实际 Python/依赖
版本及原有完整镜像身份/字节；模型不能通过重分类提高命中。

当前业务 requirements/constraints 与原 prompt/notes/constraints/checks 单独冻结于
acceptance.payload.skill_contract；兼容封套位于 environment.payload.tool_compatibility。
两者均有 schema version 与独立 sha256，仍由原 revision/freeze/RuntimeRequest 指纹保护。
当前必需路径、原生用例映射、独立审阅、覆盖、来源与资格门禁全部保留。

未分类旧式 requirements/constraints 仍保守进入 unclassified；顶层未知 constraints 保留完整
对象和值。来源策略只支持完整快照，除 package/SKILL.md 外不自动排除文件：源码、依赖、数据、
README/例子等变化仍 miss。新模式明确 prompt 是当前 Skill 指导；不提供任意自由文本的语义
分类或任意上游业务文档排除。未知字段/版本/策略具名拒绝。完整协议见
[作用域、来源与迁移](../pipeline/scoped-tool-contracts.md)。

旧配置未提供作用域时，保持旧请求字段和身份；旧 v1/v2/v3/v4 记录不改写。新作用域只支持已有
Python v1/v3/v4 实现，保留 implementation_abi；Open Babel 新作用域暂拒绝，原 v2 路径继续支持。
没有远端平台、OCI、依赖自动合并、结果缓存或 GC。

## 普通 CLI 真实配对

证据根 `E:/Users/27343/Docker/scoped-contract-cli-20261102-01`。
配置为 `validation/scoped-contracts/skill-a.json`、`skill-b.json`，沿用此前真实 sibling-json/source。
原脚本、JSON、requirements 与来源均未改。两个配置都没有 plan/acceptance_plan/tool_artifact，
也没有旧 runtime requirements/constraints：不是再次手工填相同旧字符串来制造命中。
仅共享同一新工具和环境登记目录；Docker/BuildKit 的既有镜像和缓存完整保留。

实际公开入口为：

```powershell
python -m creation_pipeline build validation/scoped-contracts/skill-a.json --state-dir E:/Users/27343/Docker/scoped-contract-cli-20261102-01/a/state --library-dir E:/Users/27343/Docker/scoped-contract-cli-20261102-01/a/library --keep-debug
python -m creation_pipeline build validation/scoped-contracts/skill-b.json --state-dir E:/Users/27343/Docker/scoped-contract-cli-20261102-01/b/state --library-dir E:/Users/27343/Docker/scoped-contract-cli-20261102-01/b/library --keep-debug
```

外层 record_public_cli.py 只留存子进程输出/耗时，不构造内部状态或旧资格。代理仅随命令设置
7897；原 .env 不复制到证据。日志和证据使用现有 redact/sanitized/write_json。

| 观察 | A 操作者 Skill | B 数据整理 Skill |
| --- | ---: | ---: |
| 独立发现/编写/审阅 admitted calls | 3 | 3 |
| 组合环境/验收规划 calls | 2 | **0** |
| 当前验收专用 calls | 0 | 2 |
| 全部 admitted calls | 5 | 5 |
| 环境 / 工具 build | 1 / 1 | **0 / 0** |
| 模型编制用例 / 原生映射用例 | 9 / 8 | 6 / 11 |
| 当前独立 Docker 用例 | **17/17** | **17/17** |
| 当前资格 | accepted | accepted |

共两个真实生成批次、34/34；不能声称全部模型调用为 0。A 的组合调用同时计入环境/验收两个
观察计数，各为 2，但实际是两次，不能相加为四次。B 仅使用当前验收专用阶段。
两份业务 requirements、constraints、prompt、文案、revision、实际锁定 cases 指纹、验收指纹、
作者/独立审阅会话与 attempt 均不同；兼容封套和实际工具版本完全相同。

- request_key：`4ff3ae1999af786661fa80842819e9e46e6f54d1d779d5ad01c3111dd51cbfe3`
- artifact_id：`7030f8641c7aaecd8b100e296cf2c1d4dd6b27f8249588985dbde8302ba22f9a`
- 本机 image ID：`sha256:89bca2b1356312efc59ba318d15e6914ac16e19031391981acae01cfab49aa49`
- 相同兼容 sha256：`71ec40807a806596c19713103246b6be62d77362b0b01ad8e56f2561fc574075`
- A 业务 sha256：`0ee1ebc05e9420d3c1b7bdb900becccf315f59827b20e95298f13f7e68d88acd`
- B 业务 sha256：`a3637aa07d3d83f3f9d47d5f1380b3b7a8bea5c94c3450a220ae4daba715ed62`

工具记录不含当前 skill_contract、当前 cases 或 passed。audit-a、audit-ab 保留完整观察，
逐条复核 ethanol/phenol、非法/空输入的实际入口输出和 exit；当前业务检查不是由模型声明代替。

## 负例、拒绝与恢复

隔离 request 副本：源码、JSON（更新声明摘要）、依赖、接口均自动 miss，显式旧版本
selected_request_mismatch，保留字段、路径、期望与实际。另用普通 CLI 显式选择旧版本验证
11 类变更：上述四类、平台、资源能力、base image、未知字段、未分类旧要求、来源文档、未知
caller constraint，全部在模型前阻止，0 模型/实际 build，不创建 state/library；原库和 registry
全文件 manifest 不变。这里是无模型负例，不冒充额外生成批次。

`delivery-cli` 通过公开入口验证新封套：导入后不合格；用 runtime-prepare 更换业务作用域报
skill_contract_change_requires_review，失败库仍不合格且不重跑。另一干净库从安装 envelope 导入，
新 attempt 实际执行原锁定合同 **17/17** 才恢复资格；0 模型/实际 build，旧绑定/registry 不变。
这是交付重验，单独计数，不加进 34 条真实生成结果。历史 receipt 的 1/1 不冒充本次构建。

runtime-only 修复保留原两份作用域、未分类要求和 caller snapshot；不能静默降级旧模式。
旧修订直接升级新作用域报 scope_migration_requires_new_skill，需新 Skill 编写/独立审阅。
新 Skill 的新合同仍通过普通生成入口完成。oracle 修正保留原有诊断与独立审阅要求。

保留的失败：A 首次组合提案缺少 smiles-flag 的实际非法输入拒绝；B 首次验收提案把脚本单独
当 entrypoint，错误逐用例给出 received 与 expected `[python, absolute-script]`。两份原 rejection、
prompt/schema、响应和后续结果保留；在原预算内校验新提案，不删除或弱化失败用例。
另以 proposal-retention-20261102.json 只读比对：两份原提案的所有用例名均保留，所有非调用字段
及断言完全不变；A 从 8 个模型用例增加到 9 个，B 的 6 个用例仅修正解释器/脚本调用形式。
没有失败 Docker 批次的 resume/restart。离线首轮仅有两处新夹具错误（错误布局措辞、不完整
HOST gap），按原语法/结构修正夹具，未放宽生产校验；记录于独立 offline 目录。

## 旧协议与最终回归

`scoped-contract-legacy-audit-20261102-01` 用最终代码重算旧 v4 A/B 的完整请求：与旧 frozen
request/request_key 完全一致；公开 runtime-inspect 当前资格均通过，0 模型/build，原库字节不变。
旧自包含 Open Babel 在 `legacy-delivery-cli-20261102-02` 走公开 CLI 安装/导入/迁移，两个新
attempt **16/16**，0 模型/build，原库不变。均为既有合同重验，未继承旧执行资格。

最终日志 `E:/Users/27343/Docker/scoped-contract-regression-20261102-02`：
**786 项，783 通过、3 跳过**；针对性 **64/64**；三个提示自检、平台契约核验通过。
未修改提示/schema，无需 freeze。平台机器清单还从实际 validate_record AST 核对 request v2
字段集合，区分 ABI、请求、作用域、delivery 和 RuntimeRequest 的独立版本域。

本轮证明精确匹配不再受显式业务要求/当前文案/用例的无关变化影响，同时保留保守来源与未知
要求身份；不外推任意来源文档、自由文本语义分类或跨平台兼容。模型回执是 admitted calls，
不等同供应商全部网络请求或已知费用。缓存保留，build 调用数也不等同实际安装次数。
机器索引见 `validation/scoped-contracts/results-20261102.json`，含可追溯证据和 SHA256 manifest。
