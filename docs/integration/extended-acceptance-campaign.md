# 扩展验收：两个描述符批次与两个典型场景

操作者在 run49 后明确授权：新开独立轮，先跑通前两轮描述符文件测试，遇错修复后重跑；再选择两个典型场景，同样调试到通过。采用四个独立成功批次作为完成标准，失败批次不计成功，不续跑/重启失败轮，不放宽用例。

| 场景 | 来源 | 必需业务证据 |
| --- | --- | --- |
| descriptors-a | 原有 chem-rdkit-descriptors | 原脚本不变、真实乙醇数值、空串/非法输入拒绝、合法与混合批次实际 --output JSONL |
| descriptors-b | 同一来源，全新生成/规划/执行 | 同样完整义务；独立 state/library 和镜像执行证据，不能复用 a 的状态 |
| atommap | 原有 chem-reaction-atommap-audit | 正常映射、合法 leaving-group map、重复/缺失/额外映射与语法拒绝、混合批次文件输出 |
| geometry | 原有 ASE chem-structure-check | 实际坐标距离、约束失败但检查完成、非法请求拒绝、输入不可变；不虚构输出文件功能或物理有效性 |

四个输入封套分别位于 `validation/deepseek-api/acceptance-{descriptors-a,descriptors-b,atommap,geometry}-input.json`。原项目仅作为只读来源。继续采用 Codex CLI 原生阶段与 DeepSeek 结构化阶段，每轮 16 次预算计数调用、600 秒单次、3600 秒总限额，基础镜像固定 digest。每次失败后先保存和诊断证据、离线修复/回归、自检、提交，再用新轮次和全新目录重跑；不修改正在运行的实现或封套。不打印凭据，不推送/合并/创建 PR。

完成必须同时有：规划 prepared 与固定 digest、构建 image.id、对应场景业务断言全部通过（不是只看 ready）、冻结证据完整、轮后全量离线回归与三个自检全绿。阶段预算计数不能冒充供应商 HTTP 请求总数。

进度保存在 `validation/deepseek-api/extended-acceptance-progress.json`，每轮结束后更新实际结果与证据路径。run47 的旧成功可用于回归参考，不能替代本轮四项新的独立成功。

## run50：描述符 A，模型流超时

实现起点 `7f80b5a`，构建 `20261028T221546-0b900804`，北京时间 2026-10-28 22:15:46–22:37:45。发现、编写、独立审阅完成，首次结构化规划 HTTP 200、连接约 0.23 秒，但接收约 8.3 MB SSE 数据后仍未在 600 秒内完成，停止于 `model_timeout`；预算计数 4，没有镜像或业务执行。没有重启/恢复本轮。

