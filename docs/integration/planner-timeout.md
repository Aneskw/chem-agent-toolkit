# RECAP 新创建实验 B 的 planner 超时专项

基线 `92e5388`，开始时 `integration/markdown-entry` 干净、没有后续提交，未发现适用 AGENTS.md。工作分支 `integration/planner-timeout`。没有修改 partner、DNA、原始验证档案、正确业务源码或作者检查；没有安装宿主依赖。

## 已查明事实与尚未证明的解释

旧证据仍在 `validation/markdown-entry/`。只读对照程序和结果为 `validation/planner-timeout/inspect_baseline.py`、`baseline.json`。

- A 首次完整规划 prompt 为 44,344 字节，B 为 45,609 字节；实际来源材料分别 32,088 与 33,667 字符。两边均包含实际 Markdown、提取入口、来源与许可证，不支持“B 输入明显超过 A 的规模”这一解释。
- A 首次规划 71.787 秒返回，回执为 58,786 输入 token、2,822 输出 token。B 历史记录只有 thread.started、turn.started，无方案、完成事件或 usage；600 秒后 `subprocess.run` 抛出 TimeoutExpired。记录不能证明服务端收到/完成了全部模型请求，也不能据此断言网络故障。
- 两边原 tool-free caller 都继承用户配置；显式模型均为 gpt-6-astra。已保存配置观测为 low reasoning effort。本次保留 model/provider/effort/service-tier/auth 的继承方式，未改模型、未调高超时。
- Native 内容/独立审阅调用有 `--ignore-user-config` 和工具能力限制；原 planner caller 只有提示词“不要调用工具”，仍允许 CLI 发现宿主 skills/plugins/MCP/hooks。A 的高输入 token 说明显式 prompt 不是完整上下文，但不能把差额全部归于某个插件或准确计算隐含上下文长度。
- 历史 B 的 stderr 有插件图标和 PowerShell snapshot 告警。A 成功不能排除偶发服务或传输问题；B 超时也不能证明化学任务本身无法规划。

诊断假设：去除无工具调用不需要的宿主集成，减少上下文/启动干扰，并记录生命周期。判定标准：同一 B 候选、不更换来源、不提供人工计划、同一模型和 600 秒限制，经原 runtime-prepare 获得方案并完成原有校验；失败则按明确新证据分流，不重复无变化调用。即使成功，也不是历史超时唯一根因的受控证明。

## 最小修改

仅修改原 `creation_pipeline/runtime/model_call.py`，调用签名、planner、修复调度、执行器及 catalog 不变。

- 对无工具结构化调用禁用宿主 skill 发现、apps/plugins、MCP、shell、multi-agent、hooks 和 legacy notify；禁用 web search、审批交互。保留用户模型/提供商/认证/推理配置，未改用户配置文件。
- MCP 名称使用 CLI 支持的普通点路径覆盖；含非字母数字/下划线/连字符的名称明确阻塞，避免错误覆盖或默默保留可用工具。
- 保存脱敏的 request/schema、PID、启动时刻、stdin 完成时刻、事件类型与耗时、stdout/stderr、退出码和超时位置。事件摘要不保存私有推理内容。不保存进程环境或凭据。
- 原 subprocess.run 改为原调用内的 Popen 流式记录；复用现有 terminate_tree，超时时终止进程树并回收管道，保留单次超时，不新增隐含整体配额。
- 仍拒绝实际工具事件及异常回答，不通过忽略错误、删除断言或放宽验收获得成功。

