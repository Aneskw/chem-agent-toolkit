# 精确 Tool 制品复用：本机 v1 协议

2026-11-01：已实现显式 `shared_tool_image_v1`。默认自包含模式不变。
实现为 `runtime/shared_tool.py`，准备、执行、资格、恢复与 CLI 均已接入。
当前范围是调用方声明完整闭包、字节一致来源绑定的 Python 脚本。命中后默认调用
**当前 Skill 的验收专用模型阶段**，不读取旧工具的用例或通过标记。
显式 `acceptance_plan` 仍可作为调用方覆盖，但不再是命中的必需条件。

支持通过 `tool_artifact: {request_key, artifact_id}` 直接选择已有具体版本；仍须提供独立的
`shared_tool` 声明及当前要求。指定版本不存在、损坏、不兼容或当前不可用时阻止，不自动替换
或构建。未指定引用时仍自动解析。inspect 会返回 reference，准备后将 selection 与完整制品
记录一起冻结；运行时再次核对。用法与实测见 [直接版本选择](../integration/shared-tool-explicit-version-20261101.md)。

## 四类对象与状态

| 对象 | 身份与持久化 | 不代表什么 |
| --- | --- | --- |
| EnvironmentArtifact | 原共享环境配方、daemon ID、image ID、层/配置观察 | 不代表业务通过 |
| ToolArtifact | ABI、完整请求、构建计划（不含验收）、具体 base/env、实际 daemon/image、artifact_id | 已核验构建对象，不代表任一新 Skill 合格 |
| SkillBinding | 当前冻结包/来源/接口/验收指纹；命中时嵌入具体版本；首建时由绑定全部冻结指纹的 receipt 完成具体版本绑定 | 不继承旧包文案或资格 |
| ExecutionAttempt | 每次独立目录、容器、当前锁定用例、输入输出、镜像、原始断言与耗时 | 旧执行记录不能授予当前执行资格 |

`request_key` 是规划前已知的闭包（路径/sha256/bytes/mode）、显式依赖要求、接口、
平台、策略、约束和 memory/cpus/pids 限制的指纹。
`recipe_key` 是当前 v1 renderer 下具体环境计划（不含验收字段）与固定 base 的指纹；
它不是依赖完全锁定或可复现构建证明。`artifact_id` 是已观察具体版本记录的完整指纹，
其中 `image_id` 与 `daemon_id` 共同表达本机 Docker 身份，**不是 OCI manifest digest**。
升级 renderer/闭包语义时必须升级 ABI/策略，不能悄悄沿用旧请求协议。

`built`、只读探测 `available` 和 Skill `accepted` 分属不同事实。工具记录不含测试、
passed 或 Skill 资格字段。`complete_rebuild_lock=false` 的环境仍只复用当前确切镜像。

## 声明、闭包与准备

在 `runtime.<candidate>` 或 `runtime_defaults` 配置：

```json
{
  "options": {"pin_base_image": true},
  "shared_tool": {
    "closure": "all-package-and-sources-except-skill-document",
    "requirements": {"imports": {"rdkit": "unpinned"}, "executables": []},
    "interface": {
      "entrypoint": ["python", "/opt/skill/package/scripts/audit_atom_maps.py"],
      "workdir": "/opt/skill", "resources": [], "runtime_network": false
    },
    "platform": "linux/amd64", "policy": "closed-python-bundle-v1"
  }
}
```

所有 package 支持文件与完整 sources 都进入闭包，只有根 `package/SKILL.md` 被排除；
该文档仍进入当前 Skill 冻结、内容审阅与来源核验。当前不支持选择性排除其他文件，
因此改动包内 examples、资源或辅助脚本会保守 miss。锁定测试里的 fixture 与用例可以不同。
显式 `requirements`/`constraints` 保守进入请求键；流水线默认将用户 prompt 放入 requirements，
不同 prompt 可能因此 miss。只有确实相同的显式运行要求才应由调用方传入相同 requirements，
不能为了命中删除真实运行要求。仅修改 SKILL.md 文案不改变工具请求。

