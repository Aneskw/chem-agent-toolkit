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

## run53：用例来源错误逐个反馈，空结果诊断未指名

起点 `b0c9392`，构建 `20261028T234828-c6871646`，北京时间 2026-10-28 23:48:28 至 2026-10-29 00:07:48。状态 blocked、预算计数 12，停止码 planning_no_progress，没有 Docker 构建或业务执行。九次规划尝试依次修复正则格式、四个用例缺少 assertion.source_path 等问题；空文本断言又产生不指名对象的 `Outcome text must be nonempty`，最终 persisted_output_success 仍把 --output 导致的空 stdout 当作业务结果。

轮后修复：独立用例校验集中反馈（最多显示 20 条并注明余数），每条带用例名；断言来源仍须显式提供，不继承父契约；原有非空结果要求不变。文件结果的修复提示指向真实 output_file 内容及 JSON/JSONL 记录谓词，不把空 stdout 变成合法业务断言。补充模型可见字段说明、错误 purpose/kind 类型的干净拒绝。回归覆盖四个缺来源用例与空文件结果同时被拒、补齐来源仍不能通过空结果、真正 JSONL 断言保持可用。原始失败计划只读重放：同一计划仍拒绝，0 次模型调用，无业务执行；见批次根目录 case-contract-diagnostic-replay.json。

另一个未被隐藏的覆盖问题：最终正常文件用例提供 valid.txt，而声明检查绑定 input.txt；离线覆盖校验明确列出两者，仍拒绝，必须由新规划正确绑定实际文件。不得据本轮离线修复声称文件场景已通过。专项 61 项通过；全量回归与三个自检在本轮收尾记录。

轮后验证：568 OK (3 skipped)，三个自检全绿，Docker 29.8.2 可用；日志 `E:\Users\27343\Docker\acceptance-run53-postflight-tests.log`。freeze 顺序已执行。下一轮保持同一描述符义务、后端与预算，使用新目录。

## run54：业务全部通过，版本探针误用模块展示字符串

起点 `4a9b946`，构建 `20261029T002439-7dbd378a`，北京时间 2026-10-29 00:24:39–00:46:27，预算计数 6（三个原生阶段、三次规划），最终 failed。规划 prepared、固定基础镜像 digest、构建成功，image.id 为 `sha256:08f26bae40350181c1aa4cd38cf598b6c4527e42948245c55d39e23741b9d340`。来源与原脚本保持不变。

执行报告 15 条记录中 14 passed：乙醇计算、非法/空白输入拒绝、原始和混合文件持久化、合法文件写出均通过。唯一失败 environment_python_rdkit_versions：执行 `import rdkit; print(rdkit.__version__)` 得到 2024.09.6，计划的 stdout_equals 却从 requirements pin 写成 2024.9.6。未修改锁定测试或旧报告，仍记整轮失败。receipt 仍描述 built 阶段、gaps 为空；实际失败应以 record.runtime.execution_status 和 execution/report.json 为准，不能捏造 gaps 停止码。

失败后只在同一绑定镜像读取标准库发行包元数据（禁网、不运行化学业务、不调用模型、不恢复批次）：rdkit=2024.9.6、numpy=1.26.4、pillow=11.3.0，见根目录 dependency-metadata-diagnosis.json。这说明依赖安装满足原 pins，失败来自探针的版本字符串 oracle。轮后模型说明改为查询 importlib.metadata 的发行包版本，按发布版本语义比较；不同版本仍必须失败，不删除版本检查、不修改通用精确输出比较器，也不注入固定通过字符串。

