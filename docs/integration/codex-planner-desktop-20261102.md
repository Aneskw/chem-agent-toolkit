# Codex planner：桌面随附运行时验证

核对基线 `3f459be`。用户明确授权本轮把 planner 从 DeepSeek API 切回 Codex，并跑一组测试。
使用已实现的 `codex_cli` 后端，新增普通配置 `validation/codex-planner/skill-{a,b}.json`；
没有新增私有桌面 RPC、读取/复制登录 token、安装独立 CLI、修改全局配置或引入自动后端回退。
原 DeepSeek 配置及此前证据保留。首轮暴露了 Codex 严格 schema 的真实兼容缺口；
修复限传输适配和错误反馈，实际结果及失败凭据分开记录。
**最终通过**：普通 CLI A 16/16、B 16/16，共 32/32；当前资格均通过。
首建的 3 次联合 planner 与命中的 2 次验收专用 planner 都是实际 Codex 完成回执，
无工具事件、无 DeepSeek 模型调用；独立审阅、当前锁定合同和新执行全部保留。

## 本机实际入口

`codex_command()` 从当前 PATH 解析到桌面附带的
`C:/Users/27343/AppData/Local/OpenAI/Codex/bin/22cfb1d302613eae/codex.exe`，
`--version` 返回 `codex-cli 0.166.0-alpha.5.1`。这是本机观测，不保证所有 ChatGPT 桌面端
都带相同组件，也不表示聊天窗口提供程序 API。普通终端需要在自己的进程 PATH 中能解析 codex。
版本检查不证明登录/模型权限；只有实际 completed 回执与合格业务执行才构成本轮证据。

官方 [非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode) 支持 `codex exec`、
复用正常客户端认证、`--output-schema` 和 `--json`。本项目沿用该机制：临时隔离目录只有 schema，
read-only、ephemeral、关闭 shell/apps/plugins/hooks/MCP 等，禁止工具调用；收到工具事件或不完整
输出仍拒绝。没有直接请求桌面内部 HTTP 端点，也没有把订阅登录凭据作为 API key 导出。

## 配置与预算

仅将 runtime options 设为 backend=codex_cli、model=gpt-6-astra、transport=https；模型与传输
沿用已有 native Codex 配置。发现、编写与独立审阅的配置不变，接口、依赖、JSON、源码、显式要求
及业务失败用例不变。DeepSeek 专用 api_* 字段移除，它们不约束 Codex 子进程；不能把该变化描述为
相同的 provider token 硬上限或定价。每批 16 个准入阶段、单次 600 秒、总计 3600 秒、准备 2400 秒
等原封套保留，实际 usage 单独记录。入口关联和诊断复用 runtime options；本轮若没有这些调用，
不把它们计成已验证的真实模型场景。独立审阅和当前冻结资格门禁全部保留。

源码仍是 P2 新整合的真实 RDKit 模块与固定 JSON 规则，源计算模块和原 requirements 原字节不变。
不是重新包装后把旧验收或 passed 带入新 Skill。两个配置仅文案/批次标签不同，实现和要求相同。

## 离线检查与真实操作

`E:/Users/27343/Docker/codex-planner-cli-20261102-01/offline-checks`：133 项既有 Codex/DeepSeek
传输、planner schema、输入契约回归通过；三个提示自检和平台契约检查通过。实际 Docker 可用。
这些检查不发送真实模型请求；没有因漂移而 freeze，没有改提示或 schema。
这是修复前结果，不能作为修复后代码的完整证明。

首轮 `20261102T122109-69cca6e5`：发现/编写/独审通过，第一次 planner 请求即被服务端拒绝，
API code=invalid_json_schema，具体位置 `plan.acceptance_json.type[1]` 缺 additionalProperties=false。
这不是网络或 PowerShell snapshot 警告导致的故障。原逻辑 schema 允许 JSON 字符串或开放对象，
与 Codex 的严格输出 schema 不兼容；case_json 有同类问题，PATCH 的可选 value_json 也不满足
严格 required 规则。此轮 4 个准入阶段（3 完成、1 请求拒绝）、零构建、零业务执行，资格 false。
未 resume/restart、未增加预算，全部日志保留。此前错误只显示 stderr 警告；现在会保留并脱敏
终端 error/turn.failed 消息，将服务端 invalid_json_schema 分类为 model_config_invalid，指出真实字段。