第三方 import 必须有显式要求；当前只支持与 import 同名的 distribution、精确版本或显式
`unpinned`。配方声明须一致，构建/绑定时再读取实际安装版本。包内本地模块和数据均按字节纳入。
动态加载、已识别的动态执行、`__file__`、外部进程、外部资源、运行时网络、Markdown 入口、
源码相关安装步骤、生成安装文件和依赖文件在闭包外的情况均拒绝。声明来自运行配置，不允许
模型用一段“闭包完整”声明替代这些确定性核验。这不是任意 Python 程序的静态闭包证明；
无法满足此显式有限协议时用具名 miss/阻止或保持原自包含模式。

命中发生在 `propose()` 和 base 解析之前。默认使用 `acceptance_only` 协议，只允许模型返回
`tests`、`acceptance_json`、`output_contract`、`unverified_behavior` 四个当前字段。
响应与模拟/重放输出都经过同一严格 schema；额外环境字段或 patch 操作被拒绝。
环境计划由程序从已绑定制品复制，确定性合并当前验收，模型不能改环境或入口。
材料按需读取、deadline、尝试数、调用 guard、DeepSeek 配置及供应商重试上限沿用原实现。
回执阶段为 `runtime_acceptance_planning`，独立于 miss 路径的 `runtime_planning`；
每个验收读材料/生成调用均占原有预算，不能把环境规划为零解释成总模型调用为零。
首次 miss 可走原组合 planner 或提供完整 `plan`；命中后不会调用原组合环境规划协议。
若同时给出的完整 plan 改变环境
字段，明确记录 `supplied_environment_plan_mismatch`，不会忽略调用方要求。
当前用例重新通过原来源引用、覆盖、负例、锁定及 native check 校验；候选的独立内容审阅不被省略。
验收模型不可用、超时、预算不足或合同不合格时阻止，不回退到旧用例或环境重规划。
修复只基于当前 Skill 的被拒草稿，不能引入 ToolArtifact 历史验收。
调用方覆盖的 `acceptance_plan` 同样要求恰含这四个字段并经过全部原校验。

## 镜像与资格

旧模式继续核对 revision/environment 标签、整个 package manifest 和来源入口。
新模式使用 `chem.tool.request`/`chem.tool.recipe` 标签与实际 image/daemon 身份。
规范工具树为 `/opt/tools/<request_key>/`，另有相同字节的 `/opt/skill/` 执行布局以兼容当前
入口及 native check 路径。两份工具目录都在镜像内核验；这项兼容副本有存储成本，不能宣称零开销。
SKILL.md 不在工具镜像内；依赖读取该文档的检查不会被删除，而会失败或要求使用旧模式。

运行前重算当前完整闭包与资源限制，核对冻结包/来源、具体工具记录、入口、层/ENV/WORKDIR、
非 root 用户和文件内容。目录检查拒绝额外文件与链接。每次在独立只读、非 root、无网络容器执行；
当前 report 继续通过 `locked_inputs`、`observations_pass`、coverage、当前 daemon 核验后才能 qualify。
新 Skill 的业务失败只影响自己的执行与资格；不改工具或旧 Skill。

## 登记、检查与恢复

默认目录 `.pipeline/shared-tools`；进程级 `CHEM_AGENT_SHARED_TOOLS` 可选同主机绝对共享目录。
目录不进入冻结配方。按 request_key 在原构建 deadline 内等待互斥锁；取得锁后重查候选，
完整构建、身份、内容与当前输入核验完成后才原子发布 `<request_key>-<artifact_id>.json`。
版本追加，不覆盖旧版本。失败/超时不发布；取消只释放自己的 token 锁；不按年龄抢占崩溃锁。

