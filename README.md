# Chem Agent Toolkit

面向化学科研 agent 的可复用技能仓库雏形。

## 当前状态

仓库先提供统一目录、安装入口和已有技能样例。尚未生成的技能不会提前创建；空的分类目录只保留目录说明。

## 技能目录

| 技能 | 类别 | 状态 |
| --- | --- | --- |
| `localretro-single-step-retrosynthesis` | models-skills/open-models | verified（限定样例） |
| `retroprime-two-stage-retrosynthesis` | models-skills/open-models | verified（限定样例） |
| `wln-build-molecular-graph` | models-skills/open-models | verified（图构建子技能） |
| `retroxpert-evaluate-bond-disconnection` | models-skills/open-models | blocked_resources |
| `localtransform-forward-prediction` | models-skills/open-models | blocked_resources |

## 使用

将需要的技能目录复制到 agent 的 skill 目录，阅读其中的 `SKILL.md`，再按“使用步骤”执行。技能的运行状态和验收范围以各自文档及 `reports/` 记录为准。

## 目录约定

- `skills/`：扁平 CLI/agent 安装入口；指向分类目录中的已生成技能。
- `databases-skills/`：数据库技能分类，当前为空；未来放 PubChem、ChEMBL、Identifier Resolver。
- `tools-skills/`：工具库技能分类，当前为空；未来放 RDKit、Open Babel、OpenMM、PySCF 等。
- `models-skills/`：模型技能分类；现有五个反应模型技能归入 `open-models/`。
- `workflows/`：组合工作流，当前为空。
- `.claude-plugin/`：插件市场元数据。

## 证据与方法

原始论文、仓库快照、运行日志和格式说明保存在项目的开发归档中；技能文档中的 `reference` 指向固定来源。`verified` 只表示文档声明范围内的可运行性，不代表化学准确率或实验成功率。

## 关于“9/10 个候选”

这里的 9 和 10 是一次模型推理返回的候选反应物数量，不是“9 个技能通过、10 个技能候选”。例如 LocalRetro 请求 `top_k=10` 时，模型先生成编辑候选，包装器再删除非法、重复和占位结果，所以最终可能返回 9 个或 10 个有效候选；数量少于 `top_k` 不代表模型失败，也不代表化学反应一定可行。