`model_call.codex_schema()` 将原 schema 已允许的 JSON 文本联合类型收窄为 string，固定对象的
已有属性全部列为 required（remove 补丁可给未使用的 value_json="null"）；未知开放对象没有文本
替代形式则在发请求前具名拒绝。不发明业务字段、不放宽 source schema，不改变 JSON 文本的解码、
source quote/coverage/契约/资格检查；DeepSeek 分支继续使用原 schema。source schema 与实际 wire
文件各有独立摘要，receipt 增加 wire_schema_sha256 和 schema_projection=codex-json-text-v1。
该有限适配依据官方 [Structured Outputs 约束](https://developers.openai.com/api/docs/guides/structured-outputs)，
不是支持任意 JSON Schema 的编译器。

新增 7 项有效离线回归；修复后 154 项针对性集合通过。按顺序 verify_planner freeze →
verify_acceptance_prompt freeze 后三个 check 及平台契约通过。确认差异只有新增 wire schema 身份，
原 prompt、逻辑 schema、业务规范和 fixture 原字节不变，没有为消除未知漂移刷新快照。
修复后全套 **755 项：752 通过、3 跳过**，unittest 内部 191.916 秒，
见 `codex-planner-postflight-20261102-01`；不是使用 748 项历史结果代替。

修复后的独立新轮为 `codex-planner-cli-20261102-02`，配置与首轮原字节相同，模型/时间封套未增加。
零模型 `codex login status` 只记录 auth_mode=chatgpt 和退出码，不保存原始输出或账户详情；
没有新配 API key，正常客户端认证的读取/刷新由客户端负责，程序不读取或复制 token。
此状态只说明登录方式，不替代实际 inference completed/资格证据。

```powershell
$root="E:/Users/27343/Docker/codex-planner-cli-20261102-02"
$env:CHEM_AGENT_SHARED_TOOLS="$root/shared-tools"
$env:CHEM_AGENT_SHARED_ENVIRONMENTS="$root/shared-environments"
python -m creation_pipeline build "$root/skill-a.json" --preflight
python -m creation_pipeline build "$root/skill-a.json" --state-dir "$root/a/state" --library-dir "$root/a/library" --keep-debug
# A 完整核验后才启动 B；不恢复失败轮。
python -m creation_pipeline build "$root/skill-b.json" --state-dir "$root/b/state" --library-dir "$root/b/library" --keep-debug
```

记录器仍为 record_public_cli.py，只记录实际 CLI 命令和经 redact 的日志；没有注入候选、环境、
acceptance_plan、绑定或资格。新 registry 不代表 Docker 冷缓存：已有镜像和 BuildKit 层保持原样。
模型/环境/工具/用例计数分别记录，不把 build 次数当安装次数，不从虚拟镜像大小推导物理磁盘节省。

## 最终实际结果

| Skill | build_id | Docker 用例 | 发现/编写/独审 | 联合 planner | 验收专用 planner | 环境/工具 build |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | 20261102T133538-abd4a2ac | 16/16 | 各 1 | 3 | 0 | 1/1 |
| B | 20261102T135016-17fd2f45 | 16/16 | 各 1 | 0 | 2 | 0/0 |

A/B 同一 request_key=`b526d9105559a4bcdafbc4b5a9e1468d454fe5a3fb7c14f91c73f9a2f4c627ac`，
具体 artifact_id=`95a3fe4d2173cdfa03118dc49eb5855bb44ce0a5bf96be488ae13dc2f4a33357`。
这是独立新 registry 首建的版本，不把旧 P2 版本或其 passed 复制过来。B 是自动命中，不指定 artifact。
Skill 文案/revision、编写/独审 session、执行 attempt 均独立；镜像/实现闭包/要求相同。

A 总计 6 个准入阶段，B 为 5 个，成功配对合计 11。再加首轮失败 4，共 **15 个启动阶段、
14 个完成阶段**，另一个是服务端 schema 拒绝请求，是否计费未知；不是免费探针。
这些是准入阶段，不等于 Codex 内部 turns、底层 HTTP 请求或计费调用次数；每批限额仍为 16。
所有真实运行时模型回执 backend=codex_cli、model=gpt-6-astra、tool_events=[]，
逻辑 schema 摘要与每轮 provenance 相符，实际 wire 文件与 codex_schema 投影相符且 hash 单独记录。
同一 metadata 不冒充 OCI manifest；ToolArtifact 的本机 image_id 仍只表示当前 daemon 上镜像身份。

A 前两份草案分别因缺非法输入解释、缺已声明检查的负例而拒绝，自动修复后才锁定。
B 首份草案把 Python 入口错误写成脚本自身；门禁指出具体用例、实际/期望 entrypoint 与 args，
第二份按相同业务要求修正后执行。没有手工提供 plan、修改来源、删除失败执行或放宽资格。
审计辅助脚本首轮误从 summary 查完整回执字段而 KeyError；改从原始 receipt 核验同样断言后通过，
更正说明单列，不重跑模型或业务，不把它记成 pipeline 失败/成功新批次。

证据均在新 -02 目录：

- `audit-ab.json`：32/32、真实四类直接业务输出、原字节/绑定/镜像、A/B 及两份旧 P0 当前资格。
- `codex-backend-audit-ab.json`：5 次 Codex 运行时回执、实际 wire 文件/源码 schema/进程隔离参数，
  以及旧 P2 两份真实 Skill 全目录原字节不变且当前合格。
- `operations/check-current-{a,b}`：公开 CLI 按各自原配置核验交付布局通过。
- `failed-round-audit.json`、`failed-round-manifest.json`：首轮仍不合格、没有执行报告或制品登记污染。
- `production-code.json`、`source-before.json`、`final-evidence-manifest.json`：源码、来源与完整证据 hash。

可复核索引为 `validation/codex-planner/results-20261102.json`；首轮目录和完整回归目录另有清单。
CLI wall 实测 A 605.151 秒、B 635.444 秒。不同文案、模型响应、验收内容和缓存预热影响总时长，
不把它当作与 DeepSeek 的受控速度/质量对比；本轮结论是后端切换可运行且门禁完整保留。
没有物理磁盘差分测量、常驻 worker、远端平台或 OCI 分发扩展。
