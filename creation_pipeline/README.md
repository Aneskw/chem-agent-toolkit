# 论文到 Skill 的创建流程

本目录从论文、数据库文档、工具文档和模型文档中抽取**带来源引用的方法候选**。单次工具调用会作为资源提示单独记录。文档格式见 [FORMAT-v0.3.md](FORMAT-v0.3.md)。


## 快速开始

以下命令均在仓库根目录运行。可把 python3 换成项目的 .venv-eval/bin/python。处理 PDF 需要 pypdf；调用模型需要本机已经登录的 codex 命令行工具。本流程使用 Codex 登录状态，不读取 OPENAI_API_KEY。

~~~bash
python3 creation_pipeline/collect.py --paper-id 2GFR874J
python3 creation_pipeline/run_pipeline.py --paper-id 2GFR874J --model gpt-6-astra
~~~

第一条命令联网收集来源。第二条命令准备来源文本、调用模型、核对引用原文及行号、生成 v0.3 草稿并检查格式。结果写入 creation_pipeline/results/<run-id>.json，包含阶段、状态及来源／响应哈希。这里的 LocalRetro 只是原有单篇命令示例；非 LocalRetro 的完整案例见上面的复现指南。

给 run_pipeline.py 加上 --draft-eval-tasks，可以让模型为每个 method_procedure 候选**起草**两道“该用”和两道“不该用”的任务，保存在该次运行的 evaluation_task_drafts/。它不会自动证明题目真正未见过，也不会自动确认答案。正式测试前应审核化学前提、适用范围、与来源的重合及标准答案。实际运行记录见 [decision-pilot-with-task-drafts-20260920.json](results/decision-pilot-with-task-drafts-20260920.json)。

### 重放已有模型响应

机械错误修复后，可用保存的响应重复引用与格式检查，避免再调用模型。每次使用新的运行 ID：

~~~bash
python3 creation_pipeline/run_pipeline.py \
  --paper-id 2GFR874J \
  --response-file /path/to/saved-response.json \
  --skip-collect \
  --run-id my-replay-01
~~~

**重放不是新的独立抽取。**若引用检查失败，原始模型 JSON 会留在 runs/<run-id>/responses/。应检查原文与行号的差异，不要编造引文。默认情况下，缺少主要来源全文的任务会在模型调用前以 primary_text_missing 停止。显式使用 --allow-repo-only 时，只能生成标明来源范围的仓库提示，不能称为论文来源的 Skill。检查结果里的 omitted_source_sections 和 source_text_complete，确认是否有来源段落未进入本次抽取。

## 输入与来源锁定

papers.jsonl 由用户提供的 Fwd Prediction.csv 和 Retrosynthesis.csv 整理出 52 条文献元数据；papers.summary.json 记录输入哈希。原表中的本地附件路径、笔记和摘要没有直接并入公开目录。repo_map.json 为最初五个反应模型选择仓库，source_locks/ 记录选定文件的提交版本和哈希。下载的原文、缓存及模型运行目录分别放在被 Git 忽略的 acquired/、cache/、runs/。

最早针对五个已映射仓库的覆盖统计为：52 条中 2 条同时有论文全文和固定版本仓库证据（LocalRetro、RetroXpert），3 条只有仓库证据，47 条只有元数据。这个**早期统计**不能代表后来公共来源获取阶段的覆盖率。逐篇检查使用：

~~~bash
python3 creation_pipeline/source_coverage.py
~~~

LocalRetro 全文按 CC BY-NC-ND 4.0 许可仅在本机处理；RetroXpert 的 arXiv PDF 也在本机处理，均未随仓库重新分发。

## 批量处理

把多篇论文或数据库、工具、模型文档放进同一个来源清单；每项独立处理，成功的草稿可发布到 skills/generated/<run-id>/：

~~~bash
.venv-eval/bin/python creation_pipeline/batch_pipeline.py \
  --manifest /path/to/batch-manifest.json \
  --model gpt-6-astra \
  --rounds 1 \
  --push
~~~

示例见 [batch-manifest.example.json](examples/batch-manifest.example.json)。--rounds 2 表示对每个来源做两次独立抽取；不同轮次可能产生不同候选，因此报告分开保存。本阶段不会自动去重、执行候选，或宣称它们对 agent 有用。

对两张 CSV 文献表，不必逐个指定论文 ID。mine_available.py 读取 papers.jsonl 和来源锁定记录，只处理当前处于 paper_and_repository 状态的条目，跳过只有仓库或元数据的条目：

~~~bash
.venv-eval/bin/python creation_pipeline/mine_available.py \
  --model gpt-6-astra \
  --rounds 1 \
  --push
~~~

建议先加 --dry-run 查看数量和论文 ID。早期快照中选中 52 条里的 2 条；随着全文和固定版本代码进入目录，数量会增加。

