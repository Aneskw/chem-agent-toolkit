# v3 交付、零模型就绪及 v4 同目录 JSON 验证

基线按用户确认保留 a7ed138，继续使用 Codex。发现/编写/独立审阅和结构化运行时均沿用原配置：
gpt-6-astra；每批 16 admitted stages，每次 600 秒、总 3600 秒、准备 2400 秒；未提高预算、
未切换后端、未 push。模型 receipt 统计 admitted calls，不冒充所有网络请求或已知费用。

## 按顺序完成

1. v3 已有真实 A/B 通过公开 CLI 安装、envelope/原生输出导入、迁移、恢复和新资格检查：
   **192/192、12 个独立 attempt**，0 新模型/实际 build。导入、迁移先不合格，实际新执行后才合格。
   数据/绑定漂移、镜像缺失观察明确阻止；原绑定不变。详见 [v3 交付报告](v3-delivery-cli-20261102.md)。
2. 新增 `readiness CONFIG` 与普通 build 的模型前门禁。最终公开 CLI 11 场景均通过，0 模型、
   0 build：缺来源、Docker、资源摘要、指定制品或已知不支持源码时拒绝；离线/草稿保留 deferred。
   配置错误也有 object/path/expected/actual；草稿不要求尚未使用的运行时 provider 可用。
3. 真实样例核对后，仅扩展 **固定 with_name 同目录 UTF-8 JSON 读取**，独立 v4 ABI/policy。
   不是重复计算原有多模块/数据哈希能力，亦不支持引用样例整体的外部模型 checkout/subprocess。
   [协议与迁移](../pipeline/sibling-json-tool-protocol.md)、[预检边界](../pipeline/readiness.md)、
   [平台契约](../pipeline/skillnet-local-adapter-contract.md) 和机器清单均已交叉核验。

## 真实普通 CLI 配对

证据根 `E:/Users/27343/Docker/sibling-json-cli-20261102-01`。配置为
`validation/sibling-json/skill-a.json`、`skill-b.json`；仅文案面向不同操作者，共同运行要求相同。
新样例位于独立 source，原 calc_descriptors.py、requirements.txt、JSON 原字节相同，
只创建新 screen.py 包装入口；`provenance.json` 保留原路径、摘要和结构参考范围。

两次实际命令分别为：

```powershell
python -m creation_pipeline build validation/sibling-json/skill-a.json --state-dir E:/Users/27343/Docker/sibling-json-cli-20261102-01/a/state --library-dir E:/Users/27343/Docker/sibling-json-cli-20261102-01/a/library --keep-debug
python -m creation_pipeline build validation/sibling-json/skill-b.json --state-dir E:/Users/27343/Docker/sibling-json-cli-20261102-01/b/state --library-dir E:/Users/27343/Docker/sibling-json-cli-20261102-01/b/library --keep-debug
```

仅为留证在外层使用 record_public_cli.py；没有内部状态注入、手工 plan/acceptance_plan/tool_artifact、
旧 passed 拷贝或手工资格。两个子进程共享新 CHEM_AGENT_SHARED_TOOLS 与 CHEM_AGENT_SHARED_ENVIRONMENTS
目录，HTTP(S) 代理仅随命令临时设置 7897。所有原 Docker/BuildKit 镜像和缓存保留。

| 观察 | A 首次 | B 不同文案 |
| --- | ---: | ---: |
| 独立发现/编写/审阅 admitted calls | 3 | 3 |
| 组合环境与验收规划 calls | 1 | 0 |
| 当前验收专用 calls | 0 | 2 |
| 全部 admitted calls | 4 | 5 |
| 环境 build / 工具 build | 1 / 1 | **0 / 0** |
| 当前独立用例 | 13/13 | 14/14 |
| 当前资格 | accepted | accepted |

A 的组合 planner 同时编制验收，故 environment_planning_calls 与 acceptance_planning_calls 各为 1，
不能相加算两次。B 的 environment_planning_calls=0、acceptance_planning_calls=2。
第一次验收提案省略解释器，只把脚本当 entrypoint；确定性检查按具体用例指出 received 脚本、
expected `[python, absolute-script]`，在原预算内重新编制后通过。原 rejection.json、响应、反馈、
prompt/schema 摘要均保留，没有手工改方案或删除用例。这是内部提案校验，非失败 Docker 批次续跑。

两个 Skill 的文案摘要、revision、作者/审阅会话、验收指纹和 attempt 不同；同一具体版本：

- request_key：`e2ac53361b5bc6644fe542ff1c0d4c32b6d6580b28c736427596d515fc01bed2`
- artifact_id：`5b8c4de1cd5ba3beadb95279acb41a2266c812b1c6de92577537514a1cf2edd8`
- 本机 image ID：`sha256:7883e23ce781eb00adb9bb149d28fcc120b36837222b5f7cd6a40617f61f0985`

