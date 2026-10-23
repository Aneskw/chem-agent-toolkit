# 按实际需求交付 Skill（r3）

版本 `source-2026.10.23-r3.1`。这是可构建运行环境的源码包，不内嵌镜像 tar、模型权重或认证信息。
首次模型调用、基础镜像和依赖下载需要网络；不承诺完全离线或字节级重建。

## 默认完整创建

需要 Python 3.10+、已自行认证的 Codex CLI；工具型候选还需要 Linux Docker Engine。
本轮使用 Python 3.14、Docker Desktop Linux amd64；宿主 Python 无需安装 RDKit。

```sh
python -m pip install -r creation_pipeline/requirements-runtime-model.txt
python creation_pipeline/verify_release.py --tests
python creation_pipeline/run_pipeline.py --config creation_pipeline/examples/rdkit-source.json --tool-bindings creation_pipeline/examples/rdkit-runtime.json --model gpt-6.1-sol --publish-local --run-id my-rdkit-run --total-seconds 2100
```

正常命令自动执行每个候选需要的阶段：生成 → 内容/格式/来源检查 → 工具需求判定 → 环境准备 → Docker 构建 → 业务验证 → 交付判定。归档单独记录。

- `not_required` 必须有来源支持的明确声明，没有冲突的执行需求或未解析依赖；内容检查通过即可交付，不调用 Docker。空 requirements 和 `allowed-tools: Read` 不能单独证明免执行。
- `required` 通过显式 bindings 关联工具。缺失绑定或来源文件阻塞；准备、构建及当前严格执行验收全部通过才交付。抽取阶段缺失的 repo_file 可由绑定工具目录中同路径的真实文件补齐，记录哈希；不能猜测关联。
- `unknown` 或关联不明确：待确认/阻塞，不能交付。提供有依据的输入后显式恢复。

新抽取结果提供 `tool_requirement: {status, reason: {text, citations}}`。
旧结果没有该字段时不会自动免执行；tool_usage 要求工具，方法型候选需要明确声明或绑定。仅引用可读取文档/数据资源不等于必须执行工具。
bindings 可按候选 ID 或引用来源选择。显式 not_required binding 必须提供相同结构的 reason，不能覆盖必需工具。
候选已明确 required 或 not_required 时，显式 binding 必须与之相同；双向冲突均阻塞，不自动覆盖。tool_usage 类型与 not_required 声明冲突也会在环境准备前阻塞，即使 binding 要求执行。
纯文本候选有未解析 unknowns 时保守阻塞。来源范围和科学限制保留原说明。

纯文本的确定性示例（人工编写且来源可核对的 response，记录为 saved_response_replay，无模型/Docker）：

```sh
python creation_pipeline/run_pipeline.py --config creation_pipeline/examples/text-source.json --response-file creation_pipeline/examples/text-response.json --run-id my-text-run
```

## 草稿与参数迁移

```sh
python creation_pipeline/run_pipeline.py --config creation_pipeline/examples/rdkit-source.json --draft-only --run-id research-draft
```

草稿报告 delivery_status=draft_only、delivery_accepted=false，不声明完成执行验收。

| 参数 | r2 行为 |
| --- | --- |
| 不传 runtime/success 参数 | auto + delivery，按实际需求验收 |
| --success-policy creation | 弃用别名，映射为 delivery，不能绕过工具验证 |
| --runtime-mode docker | 接受旧语法，按需自动执行；缺绑定阻塞对应候选 |
| --runtime-mode off | 必须同时显式 --draft-only，否则参数错误 |
| --success-policy execution | 保留全候选执行要求，并额外满足交付门禁；纯文本混合任务应使用默认策略 |
| --success-policy draft | 显式草稿模式别名 |
| 发布 --success-policy archive | 仅归档，可以保存失败产物，交付状态仍独立 |

## 状态和退出码

pipeline_status.json 和 results/<run-id>.json 保留抽取状态，并新增 creation_mode、delivery_status、delivery_accepted、delivered_candidates 和逐候选 delivery_checks。
阶段包括 generation、content、dependency_decision、environment_preparation、docker_build、tool_validation。
纯文本执行阶段为 not_required、execution_accepted=false，但可以 deliverable=true；prepared 仅代表环境材料已生成。
工具候选要求当前 acceptance v2、覆盖完整、证据一致且实际镜像 ID 可核对。

