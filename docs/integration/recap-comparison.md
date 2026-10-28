# RECAP 同源对照验收：真实运行，双边未完成

本次结果不能称为双边端到端通过。partner 原版完成发现和文件编写，但作者完成回执受阻；合并版完成发现、编写及独立内容审阅，但文档内入口无法绑定，停在 Docker 规划之前。没有真实业务执行、镜像构建或正式晋升。本次没有重复尝试 DNA，也没有改变其历史证据。

## 基线和输入

- 原版：`e117c434f54d11fd24e3e5566f187a8f4a41a87f`，原 Downloads 工作区干净。用本地 clone `E:/Users/27343/Docker/chem-agent-toolkit-recap-partner` 运行，代码未改，运行后 clone 仍干净。
- 合并版：`cf7a9c5d095546dc10f13a1cf79b67483dd1b4bc`，开始时干净，无后续提交。本轮新分支 `integration/recap-comparison`，没有生产代码改动。
- 核查父目录及双方仓库，未发现适用 AGENTS.md。没有 fetch/reset、远端推送或发布。
- 原版历史 build `20261022T235548-09672526`，来源 ID `recap`，snapshot `a1996f49d039b4da6a5681b22926f959d02a0038bc4f040e9eee16b8b098c5ca`。历史目录只有 Skill，catalog 记录检查名称和 pass 摘要；`.pipeline` 没有原始记录。
- 未恢复：历史输入配置、用户提示、模型参数、原始来源字节及上游版本、原发现/作者/审阅/执行日志。因此这是**同任务、共同重建输入的对照**，不是精确历史复现。
- 共同源码：[官方 Recap.py](https://github.com/rdkit/rdkit/blob/237a1d9027c800784afed8788540f38a3aa595f8/rdkit/Chem/Recap.py)，tag `Release_2025_09_1`，commit `237a1d9027c800784afed8788540f38a3aa595f8`；同时保存官方 license.txt。文件 hash 在 `validation/recap-comparison/baseline.json`，双方实际快照逐文件核验相同。
- 两边读取同一个 input.json，未做协议转换；同一真实模型 `gpt-6-astra`，production 默认不设整体配额。原版生成检查默认 opt-in，本次未开启宿主执行；合并版沿用自动 Docker 阶段。没有安装宿主依赖。
- 输入没有历史 Skill、测试预期或预制脚本。业务评估清单在运行前写入 `business-checklist.md`，未作为来源输入。双方保留原生提示词。模型客户端/Docker 版本分别在 codex-version.txt/docker-version.json。

## 本次真实运行与边界

| 项目 | partner 原版 | 合并版 |
|---|---|---|
| 新 run ID | 20261026T121411-9b1ae0d2 | 20261026T121422-2d6fa481 |
| 真实模型阶段 | 发现、作者两轮 | 发现、作者两轮、独立审阅 |
| 生成目录 | SKILL.md + references/LICENSE.txt | SKILL.md + references/license.md |
| 作者完成 | 未完成回执 | 已完成，复用既有宿主 finish 保障 |
| 独立内容审阅 | 未到达 | pass，执行需求 confirmed |
| Docker 规划/构建/执行 | 原版未提供自动 Docker 能力；生成检查未执行 | 全部未到达：binding_unresolved |
| 状态/入库 | failed / not_eligible | runtime_blocked / candidates |
| 正式资格 | 不适用新版库，未宣称合格 | accepted=false |

原版模型子进程启动指定 Python helper 时发生 Windows access denied。两轮未产生合法 finish 回执，原有“Repeated unchanged failure”机制停止。未修改原版、手工调用 finish 或填造回执。它有新生成的文档，但不是原版成功交付。原版没有 Docker 本身不是判失败依据。

合并版既有 author() 允许模型写完文件/metadata 后，由宿主调用相同 finish 校验，解决上述 helper 条件；这不是本轮添加的回退。第一轮还把许可证放在不支持的顶层 LICENSE.txt；第二轮作者自行移到 references/license.md，随后独立审阅通过。这是**真实作者文件结构修复**，不是内容业务失败修复或验收契约修复。

合并版作者声明 required，提出三项检查：documented-terminal-example、valid-empty-result、input-guards。它们读取实际交付 SKILL.md 的 Python 块并执行，不是仅验证 RDKit 安装。独立审阅明确指出运行未验证。可惜 preparation.bind() 自动关联只支持与来源字节一致且唯一的 .py/.sh 交付文件；本产物只有说明和代码块，因此在 host 探测、planner 调用、环境材料生成之前被拦住，model_calls=0。

这是**当前执行绑定协议不能覆盖该交付形态**，不是 GPU/内存/Docker 暂缺，也不是已证明的业务源码错误。补充资源或原样 runtime-resume 不会解决它。现有显式 binding 也不能独自解决 Markdown 的解释器入口和完整测试映射问题；不应拿 SKILL.md 当 Python 文件或手工增加脚本后称自动通过。本轮未增加另一套执行器/入口、未人工补计划或放松资格。支持这一形态需要后续在既有绑定/规划边界设计可核验文档代码入口，本报告不宣称已经支持。

候选修订 `rev-ff87c14e89b29edc4aac7fe8a4c1dfb7ae26815ddd9325bf74b88fd811ea53e0`；内容 passed、执行 runtime_blocked、host not_checked。catalog 及 sources、交付、作者测试、诊断、freeze 均持久保存。CLI 实测默认查询为空、显式候选访问成功、默认安装拒绝且未创建安装目录。没有错误晋升。

## 共同业务质量比较

共同检查依据为固定源码的 docstring、GetLeaves 实现、test1/test2/testMinFragmentSize；不是从生成结果倒推预期。

| 方面 | 实际比较 |
|---|---|
| 化学任务忠实度 | 两边都使用 RecapDecompose/GetLeaves，不是描述符；保留 * 附着点，不声称合成可行性。 |
| 层级/终端/空结果 | 两边均正确给出 4 直接子节点、5 后代、3 leaves；CCCOCCC 默认空结果合法，不回退原分子。 |
| 输入输出 | 原版连续示例保留 leaves、fragment_smiles、fragment_mols；合并版给出 terminal_fragment_smiles 函数返回排序字符串列表，并说明如何另取 node.mol。排序有源码示例依据。 |
| 非法输入 | 两边都定义空字符串、解析失败、零原子 guard，说明它是接口政策而非 RECAP 原生规则；未执行，不能确认异常行为已验收。 |
| 可用性/触发 | 两边均有具体化学触发描述、容器前提及连续示例。原版提供 docker exec 交互使用步骤；合并版函数更便于复用，但未形成可绑定脚本。长度差别不是质量结论。 |
| 范围 | 两边都区分唯一片段数与重数，说明缓存/过滤边界。原版额外详述 minFragmentSize=3 的 *CCC 结果；合并版将自定义参数放在正常范围之外，没有冒充另一个任务。 |
| 支持文件 | 都只有必要许可证文本，无独立脚本；这一形态符合原版直接 API 包装思路，却暴露合并版执行入口支持不足。 |
| 来源版本表述 | **共同问题**：本地 path 来源采集得到所在集成仓库 cf7a9c5 + dirty；两边把它写作 supplied source revision，而非官方 RDKit commit。原版同时给出准确文件 SHA-256，合并版正文未给文件指纹。两边都提示不能等同安装版本，但上游版本归属仍不清。baseline.json 保留真正上游身份；原始产物不作展示性修订。 |

历史 partner Skill（1901 字节）只有简短调用、3 leaves 和空结果说明；本次原版（5507 字节）与本次合并版（5221 字节）增加了输入 guard、层级差异、许可证及科学边界。历史 Skill 不是本次任一生成结果，没有继承其 pass 状态。

资源准备与候选发现行为在本任务保持；独立内容审阅在合并版实际运行，原版受前置环境阻塞无法公平比较该阶段。不能凭本轮断言全部 partner Skill 无回归。Docker 新增保障本轮只验证了“执行需求不能因无脚本而被跳过、未验收不得正式入库、候选默认隔离”，**没有验证构建或业务执行成功**。

## 超时、修复与人工干预

本轮没有 planner 请求，所以没有重现或解释 DNA 的规划超时。真实 Native 模型请求有事件、源码读取和完成记录，不能由此推断另一种 tool-free planner 调用正常。也不能把本轮 Python access denied 说成此前网络超时根因。

人工操作仅限固定版本、本地隔离 clone、共同来源下载与输入配置、运行 CLI、读取/归档证据和库访问验证。没有显式 resume、重启创建、人工修业务代码/断言/环境计划。正常主流程自行发起第二轮作者调用；无运行契约诊断、独立契约批准、环境修复或内容业务失败修复。本轮这些路径均未覆盖。没有额外手工 Docker 测试冒充主流程验收。

## 直接打开的新产物与证据结构

仓库根目录为 `E:/Users/27343/Docker/chem-agent-toolkit-integration`：

- 原版本次新生成：`validation/recap-comparison/partner-state/runs/20261026T121411-9b1ae0d2/bundle/skills/rdkit-recap-terminal-fragments/SKILL.md`。
- 合并版本次新生成：`validation/recap-comparison/merged-state/runs/20261026T121422-2d6fa481/bundle/skills/rdkit-recap-terminal-fragments/SKILL.md`。
- 历史对照（不混用）：`validation/recap-comparison/partner-historical/SKILL.md`。

```text
validation/recap-comparison/
  source/                         # 共同官方源码和许可证
  input.json baseline.json commands.json business-checklist.md
  partner.log merged.log summary.json
  partner-state/                  # cache、runs、outputs 原始字节归档
  merged-state/                   # 同上，含独立 reviewer 提示、事件及结果
  partner-historical/             # 明确标记的历史对照
  library/                       # candidates + 统一 catalog + 持久化 evidence
  default-query.json explicit-candidate.json install-rejection.json inspect.json
  cli-verification.json evidence-inventory.json
```

每轮模型 prompt/schema/events/stderr/result 在各 state/runs/<ID>/agent-turns/，作者 metadata 和失败 record 同样保留。原工作目录也未删除。没有镜像身份/业务执行日志，是因为本轮未创建或执行镜像；docker-version.json 仅证明引擎可查询，不是验收证据。

## 复现和检查

实际命令在 commands.json；两边使用同一个 input.json。选择新 state/library 目录避免混入旧运行：

```powershell
# 原版隔离 clone 根目录（固定 e117c43）
python -m creation_pipeline build E:/Users/27343/Docker/chem-agent-toolkit-integration/validation/recap-comparison/input.json --state-dir E:/Users/27343/Docker/recap-p-new --keep-debug
# 合并仓库根目录（验证代码 cf7a9c5）
python -m creation_pipeline build validation/recap-comparison/input.json --state-dir E:/Users/27343/Docker/recap-m-new --library-dir validation/recap-comparison/new-library --keep-debug
python -m creation_pipeline library validation/recap-comparison/library
python -m creation_pipeline library validation/recap-comparison/library --name rdkit-recap-terminal-fragments --include-candidates
python -m creation_pipeline runtime-inspect validation/recap-comparison/library --candidate rdkit-recap-terminal-fragments
# 以下安装应拒绝，不能加候选绕过资格：
python -m creation_pipeline install validation/recap-comparison/library --name rdkit-recap-terminal-fragments --destination ./recap-install-new
```

验证脚本 verify_cli.py 实际调用 CLI，检查过滤/显式访问/拒绝安装。verify_evidence.py 核验共同来源、归档、资格、模型阶段和文档原始字节。未修改程序，无必要重跑与本次无关的昂贵全量模型/Docker 实验；此前回归证据不改标为本轮运行。本次只运行记录与库接口相关检查。

未完成：原版独立审阅/检查完成；合并版文档代码绑定、模型规划、Docker 构建/实际入口验收/accepted 晋升。两边内容的源码静态对照不能替代真实业务执行。第二台主机、远程 GPU、外部资源挂载、凭据传递、外部服务都未扩展。DNA 仅保持辅助历史测试定位。