本轮证据：`E:\Users\27343\Docker\acceptance-descriptors-a-run54-20261029\`。旧轮不计四项新成功，必须新开一轮得到所有记录 passed 和独立审计通过。

轮后：568 OK (3 skipped)，三个自检全绿；日志 `E:\Users\27343\Docker\acceptance-run54-postflight-tests.log`。独立审计拒绝原轮（batch_not_ready、not_all_cases_passed、current_qualification_failed），业务场景额外检查无缺项，见 acceptance-audit.json。本轮 registry 解析成功，基础镜像固定为 `python@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd`，resolved_from=registry；不能将此前网络不可达当成本轮失败原因。

## run55：资源评估引文与缺字段补丁反馈仍不够具体

起点 `25ad422`，构建 `20261029T005455-544251ee`，北京时间 00:54:55–01:05:26，blocked、预算计数 7，没有构建或业务执行。首个计划漏掉脚本路径中的 package/，入口绑定门禁正确拒绝并给出完整路径，随后已修复。resource_assessment 复制原 Dockerfile FROM 行时在 digest 后多了一个字符，逐字来源校验拒绝；旧反馈没指名资源评估字段，也没指出引用文件/引文。两次对象替换补丁试图修改状态，但未保留 source_path 等 schema 必需字段；`Patched plan schema error: 'source_path' is a required property` 又未给对象路径，最终 plan_unresolved 停止。

轮后只改诊断与已有模型说明：resource_assessment 使用 grounding_problem，指名字段、未匹配路径及引文首行；所有计划/补丁 schema 错误附带 JSON Pointer，原始两条补丁现在明确指出 `/plan/resource_assessment`。unknown 状态仍必须保留 schema 字段（不需引文时可为空字符串），必须描述 unresolved，且仍阻塞 Docker，不用它规避资源义务。新增回归证明同一坏引文和缺字段补丁仍被拒，原计划不被就地改写。

原始材料离线重放 `E:\Users\27343\Docker\acceptance-descriptors-a-run55-20261029\resource-diagnostic-replay.json`，0 次模型调用、无业务执行。专项 55 项通过，随后执行全量和三个自检。

轮后：570 OK (3 skipped)，三个自检全绿，日志 `E:\Users\27343\Docker\acceptance-run55-postflight-tests.log`。本轮已停止，不恢复旧状态。另有静态复查发现只读文件输入/JSON stdout 与全局工具写文件门禁冲突，已留纯门禁复现，下一项独立修复会保留真实写文件工具的义务，不能用切换场景或删检查绕开。

## 代码复查：只读文件输入与工具写文件义务分开验证

原 ASE skill 的 SKILL.md 明确：Stdout is JSON，Input files are never changed；入口只有 --request，没有 --output。执行器需要 file_io=true 才允许 /input 只读挂载，但旧覆盖门禁又一律要求业务工具自己写出文件，且不允许捕获 stdout 计作文件证据。这使真实只读文件工具无法同时满足来源契约和通用门禁。纯门禁复现：`E:\Users\27343\Docker\acceptance-review-20261028\readonly-file-coverage-before.json`，没有模型或业务执行，不是新的付费实验。

新增可选执行要求 file_output={mode:read_only_stdout, reason, citations}。只有原始来源逐字引文有效、独立内容审阅另行返回 file_output_assessment=confirmed，且主执行要求也确认后，host 才冻结这一事实并交给规划器；缺引文、unknown/conflict、自证审阅、其他模式一律不能获得此路径。ASE 封套提供原文并接受上述审阅，不硬编码审阅结果。writer 默认规则不变，规划器 acceptance_json 中声明相同字段也无效。

只读路径仍要求 file_io=true、实际 /input fixture、正常业务结果与拒绝覆盖、退出后保留并断言 stdout 报告（output_file + capture_stdout=true）；输入继续以 readonly 挂载，镜像根目录继续只读。任一 operation 的 require_persistence=true 仍只能由工具实际写文件满足，不能由此例外豁免。修复不能改变已冻结的文件输出契约。没有修改原工具脚本、删用例、变弱科学断言或把 stdout 伪称为工具写出的结构文件。

新增机制回归覆盖逐字来源、独立确认、配置/规划权限边界、旧 writer 和 operation 的实际写出要求、真实输入/保留报告/拒绝用例缺项仍失败，以及修复不能改换 scope。它们不是 ASE 业务通过证据；几何场景仍须完整新批次并通过独立审计。

旧 run47 当前只读复核：覆盖仍 complete，镜像本身仍存在，但其 `python@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89` 已不在本机缓存，当前资格校验返回 base_image_unavailable，不能再称“当前复核通过”。这不是新覆盖规则拒绝了 writer，也不是重新执行业务；历史冻结报告保持原样。详见 `E:\Users\27343\Docker\acceptance-review-20261028\run47-after-readonly-contract-audit.json` 与 run47-current-resource-diagnosis.json。新批次必须在当前环境重新满足全部门禁。

本项轮间修复验证：579 OK (3 skipped)，三个自检全绿，ASE 封套 --preflight 配置有效且 0 模型调用；日志 `E:\Users\27343\Docker\acceptance-readonly-contract-regression.log`。尚未运行 ASE 业务，不宣称只读新路径端到端通过。下一真实轮仍按原顺序验证描述符 A。

## run56：旧行为前置校验忽略 acceptance.assertion，诱发包装循环

起点 `cb4438a`，构建 `20261029T012856-e4bf25f3`，北京时间 01:28:56–01:45:26。blocked、预算计数 9，停止码 planning_no_progress，未构建/执行业务。三个文件行为用例本已定义 acceptance.assertion，但前置校验只识别旧 stdout/expected_json_lines 字段或独立 entrypoint，逐个要求补断言。模型采用 sh -c 调用后 cat 文件，避开了旧前置校验，却正确被覆盖门禁排除为非绑定入口。模型恢复默认直接调用后，又触发旧的 `Behavior test valid_file_output requires assertions or explicit test runner`，停止重复诊断。

轮后修复前后置校验不一致：前置校验识别非空 acceptance.assertion 对象，随后照常执行来源、角色、谓词与一致性校验；runner 本来就执行这种断言，没有放行空断言、未读来源或错误业务输出。业务 acceptance 的调用在契约校验中就必须绑定实际入口，包装调用一次具名列出，指出无需 cat（runner 退出后读 output_file）。缺正常覆盖时，也指名已有但缺 acceptance 的正常候选用例及 operation。模型说明补明确 purpose/role 映射。

原始计划重放见 `E:\Users\27343\Docker\acceptance-descriptors-a-run56-20261029\behavior-assertion-replay.json`：初版现在暴露真正的缺断言/角色问题，包装版明确拒绝三个 sh/cat 用例，最终版仍因角色和引文问题拒绝；没有把旧轮改成通过，没有模型或业务执行。回归证明合法完整断言无需重复旧字段、错误输出仍失败、断言缺独立来源仍拒绝、包装调用具名聚合；缺失业务契约补齐前仍不可覆盖。专项 92 项通过，另新增覆盖诊断专项后 46 项通过；随后执行全量和三个自检。

首轮全量 583 项有 1 个错误：新增业务入口校验把一条旧环境元数据探针也当成业务调用。环境层本来不计入 business_args/业务覆盖，修正为只对非环境业务契约执行入口绑定；业务包装仍拒绝。旧全量失败日志保留在 `E:\Users\27343\Docker\acceptance-run56-postflight-tests.log`，修正后专项 115 项通过（2 skipped），另存完整重跑为 acceptance-run56-postflight-fixed-tests.log。三个自检已绿；2026-10-29 上午免费检查发现 Docker 未运行，已按前置约定启动 Desktop，待 daemon 就绪再开下一轮，不恢复 run56。

修正后全量完成：583 OK (3 skipped)，三个自检全绿。操作者随后确认手动开启 Docker；以 daemon 实际版本响应为下一轮启动条件，不把 Desktop 进程存在当作引擎可用。修复提交后仍先运行描述符 A 的全新独立轮。