audit-a、audit-ab、final-audit-ab 核验当前资格、独立会话、真实入口输出、锁定合同和来源。
两类构建计数还与 build-log 实际命令交叉核验；32/36 个原生 command_execution 事件中各无 Docker
build，观测范围另存 native-build-audit.json。资格不是由 registry 可用或模型声明代替。

## 变更、失败和旧模式

四类隔离副本分别修改模块、JSON（同步新摘要）、依赖版本、接口：
精确解析 auto miss；选择旧具体版本均 selected_request_mismatch，保留字段/路径/expected/actual。
另经普通 CLI 显式旧版本分别验证，全部在模型前拒绝，不创建 state/library；0 模型、0 build。
旧 A 库和 registry 全文件 manifest 不变，随后两份当前资格均通过。
这是独立无模型负例，不冒充四个新模型生成批次。

辅助审计有两次错误，分别误读 sessions.json，以及只识别镜像默认入口而漏认实际已通过的
显式 Python 入口。两个 helper_failed 记录保留；修正后只读重审同一既有结果，没有重新执行业务。
原 A 实际 13/13，早期进度误报 16 已更正；不为保持旧数字增加或删除用例。
v3 交付前两轮辅助状态枚举错误及额外 32 条成功重验单列于其报告，不计入 192 完成矩阵。

旧自包含 Open Babel 另在 `legacy-delivery-cli-20261102-01` 走公开 CLI 安装/导入/迁移，
两次新执行 **16/16**，0 模型、0 build，原库字节不变。最终代码对原 a7 v3 A/B 的普通
runtime-inspect 仍均合格，保留在最终 postflight 的 original-v3-current.json。

真实生成完成后还补强了未执行 provider 的预检边界、坏配置结构化错误、__file__ import/async
重绑定拒绝；原始生成实现与最终实现摘要分别保留。最终代码重新做完整回归和两份 v4 当前
冻结/绑定/资格核验，无合同变更、旧资格继承或额外生成批次。

## 耗时与存储观测

measurements.json 保留阶段和逐用例时间、模型回执、build 命令缓存证据和存储原始路径。

| 秒 | A | B |
| --- | ---: | ---: |
| 普通 CLI 总耗时 | 588.18 | 679.56 |
| 构建或绑定（含身份核验） | 8.83 | 3.07 |
| 验收阶段（含检查） | 18.30 | 22.30 |
| 直接 --smiles 调用用例 wall time 合计 | 9.89 | 9.99 |

**不能据此声称端到端加速**：单次顺序样本、模型调用次数/时延和当前合同规模不同。
直接入口时间含默认/显式 Python 形式，不推断不透明 inline wrapper 的内部化学时间。
8.83/3.07 含身份检查，未单独 instrument build 子进程 wall time；原 BuildKit step 时间完整保留。
A 环境 pip RUN 明确 CACHED，1 次 build 不等于实际执行了 1 次安装。

B 前后 Engine /system/df：image layer bytes 增量 0，无新/删除 image ID；build cache record/bytes
增量 0。Docker Desktop 数据文件系统 `df -B1` used bytes 增量 0。这些是本次整 daemon/文件系统
观测，不是 Windows VHD 物理分配或可因果归因的单工具占用。A 前仅有 docker system df -v 人类
可读快照，不能补造精确物理/字节增量。

同一镜像 virtual Size=497478522、SharedSize=497309704，差值 168818 字节只是 Engine 的逻辑
unique 口径；不相加镜像虚拟大小、不叠加 image/cache。冻结目录逻辑大小 A=347257、B=545854，
另列而非镜像真实磁盘占用。早期三路径固定合同对照仍单列在原报告，本次没有冒充第三路径测量。

## 最终检查与边界

最终 postflight：`E:/Users/27343/Docker/tool-v4-postflight-20261102-01`，
**774 项：771 通过、3 跳过**；三个提示自检和平台契约检查通过。提示/schema 未改，未盲目 freeze。
针对性测试 63/63。初次 755 项回归中旧缺来源 helper 依赖 output 字段，在更早阻止后报错；
已加强为断言模型/会话/state 均未启动，原拒绝要求保留，初始失败日志未覆盖。

本轮支持同 daemon 的具体完整镜像、有限固定 JSON 读取及本地冻结交付；预检只观察已知条件。
一般 Path 变量、默认编码、动态加载、外部资源、任意 subprocess、引用模型工具整体、OCI/远端
分发、平台服务和 GC 均未增加。镜像缺失只明确阻止，跨主机重建不透明替换具体版本。
v3 缺镜像实验为精确 inspect 边界注入，并未删除现有镜像。全部失败证据和旧模式资格门禁保留。

机器索引 `validation/sibling-json/results-20261102.json` 链接本轮证据摘要与全文件 SHA256 manifest。