```text
python -m creation_pipeline runtime-tools-inspect
python -m creation_pipeline runtime-tools-inspect --offline
python -m creation_pipeline runtime-tools-inspect --root ABSOLUTE_PATH
```

只读检查不建目录、不建镜像、不删锁、不执行业务或授予资格。离线返回 `historical_unverified`；
在线区分 `different_daemon`、`image_unavailable_or_changed`、`invalid_record` 等。
miss 包含具体版本、具名失配字段或文件路径。不同请求不会尝试推断兼容。

安装 envelope、导入、同主机路径迁移与恢复沿用现有单一 catalog。导入/迁移撤销旧资格，
必须重新执行当前锁定合同。已有具体版本的恢复（包括显式 rebuild）仅核验并执行该版本，
不能在镜像消失后用同配方重建结果悄悄替代它；需要新制品时显式准备新修订。
本机环境偶然存在的作者路径不是依赖：运行使用冻结来源和镜像内文件。
跨 daemon/主机不继承可用性，当前没有 OCI registry 或 archive 导出导入。
文件 envelope 可以复制，但不是便携镜像交付，缺失具体制品时明确阻止。

安装生成普通包与旁置 `.runtime/<name>/{frozen,attempt}`。导入支持这份完整 envelope 或
包含 `records/<name>.json` 的原生输出目录；裸 SKILL 包、缺少 receipt 的 envelope、归档/OCI
镜像导入均明确拒绝，不从 package 文案重建资格。导入后的候选不能再次安装，必须显式执行。
迁移目录亦须撤销旧执行地点的资格，冻结输入与具体绑定不重写。

恢复可使用冻结绑定/历史构建回执中已核验的完整 ToolArtifact，不要求原共享目录仍存在；
这不等于镜像可缺失，也不依赖原作者路径。当前 daemon 必须仍拥有相同、可核验的具体镜像。
共享模式的显式 `--rebuild` 仍是该具体版本的核验和新执行，不重建一个替代版本。
复制到新 attempt 的 build receipt 保留历史 build_calls，不能用它统计本次构建；
本次构建次数应取当前实际调用日志。安装、导入和恢复的真实记录见
[两个生成 Skill 的交付验证](../integration/shared-tool-delivery-20261101.md)。

## Skillnet 后续适配接口

适配层可读取现有 catalog 的 Skill revision/内容状态、SkillBinding 的请求与具体 artifact_id、
ToolArtifact 的 typed local identity，以及 ExecutionAttempt 的当前合同指纹、独立输出和 qualify 结果。
写入应走 prepare → freeze → build/bind → execute → qualify/adopt；不直接写 accepted。
远端适配另增 `oci_manifest` 身份类型、分发与拉取验证、平台/策略协商和新的本机观察，
不把当前 Docker image ID 当远端引用。本轮不实现 Skillnet 平台、调度、worker、结果缓存或 GC。

## 2026-10-29 原设计记录（历史）

以下是实施前草案；其“尚未实现”状态由上面的有限 v1 实现范围替代，超出范围的能力仍是设计。

## 可复用对象和绑定

分开 EnvironmentArtifact、ToolArtifact、SkillBinding、ExecutionAttempt。EnvironmentArtifact 对应已核验的依赖环境；ToolArtifact 包含工具实现闭包、固定运行接口和具体环境；SkillBinding 把当次冻结 skill 的入口证明映射到具体 ToolArtifact；ExecutionAttempt 保留当前测试、镜像身份和独立输出。Skill 文案与验收不放入环境身份，但仍进入 skill 自己的冻结指纹与资格。

ToolArtifact 的最小记录必须包含协议版本、实现闭包 manifest（相对路径/sha256/mode）、源绑定、接口 argv/工作目录/资源能力、environment artifact identity、构建计划与审阅凭证，以及本机 daemon/image 身份。portable OCI identity 必须是独立类型和真实观察值，不能将 image ID 填入 manifest digest 字段。