### 获取公开论文

acquire_catalog_sources.py 扫描 papers.jsonl，尝试 arXiv、PMLR、开放出版页面、OpenAlex、Unpaywall 等公开来源，生成 acquisition_report.json 与 acquired_manifest.json。无法取得公开全文的记录标为 source_missing，不会虚构论文内容。原始下载文件保存在被 Git 忽略的 creation_pipeline/acquired/；报告和清单可提交，以便重新取得和核对来源。

取得来源后，可以这样尝试最多 20 篇：

~~~bash
.venv-eval/bin/python creation_pipeline/batch_pipeline.py \
  --manifest creation_pipeline/acquired_manifest.json \
  --model gpt-6-astra --max-jobs 20 \
  --prefix public20-$(date +%Y%m%d-%H%M%S) --push
~~~

--max-jobs 20 指**尝试 20 篇**，不保证生成 20 个候选：某篇可能没有足够的方法信息，也可能遇到模型服务失败。候选经过来源与引用检查，执行验证和 agent 效果评估仍是后续步骤。

## 其他论文、数据库、工具和模型文档

抽取核心不限于上述 52 篇，也不要求配套仓库。可复制 [database-source.example.json](examples/database-source.example.json)，替换来源路径、URL、SHA-256，并把文档放在相对于清单的指定位置：

~~~bash
.venv-eval/bin/python creation_pipeline/run_pipeline.py \
  --config /path/to/source-manifest.json \
  --run-id my-source-01
~~~

清单中的历史字段 paper_id 在此只是安全的**任务标识**，不表示来源必须是论文。source_type 可以是 paper、database、tool 或 model；主要文档分别使用 paper、database_doc、tool_doc、model_doc 角色。补充实现文件可用 repo_code／repo_doc；这时最好提供 repo_root 和固定版本的 repo_manifest。

核心读取本地 PDF、JATS XML、HTML、Markdown、纯文本、代码和 notebook，检查引用行是否出现在提取原文中，并核对声明的 SHA-256。清单里的 url 用于记录出处，**不会**由这个入口自动下载。缺少主要文档时，除非显式使用 --allow-repo-only，否则停止。数据库文档可以支持条件化操作规则；单次 API 请求仍属于 tool_usage 提示，不自动成为方法 Skill。

抽取不会固定在某段或某行；但单次 run_pipeline.py 有上下文预算，每项至多返回四个候选。若来源很长或选段不佳，不能把一次成功运行解释为“挖完全文”。任意网站的自动发现、许可审查和下载不由这个清单入口完成；跨文本片段自动归纳也尚未由它保证。

### 更通用的文档、URL 和表格入口

run_public_pipeline.py 可接受本地文档、目录、公开 URL、混合 JSON 清单，或推断 CSV／TSV／XLSX 表格中的论文和来源列：

~~~bash
# 本地论文目录
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --input /absolute/path/to/papers --source-type paper \
  --target-candidates 20 --model gpt-6-astra --push

# 数据库文档网址，不是直接连接数据库
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --input https://example.org/database/api-documentation \
  --source-type database --target-candidates 2 --model gpt-6-astra

# 混合来源清单
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --catalog /absolute/path/to/sources.json --target-candidates 20 --push

# 从表格推断论文、DOI、PDF、仓库等列
.venv-eval/bin/python creation_pipeline/run_public_pipeline.py \
  --table /absolute/path/to/papers.xlsx --target-candidates 20 --push
~~~

sources.json 示例；相对路径以该文件所在目录为基准：

~~~json
{
  "items": [
    {"id": "paper-a", "source_type": "paper", "title": "论文 A",
     "sources": [{"path": "paper.pdf"}, {"path": "supplement.md"}]},
    {"id": "database-b", "source_type": "database", "title": "数据库 B",
     "sources": [{"url": "https://example.org/api-docs"},
                 {"path": "schema.sqlite"},
                 {"path": "data-dictionary.md"}]}
  ]
}
~~~

只获取并检查来源、不调用模型时：

~~~bash
.venv-eval/bin/python creation_pipeline/ingest_sources.py \
  --catalog /absolute/path/to/sources.json \
  --out creation_pipeline/intakes/my-sources
~~~

支持文本型 PDF、JATS XML、HTML、Markdown、纯文本、DOCX、notebook、JSON／JSONL、YAML／OpenAPI、SQL、CSV／TSV 和本地 SQLite 模式。SQLite 只读并只导出结构，不导出表记录。CSV／TSV 的行默认是元数据；抽取方法仍需相应文档。公开论文落地页上的 PDF 链接会被跟随；摘要页或访问验证页面会被拒绝，但 HTML 判断仍需人工复核。这不是无限制的网页爬虫。