正常创建/批处理/恢复/默认发布：0 = 所需阶段通过；1 = 创建或归档流程错误；2 = 未满足交付条件（参数错误也为 2）。
草稿退出 0 只表示草稿成功；显式 archive 退出 0 只表示归档成功。无候选不是成功交付。
混合候选任一失败时整体失败；保留通过候选和失败证据。

```sh
python creation_pipeline/batch_pipeline.py --manifest creation_pipeline/examples/rdkit-source.json --tool-bindings creation_pipeline/examples/rdkit-runtime.json --prefix my-batch
python creation_pipeline/run_public_pipeline.py --catalog my-catalog.json --tool-bindings my-bindings.json
python creation_pipeline/publish_run.py --run-id my-rdkit-run
python creation_pipeline/publish_run.py --run-id failed-run --success-policy archive
```

发布事务保护归档和分类目录，默认不覆盖；确需替换时显式 --replace-existing。
PUBLISHING.json 的 archive_status=completed 不等于 delivery_accepted=true；delivery_publication_state 区分 accepted_delivery / unaccepted_archive。

## 独立恢复

```sh
python creation_pipeline/inspect_run.py --run-id my-rdkit-run
python creation_pipeline/inspect_run.py --run-id my-rdkit-run --action retry-runtime --total-seconds 900
python creation_pipeline/inspect_run.py --run-id research-draft --action retry-prepare --tool-bindings creation_pipeline/examples/rdkit-runtime.json --total-seconds 1500
python creation_pipeline/inspect_run.py --run-id my-rdkit-run --action retry-publish
```

retry-runtime 不重新抽取或生成 Skill，复用计划和锁定测试。构建失败则重建；可核对且未漂移的构建可复用镜像，但重新执行全部必需业务测试。已通过候选也须检查当前证据才能跳过。
retry-prepare 用于尚无 runtime 的草稿或补齐绑定后的候选；有 runtime 时不隐式重置契约。
显式准备入口是 prepare_runtime.py <candidate> --job-id <job> --tool-bindings <file>，旧证据会保留。
输入/来源/绑定改变应处理后新建运行或明确重新准备，不能只改哈希保留通过标记。无效锁定探针与漂移阻止自动续行。
只选择一个候选恢复时，最终仍检查整个运行。

## 可构建示例与迁移

发布包 examples/accepted-skill 包含本轮验收的 RDKit Skill、Dockerfile、完整上下文、运行器、配置及原始验证证据。
DOCKER.md 提供业务命令。包内 runtime/runner.py 只需要包内执行材料及 Docker，但要求对应已验收镜像存在。
历史记录的绝对路径是原验收审计路径，不能当成新主机的当前通过证据。

迁移入口检查工件、相同 bindings 字节及完整源码清单，归档旧证明、撤销旧接受状态，再以原锁定测试重新构建和验证；不调用模型，不降低断言：

```sh
python creation_pipeline/relocate_runtime.py examples/accepted-skill/calculate-rdkit-descriptors --tool-bindings creation_pipeline/examples/rdkit-runtime.json --total-seconds 900
```

ZIP 解压可能改变时间戳精度。迁移入口先核对文件内容与来源清单，再恢复上下文已记录的时间戳/权限，保留原有完整性检查。
先验清单，再在副本中运行迁移/重验；重验会生成新记录，因此文件清单自然变化。bindings 或源码内容不同时拒绝迁移，须建立新的准备和验收。
ZIP 不含镜像。镜像 ID 及完整命令在 runtime/delivery.json：

```sh
docker image save -o rdkit-image.tar <image-id>
docker image load -i rdkit-image.tar
```

镜像加载不自动赋予新输入验收资格，仍需迁移/重验；标签不是不可变 ID。

## 回归与封包

verify_release.py --tests 检查清单、入口和机制回归，模拟模型/引擎，不代表真实执行。
包内 evidence/ACCEPTANCE.json 记录封包前回归和真实执行；最终 ZIP 外 FINAL-ACCEPTANCE.json 绑定 ZIP SHA-256，记录独立解压清单与业务重验。
MANIFEST.json 包含除自身外全部文件哈希。最终 ZIP 验收后不再修改。
本包验证工程行为，不证明科学正确性、全面工具支持或 Agent 收益。