官方 [非交互模式说明](https://learn.chatgpt.com/docs/non-interactive-mode)用于核对 JSONL 事件和 schema 接口；具体配置兼容性以本机 CLI 和下面的实际调用记录为准。

## 诊断干预记录

所有命令均为同一已有入口：

```powershell
python -m creation_pipeline runtime-prepare E:/Users/27343/Docker/me-b --candidate rdkit-recap-terminal-fragments --spec validation/markdown-entry/auto-spec.json
```

1. `recovery.log`：第一次配置隔离试验在模型发出请求前失败。带引号的 MCP 点路径被 CLI 当作不同的键，缺少 transport。已保存子进程 exit=1；改为普通键路径后继续。这是本次诊断引入的兼容问题，不是旧超时根因。
2. `recovery-2.log`：关联模型约 32 秒返回答案，但出现启动告警 item.error，被原工具事件检查拒绝。stderr 另有 legacy_notify 的 Windows 命令过长错误，说明仅禁用 hooks 不足以禁用旧式通知。明确加 `notify=[]`，不更改宿主设置。
3. `recovery-3.log`：约 35 秒返回答案，但同一启动告警仍触发拒绝。直接检查 stdout 证实告警是启用 skip_host_skill_discovery 的实验功能提示，**不是 legacy_notify，也不是业务错误**。stderr 另有模型列表刷新超时，但本次实际模型回答已经成功返回。按 CLI 指示设置 suppress_unstable_features_warning=true，未豁免真实错误或实际工具使用。
4. `recovery-4.log`：在上述有具体依据的修正后，继续原入口；最终结果见下方恢复证据。前三次都尚未进入 planner，不能计为“三次规划成功/失败”。

每次准备产生的候选修订及证据保留在原库历史。此前评论中曾将拒绝事件与 notify 错误关联；直接核对 stdout 后已更正，不能沿用该错误因果解释。

## 真实恢复结果

**新创建实验的显式恢复完成。** 原 `runtime-prepare` 已完成来源关联、独立审阅、真实模型规划、Docker 构建、11/11 业务/环境/上游检查和原 catalog 事务晋升。

- 起始修订：`rev-2b405edc86958b3d155a650495c5985fca33bf561c90978f5a664fb545336a3d`。
- 正式修订：`rev-6f7bc04409c4055c6b7d37b52276e3609a741cd97f3fe38cb88b5691d3ee19a9`。
- 镜像：`sha256:a617ef6e1ba01ecc79e3d75a7a1ed598822f3582ffbdd53e0ddcf590d781dd48`。
- 实测 Python 3.11.17、RDKit 2024.09.6。RDKit pin 是模型明确标为 inferred 的环境选择，不宣称该 wheel 就是上游固定提交构建；固定来源原测试和实际交付的适用行为在此镜像通过。
- 首次完整规划：公开完成事件 113.905 秒，完整调用回执 115.296 秒，54,927 输入 token、3,298 输出 token。后续四次模型 patch 为 34.639、20.807、17.972、21.053 秒，无工具事件。
- 初始未冻结提案的三个 Markdown 探针有换行转义错误，随后一次 patch 把 case_json 写成对象而非字符串。既有校验器给出具体失败位置，既有 planner 自行修正；没有人工提供修正数值、脚本、计划或 Dockerfile。这些是**执行前的新方案结构修正**，不是冻结契约或执行后自动修复的新证明。
- 全量锁定测试包括环境版本/反应初始化、实际提取入口终端片段、实际入口合法空结果、实际入口空白参数拒绝、固定上游原始 unittest、三个文档行为探针、原作者三个检查。全部通过；空白参数用例按契约退出 1，而非伪装为成功业务返回。
- 默认库查询、显式访问和安装均返回 0，默认查询只返回该 accepted 项，实际安装内容已保存。

源码、来源和作者检查逐项相等，恢复调用记录无 discovery/author，独立 review 一次。`collect.py` 直接核验冻结包与全部历史，而非只比较文档描述：

| 身份 | 恢复前后相同的 SHA-256 |
|---|---|
| 交付文件清单 | `885de0e5f8646fa30fde035ec78d46a3bd1a8a6ef2e948fe92f9e8565f6a0ffa` |
| 来源身份与清单 | `fcf3caddc80c62c81d9ff6ab8e8c38d08fb129222432f733587fed143d32d5e4` |
| 作者检查 | `866b67dfe78ebdfa1c6ad014c479806b4888535243fc9beef52dd85cdca5a058` |
| 原样 Markdown Python 块 | `0dae36e3478d6800028515d325c95124eb66106115cefc70c87f98a62fc3ef91` |

执行契约从只有作者检查的 version 1 扩展为完整环境计划、锁定业务测试及不变作者检查的 version 2；环境/绑定/契约产生新身份，未沿用旧资格。旧超时、三次诊断阻塞及对应修订仍可从 catalog.history 和完整 evidence 找到。

### 超时根因结论的限度

已证实并修复无工具调用加载无关宿主能力、旧式通知仍执行、缺少流式观测和完整进程树清理的问题。本机启动告警的兼容处理也经过真实验证。新记录证明请求内容被写入 stdin、CLI 返回答案及 turn.completed，并正常退出。

**未唯一定位历史 600 秒超时的底层原因。** 恢复后输入 token 仍为 54,927，没有证据声称消除了大部分上下文或某个插件必然造成旧超时。服务状态、传输等待或当时的模型生成延迟仍不可排除。恢复重新核验绑定并经独立审阅，关联说明文字也会变化；这不是只有一个变量的随机受控实验。成功仅证明经过本次修正的现有链路能在原 600 秒限制内完成同一任务。

## 验证分类与边界

`tests/pipeline/test_model_call.py` 是机制验证：配置隔离且保留 provider、脱敏记录可解析、stdin/事件/退出生命周期、真实本地测试子进程超时清理、结构化回答及工具拒绝。它不是化学业务验收，测试 Python 子进程只运行测试代码。

全量机制测试沿用上阶段测试环境：仅测试进程 PATH 排除 DockerDesktop，避免原夹具意外调用真实模型；真实 Docker 由恢复实验独立验证。Linux 补验复用既有容器镜像，无宿主安装。

最后一次程序修改后：Windows 全量 **234 项，232 通过、2 项平台跳过**；Linux 调用/恢复补验 **18/18 通过**；上述真实恢复也在最后修改后执行。早期测试中的脱敏 JSON 错误、首次配置错误和中间测试日志均保留，未用删除断言消除失败。

## 持久证据和复现

`validation/planner-timeout/` 保存 baseline.json、before.json、四次 recovery 日志、recovery-summary.json、CLI 结果、全量回归日志，以及 `library/` 中原样复制的完整 me-b 库和所有准备/审阅/规划/构建/执行/历史证据。`installed/` 是本次正式安装结果。原现场 `E:/Users/27343/Docker/me-b` 保留。归档复制不自动继承新路径的主机资格。

```powershell
# 从尚未规划成功的 B 候选恢复（本次实际命令）
python -m creation_pipeline runtime-prepare E:/Users/27343/Docker/me-b --candidate rdkit-recap-terminal-fragments --spec validation/markdown-entry/auto-spec.json
# 已完成后的默认查询、安装或完整重新验收
python -m creation_pipeline library E:/Users/27343/Docker/me-b
python -m creation_pipeline install E:/Users/27343/Docker/me-b --name rdkit-recap-terminal-fragments --destination ./recap-install-new
python -m creation_pipeline runtime-validate E:/Users/27343/Docker/me-b --candidate rdkit-recap-terminal-fragments
```

首条命令是本次历史复现记录；当前库已 accepted，复验应使用最后一条，不能重复 runtime-prepare 当作新创建。本轮真实执行的精确参数、临时 schema 定位和时间线均在各 model request.json/process.json/events.json 中，schema 本体持久保存。

正式 Skill：`validation/planner-timeout/library/accepted/rdkit-recap-terminal-fragments/SKILL.md`，与上一轮 B 的候选文件逐字一致。原始超时档案 `validation/markdown-entry/b-library/` 未改写。

远程 GPU、外部资源挂载、凭据传递、外部服务和第二台主机未扩展。此次若完成，只能称为“新创建实验的显式恢复完成”，不能称为不中断的自动创建成功。