长文档按预算分段，ingestion_report.json 保留原文件哈希、页码、URL 和片段清单。各主要文本片段会排队抽取，不因上下文长度而静默丢弃；但片段之间不会自动合并为同一个方法。单个来源失败会记录下来，其他来源继续处理。

table_to_catalog.py 识别 title、paper、doi、url、pdf、github、repository、type、category 等常见列名；含糊的映射会报告，没有公开来源的行也会留在转换报告中。项目自定义列名需要人工审核。扫描版 PDF 需要 OCR；私有或需认证的数据库需要用户提供有权使用的文档或模式。来源没有可支持的方法时，不会凭空生成可靠 Skill。

在 macOS 上，模型子进程优先继承显式代理环境变量；没有设置时可使用已启用的系统 HTTPS 代理。它不会修改系统代理配置。

## 抽象与去重

有了多篇论文中的 method_procedure 候选后，可按任务级能力分组，并与现有资源目录比较：

~~~bash
.venv-eval/bin/python creation_pipeline/abstract_dedup.py \
  --source 2GFR874J=localretro-v03-replay \
  --source 74LHJIVM=retroxpert-paper-code-full \
  --run-id localretro-retroxpert-code-v2
~~~

该阶段为每个候选提出能力表述、条件决策规则和去重建议，并记录与已有包的重叠关系；每个候选必须进入且只进入一个组。它在本地生成 v0.3 的 procedural_skill_candidate 文档，并在 results/ 写审核报告。**语义合并不会自动执行**：报告的 human_review_required 状态必须处理后才能发布或安装。这一步也不运行 agent 任务。原 LocalRetro／RetroXpert 对照草稿保存在 candidates/localretro-retroxpert-code-v2/，没有放进扁平安装入口。

## 发布后的工具执行检查

publish_run.py 把生成包复制到 skills/generated/ 后，会检查包内声明的可执行脚本。单个包的结果在 reports/execution.json，汇总在 PUBLISHING.json 和批量报告中：

- not_applicable：没有打包的 Python 脚本；应通过 agent 任务对照评价文字方法。
- untested_no_fixture：有脚本，但没有声明测试用例。
- passed／failed：声明的脚本用例全部通过／至少有一项失败。

可选的 execution/fixtures.json 为每个测试声明本地 scripts/*.py、字符串参数 args、expected_exit，以及可选的 expected_json_lines 输出断言。每例在临时副本中最多运行 60 秒，环境中不传 API 密钥。不会因为论文或仓库文件出现在来源材料里就直接执行。脚本通过只证明指定的本地行为；模型预测精度与 agent 效用需要分别评估。

对已有工具 Skill，可单独运行：

~~~bash
.venv-eval/bin/python creation_pipeline/validate_tool_execution.py \
  tools-skills/rdkit/chem-rdkit-descriptors \
  --output creation_pipeline/results/rdkit-execution-check.json
~~~

## 如何理解各项状态

| 状态 | 含义 |
| --- | --- |
| source_collected | 来源字节已锁定版本。 |
| cited_draft | 响应结构与引用位置通过机械检查；方法语义仍需审核。 |
| package_valid | 另有可用的脚本或接口。 |
| execution_passed | 在说明的环境下，正反执行用例实际通过。 |
| heldout_passed | 已完成独立任务评价；须查看任务、指标和结果。 |
| blocked_resources | 缺少数据、权重或服务入口。 |

只有经过审核、相应测试通过的包才应进入 skills/ 安装入口。**来源有效、格式有效、脚本能运行、能改变 agent 决策**是不同层级的结论，不可互相替代。

早期案例说明了区别：LocalRetro 的重放生成三个引用候选，但分别受到训练数据缺失、与已有资源重叠、缺少正向模型限制；不能算三个可工作 Skill。RetroPrime 的仓库响应修复外部 URL 校验后重放，得到两个仓库来源草稿，但没有论文全文或执行验证。LocalTransform 的三个草稿虽通过引用检查，固定版本仓库却缺少相应预处理、训练或解码脚本。RetroXpert 的首次论文加代码抽取有两处 PDF 空白／行号偏差，经邻近原文校正后得到两个引用草稿；扩大到 PDF、README 和六个固定版本实现文件后，得到两个论文加代码方法草稿及一个仅来自仓库的映射提示。对应报告均在 creation_pipeline/results/，不能视为化学效果验证。

另有五个按 v0.3 格式实现的**原子资源包**：RDKit 化合物过滤、RDKit 原子映射检查、RDKit 逆合成候选评分、LocalRetro 模板库预检、RetroPrime 推理预检。它们的测试只证明写明的确定性计算或文件检查范围，尚不能证明 agent 决策改善或反应预测精度提高。