证据：`E:\Users\27343\Docker\acceptance-descriptors-a-run50-20261028\`，包含旧封套 `input-envelope.json`、summary、记录、receipt 与 `model-0/attempts.json`。不能将收到字节数当作已完成计划或完整 token 用量。

下一轮配置调整：本地后端的兼容映射将 requested `medium` 发成 provider `high`；后续结构化阶段改为 provider `low`，原生阶段仍是 Codex CLI medium。模型、验收断言、每轮 16 次/3600 秒、单次 600 秒上限不变。这是推理设置调整，不是网络恢复、代码缺陷修复或验收降级。旧轮次的 request.json 保留实际 requested/mapped 设置。

轮后回归：561 OK (3 skipped)，三个自检全绿，下一轮配置 `--preflight` 通过且为 0 次模型调用，Docker 29.8.2 可用。日志 `E:\Users\27343\Docker\acceptance-run50-postflight-tests.log`。前置回归另有一次耗时 632 秒但最终通过，重复启动的诊断检查在确认原始回归已通过后被停止，不是失败批次重启。

## run51：内容审阅错误要求未来的 Docker 证据

起点 `2ef2694`，构建 `20261028T225012-feeab5d0`，北京时间 22:50:12–22:59:35，预算计数 3，状态 `draft`，尚未到结构化 low 规划或 Docker。独立审阅确认原脚本、依赖和 fixtures 的哈希一致、来源断言有依据，但将“缺少当前轮 Docker 报告”列为 blocking check，返回 supply_evidence；host 正确保留 not_run，没有伪造内容批准。证据：`E:\Users\27343\Docker\acceptance-descriptors-a-run51-20261028\state\outputs\20261028T225012-feeab5d0\records\chem-rdkit-descriptors.json`。

这造成阶段循环：Docker 准备需内容通过，而审阅先索取 Docker 执行证据。轮后在 `generation/author.py` 的 review execution_policy 中明确 review_scope、deferred_to_bound_docker、runtime_evidence_required_for_content_approval=false 和 content_pass_grants_runtime_qualification=false；review.md 明确整个用户验收要求由后续 runtime gate 执行，内容正确且测试定义正确时，未来未执行只记非阻塞 pending finding，不能因此索取本阶段不可能拥有的证据。错误代码、错误断言、缺少来源或已观察到的错误结果仍阻塞；旧的 supply_evidence verdict 也不会被 host 自动转 pass。必须新轮取得独立审阅和最终 Docker 证据。

新增专项回归验证上述边界，尤其证明内容 pass 后没有 Docker 证据仍 blocked，不能进入 accepted。本轮失败不计成功，也未续跑。

轮后验证：564 OK (3 skipped)，三个自检全绿，Docker 29.8.2 可用；日志 `E:\Users\27343\Docker\acceptance-run51-postflight-tests.log`。新的内容审阅提示仍需后续真实轮次验证，不能据离线回归宣布解决了所有模型行为波动。

## run52：审阅边界已走通，检查引文诊断仍不具名

起点 `af9f36c`，构建 `20261028T231003-9e2fda73`，北京时间 23:10:03–23:25:59，预算计数 6，状态 blocked，停止码 planning_no_progress。内容审阅通过，实际请求与发送推理档均为 low；三次规划耗时约 236.8、73.9、77.3 秒，均完成，没有再触发 run50 的超时。本轮仍未到 Docker。

首次诊断指向 direct operation 未引用顶层检查；之后两次都只说 `Input checks require grounded id/channel/key/pattern`，没有指名对象。原始计划离线重放确认：具体失败是 **blank_line** 的 source_quote 用 `...` 拼接文档片段，不逐字匹配 `package/SKILL.md`。其余两条检查引文可以匹配，不能说它们也引用错误。三条 pattern 分别匹配空白/非法 token，另有有效性谓词方向问题，原门禁会在后续覆盖校验中继续拒绝，不允许通过修改判定放行。

轮后改动：输入检查的独立类型、正则和来源问题在一条拒绝中集中报告（最多展示 20 条，并标示剩余数），每条指名 check ID/位置和具体字段；来源失败使用既有 grounding_problem，包含路径或引文首行；保护非字符串 source_path，避免另一个类型崩溃。补充模型可见的既有规则：有效性谓词接受正常输入、拒绝用例不满足所指谓词、正常/非法文件 fixtures 使用同一绑定文件名、检查对象只定义在顶层、引文连续且不拼接。没有改变通过条件或删除用例。

离线重放：`E:\Users\27343\Docker\acceptance-descriptors-a-run52-20261028\input-check-diagnostic-replay.json`，同一原始计划仍被拒绝、0 次模型调用、无业务执行。新回归同时覆盖多个独立检查错误的具名聚合、有效检查仍可通过，以及错误路径类型的干净拒绝。专项 59 项通过；全量与三个自检结果在本轮收尾补入。

轮后验证完成：566 OK (3 skipped)，三个自检全绿，Docker 29.8.2 可用。日志 `E:\Users\27343\Docker\acceptance-run52-postflight-tests.log`。提示与 schema 按 freeze 顺序更新，未改验收含义。

## 独立结果审计

`python validation/deepseek-api/audit_extended_acceptance.py <batch-directory> <scenario>` 在批次结束后检查：冻结输入、实际入口与冻结原脚本字节、prepared/digest、image.id 与报告一致、所有记录 passed、当前严格 Docker 资格、对应场景真实数值/拒绝及退出后文件输出。混合批次需在拒绝行之后仍有有效行输出。不能只看 ready，也不能复制原脚本却用另一入口替代执行。

对于已通过执行的批次，审计器另在**绑定镜像**内用标准库 importlib.metadata 读取依赖版本（不导入或执行化学/几何业务代码、不安装软件、禁用网络），验证描述符原依赖 pins 与 ASE 版本。该环境元数据探测不会调用模型，结果单独保存在批次根目录 acceptance-audit.json，不改写原始运行证据。若审计未通过，不计入四项成功。脚本的只读自检已证明：旧的有效运行证据可被接受，未执行业务的阻塞证据会被拒绝；旧结果不计作新成功。

两个尚未运行的典型场景补充了明确的来源测试数据：原子映射用原始测试的 reactant_only_maps=[3]；几何用两 He 位于 (0,0,0)/(0,0,2)，检查 2.0 Å，并以 target=3.0 验证“检查完成但约束失败”。期望来自预设坐标和来源 API 语义，不从运行结果倒推。