request_key 在规划前产生：实现闭包、显式需求、目标平台和相关策略版本。声明闭包缺失、无法确认 import/数据/可执行依赖或含未绑定资源时，返回可解释 miss；不从一个主脚本 hash 推断所有传递依赖。环境尚未选定不妨碍按 request_key 查找多个已经接受的候选制品；只有完整要求一致、策略有效、制品可用时精确命中。不能跨不同显式版本要求或无声采用 latest。构建 recipe_key 和实际 artifact identity 分别保留，不能将 request_key 当作可重现构建证明。

旧实现的 revision 标签与镜像内 package manifest 检查是现有强约束，不能删除它们后直接“命中”。新 shared_tool_image 模式需要独立 ABI：工具文件存固定 /opt/tools/<tool-id>/，资格同时核对冻结 skill 包、源入口摘要、映射的工具入口和镜像工具 manifest。模型不能自证路径映射。旧 self_contained_image 模式继续原路径和原验证。两种模式必须在安装包、executor、证据和 qualify 中端到端识别；不混用旧 receipt。

命中只省略缺失工具的环境规划/构建，不省 skill 的内容审阅、来源/接口核验、当前验收用例编制与执行。已有工具的 passed 标记最多是工具回归历史，不是新 skill 的验收结果。命中后仍在每任务新建的非 root、只读、独立输出、默认无网络容器中运行；没有常驻 worker 或跨请求 Python 状态。

## 发布、失败与可移植性

按 request/recipe 单飞创建，已完成记录原子发布，观察记录与制品版本分离。并发未完成返回 busy 或有界等待，不能读取 partial；锁接管须可靠确认所有者。环境镜像缺失是环境 miss，ToolArtifact 源/接口不匹配是工具 miss，当前业务失败是新 SkillBinding 不合格。新构建失败不回写旧制品，不改变旧 skill 的具体绑定。

本机引用只保证同 daemon 的可用性。若要对外导出，选择并实现 OCI registry manifest 引用或自包含 OCI archive；导入后验证完整内容身份并重新建立本机观察。没有导出/导入实现时不能称为便携共享工具包。原 self-contained bundle 的可用性不能被新模式默默降级。

## 接入顺序与验收

先冻结 typed ToolArtifact/SkillBinding 协议和保守 request key，接入独立 registry + readonly resolve；再接 prepare/service/executor/qualify/install 的新模式，最后增加 planner 前精确命中。暂不增加自动兼容合并与 GC。

必须有真实测试：两个 skill 文案不同而完全同工具，第二个 ToolArtifact 命中且两次业务独立执行；不同源码/接口/资源/策略/平台拒绝错误复用；不同工具共环境；镜像丢失/daemon 漂移/记录损坏 fail closed；并发只发布完整制品；新 skill 用例失败不污染旧资格；旧绑定可继续运行；新模式导出/导入或明确拒绝不支持的交付形式。分别度量 planner 次数、环境 build、工具 build 和业务执行，不能把环境命中当成 Tool resolver 完成。

## 2026-10-29 官方资料核对

- https://github.com/opencontainers/image-spec/blob/main/manifest.md ：manifest 通过 descriptor 引用 config 和有序 layers；portable manifest identity 是独立对象。
- https://github.com/opencontainers/image-spec/blob/main/config.md#imageid ：当前规范不再统一规定各实现如何生成 ImageID，因此本机 Docker identity 必须注明实现/daemon，不能泛化为 OCI 配置哈希或 manifest digest。
- https://docs.docker.com/engine/containers/run/ ：镜像与容器有不同生命期；默认 ENTRYPOINT 与运行时 command 组合决定实际执行。共享镜像不要求共享容器；仅检查 command 数组是否重复出现脚本会误判默认入口。

上述协议取舍是对当前代码的设计推导；不是这些规范已经替 pipeline 实现或证明的功能。
