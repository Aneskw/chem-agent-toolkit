# Planner 扩展验证：Open Babel 系统依赖与结构文件转换

2026-10-29 操作者追加一个不同 skill 的测试，目的是依据真实失败强化通用 planner。此前四场景验收结果保留，不能用其成功代替本场景。

来源：`chem-agent-toolkit_newpipeline/tools-skills/openbabel/chem-openbabel-convert`，只读，GPL-2.0-or-later。实际入口 `scripts/convert_molecule.py` 必须字节一致；它通过 subprocess 调用真实系统 `obabel`，不是 Python 化学库接口。来源不指定版本，计划必须区分声明依据和推断选择。`examples/output.json` 只是缺少 executable 的历史报告。

验收封套 `validation/deepseek-api/acceptance-openbabel-input.json` 保持混合后端、16 次 admitted 调用、600 秒单次、3600 秒总预算和基础 digest 固定。业务只在 Docker 执行，失败轮不续跑，不改原业务脚本或削弱断言。环境安装网络问题与 planner/业务缺陷分别记录。

本轮必要证据：真实 obabel 与版本；原 CCO 输入转换成 SDF；退出后实际文件含 3 个重原子（2 C + 1 O）及 2 个单键的完整连通记录；保留 JSON/stdout/stderr/exit code；未知 output format 通过原错误分支 exit2、ok:false；输入保持不变。不能假设 Open Babel 会对所有非法 SMILES 返回非零，也不虚构逐行继续处理承诺。

独立审计 `validation/deepseek-api/audit_openbabel_acceptance.py` 复用冻结/镜像/严格资格审计，额外检查原脚本身份、实际 SDF 记录、版本和拒绝证据，不发模型请求或执行业务。

run66 前置：Docker 29.8.2 可用，缓存 Python 3.11 bookworm digest `94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd`；584 OK (3 skipped)，三个自检全绿，封套 preflight 为 configuration_valid / 0 模型调用。日志 `E:\Users\27343\Docker\acceptance-run66-preflight-tests.log`。尚未据此宣称新场景通过。

## run66：原生作者阶段超时，尚未测试 planner

起点 `0272a70`，构建 `20261029T151504-f8b08be0`，状态 incomplete，2 次 admitted 调用。发现阶段约 514 秒，作者约 600.7 秒后停止：`Agent author exceeded 600 seconds; progress retained`。文件保留，但没有完成回执、独立审阅、规划或 Docker 证据；不能将这次原生模型超时归为 planner 缺陷。

来源快照与原始记录在 `E:\Users\27343\Docker\acceptance-openbabel-run66-20261029`。检查保留事件显示作者写交付文件、元数据和测试脚本时超时，未见 Docker 构建。保持 600 秒单次和总预算，不恢复本轮。独立审计补充氧原子度数为 1 的检查以排除 C-O-C；同时明确检查选定未知格式值，避免其他错误误充格式拒绝证据。没有改变原始业务要求或运行中的代码。

轮后：584 OK (3 skipped)，三个自检绿，日志 acceptance-run66-postflight-tests.log。纯静态 SDF 审计检查证明 CCO 接受、COC/只有计数/只有 ok 元数据均拒绝，无模型或化学执行。下一轮 run67 使用全新目录。

## run67：会话中断，未取得完整批次结果

构建 20261029T161601-f0e2fde9。在操作者调整审批及中断会话后，发现阶段日志停止、没有 summary，也没有存活的 Python/Codex 子进程。按中断轮保留目录，不恢复、不计成功；这不是已完成的 planner 调用或 Docker 验收结论。2026-10-29 操作者授权继续自动验收与共享工具层实现，不 push。下一轮使用全新 run68。

## run68：真实 planner 补丁被旧草稿的类型错误阻断

起点 b27d6be，构建 20261029T164109-92dc7404，北京时间 16:41:09–16:56:04，blocked，预算计数 6。内容审阅通过；首版入口相对路径被具名拒绝。首版 acceptance_json.invalid_input 实际是布尔 true。第二次修复已经同时给出正确绝对入口和 /acceptance_json/invalid_input="required"，却仍被旧草稿的类型错误拒绝，最终 plan_unresolved，无镜像或业务执行。

根因不是模型不肯改字段：patch_plan 在比较修复前后分类时调用 _json_field(base)，对已被拒绝的旧数据再做严格类型验证。因此即使 result 已修正也无法通过。修复仅允许读取未接受旧草稿时将 malformed legacy 分类保守视为 required（仍优先保留明确的 per-operation/input_contract 义务）；新 result 严格验证，锁定契约不允许修改，其他结构类型检查仍在，不能把 malformed 变成无证据豁免。

新增 3 项回归：正确修复可应用且旧计划不变；错误结果与锁定修改仍拒绝；malformed 字段不能降级成免验。40 项专项通过，轮后 587 OK (3 skipped)，三个自检绿，日志 acceptance-run68-postflight-tests.log。原始两条补丁离线重放 draft-state-repair-offline-replay.json 已成功应用，0 模型调用、0 业务执行，不改 run68 的失败结论。

操作者追加共享层任务期间，相关代码在独立工作树实现，没有轮内修改 run68 使用的生产实现。下一轮将使用已回归的最新实现与全新 state/library。

run69 前置组合版本：planner 草稿修复与共享依赖环境已合入，599 OK (3 skipped)、三个自检绿。新的 planner 提示明确 source-independent prefix，有显式前缀时可使用共享环境；不改变本样例的业务要求。下一轮全新目录，不恢复 run68。

## run69：共享系统环境与构建成功，非 JSON 文件断言暴露缺口

起点 be02906，构建 20261029T170755-17414ef3，北京时间 17:07:55–17:29:59，failed，10 次 admitted 调用（3 原生、7 规划）。run68 的旧草稿类型补丁问题不再阻断。入口、selector、用途和用例覆盖经反馈后 prepared；真实 Open Babel 系统安装成功，并实际使用新共享环境（recipe b369a43e272b110de7f2e8fddd5b3bf4de03f7965b351344de814244870c9663，环境 image cb50e4d0a1d0bb065ddcf409067c8dfe698d4f0b6c6b90bd62824f1e4beed56d）。最终工具镜像 sha256:2bac54c1475697736028fcee02f37f594e0d2201837d38352be00b785dbdb792。

执行 9 条中 6 passed，3 failed：normal-file-conversion 对 output_file=SDF 使用 kind=json，误读 stdout 的 ok；bound-ethanol-acceptance 自定义解析器把 V2000 所在行的下一行当作计数行而异常；empty-output-path-rejection 实际 exit0/ok:true，与计划假设不同。首次叙述把最后一项归为文档承诺不准确，此处更正：真实引文仅说所有 flags required，没有说字符串值必须非空。required=True 是参数存在约束，不能据此推导非空值拒绝。原脚本必须保持字节一致，不为实验修改行为。

轮后补通用 text_regex 模式：对实际 retained file（无 output_file 时为 stdout）fullmatch，可容忍来源允许的动态 header，但必须匹配业务内容且不能匹配空输出。stdout_contains/json_equals 仍检查实际 stdout。角色、引用、实际入口绑定和所有旧比较器不变；旧 JSON-on-SDF 断言仍失败。6 项回归覆盖双通道、错误结构、空/非法模式、独立来源、包装入口拒绝和 exact stdout 冲突；相关 82 项通过，完整 605 OK (3 skipped)，三个自检绿，日志 acceptance-run69-postflight-tests.log。

保存本轮实际 observations 与 ethanol.sdf 为新的只读补充来源 openbabel-run69-feedback，不复用旧状态或通过标记。它说明真实计数行布局和 empty output 行为，同时明确下一轮必须重新验证所有用户要求。正常 SDF 独立审计也补正 Docker 默认 ENTRYPOINT 不会重复出现在 command 数组中的表示差异；按锁定调用判定实际入口。重放 audit 识别实际乙醇结构、格式拒绝和版本，但整轮仍 passed=false，缺 batch ready/all cases/完整资格，不把旧失败改成通过。

后续全新 run70 将采用这些来源反馈与最新修复；未知格式仍明确为 nonexistent_format_xyz，保留完整转换、文件持久化、输入保护和源脚本不变义务。不 push。

run70 最终前置：合入环境配置校验、双入口提示、具名用途反馈和共享构建失败分类修复后，609 OK (3 skipped)，三个自检与两来源封套 preflight 全绿；日志 acceptance-run70-final-preflight-tests.log。独立 audit 仅在新轮所有证据通过后额外检查绑定镜像内 obabel --version（元数据，不是化学计算或模型探针）。

## run70：首次规划 prepared、命中共享环境，检查隔离与字节投影失败

起点 03f764d，构建 20261029T175137-a863b54c，北京时间 17:51:37–18:06:56，failed，4 次 admitted 调用（3 原生、1 规划）。本次入口提示生效：首个规划直接 prepared，无规划拒绝/修复。构建成功，shared_environment.status=hit，复用 run69 的 b369a43e... 配方与 sha256:cb50e4d0a1d0bb065ddcf409067c8dfe698d4f0b6c6b90bd62824f1e4beed56d 环境，新的工具镜像 sha256:4c8912d335c0b4865f8d064a853e0214d5be9c652827761c156da817dcc9059c。ENV/WORKDIR 与层身份校验均通过。没有复用旧验收标记。

执行 11 条中 5 passed，6 failed。两条计划检查把 CCO+LF 的 input_files 与原始 CCO+CRLF 的摘要比较；正确原始摘要 c5e96abe...，实际 fixture 摘要 5c9aa2a3...。原始摘要未写错：planner.supply 对 raw.decode 结果显式做了 CRLF→LF 归一化，导致材料文本与库存原始 hash 不一致。修复为保留原始 UTF-8 换行；新增回归经实际 planner 输入帧核对 CRLF 字符、库存摘要和 used_chars。

原生声明检查还假设 /input 自动存在、检查间共享 /output：映射后三个检查缺少输入或前一检查文件。各检查本来独立隔离，不能通过共享可变目录绕过。作者/审阅上下文统一声明 fresh container/output、cross_check_state_shared=false，并明确每项自行生产和校验产物或读取 package/source fixture。已有独立审阅回归验证两个阶段收到同一约定。所有五类验证义务保留，下一轮重新生成自包含检查。

正常业务转换再次成功但其计划断言仍把 SDF 当 JSON，整轮维持 failed；调用方实验约束进一步明确该场景文件内容必须用有结构/数值依据的 text_regex，stdout JSON 单独断言，不改通用引擎为工具特例。新增 registered observed_openbabel_run70 来源记录真实 byte/隔离事实；不更改原始脚本、原始期望 hash 或用户要求，不用历史通过记录冒充新执行。

轮后 610 OK (3 skipped)，三个自检绿，日志 acceptance-run70-postflight-tests.log。run71 前还将合入已独立验证的只读共享环境检查命令并做组合回归。run70 不续跑，不推送。

run71 前置已完成：最新组合版本 617 OK (3 skipped)，三个自检及三来源封套 preflight 全绿，日志 acceptance-run71-preflight-tests.log。只读共享环境检查命令已合入。原四成功场景的历史原始证据以当前审计代码重新检查全部通过（prior-four-current-audit-20261029.json）；没有重新执行业务计算或发模型请求。run71 使用全新目录与最新冻结实现。

## run71：11/12，唯一失败是 SDF 正则误拒末尾换行

起点 b9f6ebc，构建 20261029T183610-192d1953，北京时间 18:36:10–18:52:34，failed，7 次 admitted 调用（3 原生、4 规划）。前三次规划依次拒绝资源评估引用删去 Markdown tokens、输入策略引用不精确、真正 tests[].case_json 缺验收契约（模型误写到 acceptance_json.operations[].cases）；第四次 prepared。首条诊断已具名，第二条仍是旧泛化文本 `Input policy requires scope and an exact quotation from read source`。

Docker 构建成功，固定 python@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd（本轮 resolved_from=registry），最终镜像 sha256:c560f20869ee268c8c5c2a45d8aa1fd967bdaa0c3e683ecd5442f8adb7e1026c。共享环境 status=built，recipe 27ec05ccc4a1fe0992848949f137739a0ce0d5bb49fb3cbbe5873a555b79f1eb，环境镜像 sha256:4edfe724d5d68c9b45e4908b5b4fd6d58666fdb09f1aa4b6a8d914bd170831d5。本轮安装命令与 run69/70 不完全相同，精确配方协议产生新键是预期行为，不能声称本轮 hit 或已经实现语义兼容合并。

12 条记录中 11 passed。所有六条原生检查的映射执行通过，计划中的原生自包含检查也通过：正确 CRLF、源/入口字节一致、before/after hash、真实版本、CCO 结构及未知格式拒绝均有实际证据。唯一失败 normal-direct-entry 实际 exit0/ok:true，331 字节 SDF 有效。其 fullmatch 正则在 $$$$ 后立即结束，实际 retained file 以 $$$$+LF 结束。终端换行被误拒，并非业务转换缺陷；不修改原脚本/输入、不让 runner trim、更不把失败轮改成通过。

独立 acceptance-audit.json 识别实际乙醇 SDF、版本和格式拒绝，整体仍 passed=false，缺 batch ready、全用例 passed 与完整资格。terminal-newline-offline-replay.json 用留存文本证明去掉最终 LF 才匹配，仅离线字符串比较；text-regex-diagnostic-offline-replay.json 用模拟调用重放原失败，证明新增诊断可指名用例、文件、模式和真实文本尾部，0 模型/0 业务执行。

轮后补具名策略引用诊断（3 项回归），以及文本正则失败的通道/文件/模式/尾部诊断（2 项回归）；所有原比较规则保留。新增 registered observed_openbabel_run71 来源保存原 SDF 与末尾字节事实，后续必须重新执行全部义务；不预置通过标记。新轮封套进一步明确真实用例契约放 tests[].case_json，引用保留实际 Markdown tokens。轮后 **622 OK (3 skipped)**，日志 acceptance-run71-postflight-tests.log；三个自检及四来源封套 preflight 全绿。下一轮全新 run72，不续跑、不推送。

## run72：正常文件断言与全部原生检查通过，两个额外改写检查失败

起点 fd40432，构建 20261029T190019-038f4841，北京时间 19:00:19–19:15:49，failed，5 次 admitted 调用（3 原生、2 规划）。首个规划引用 `The complete normal invocation is:` 不在实际 package/SKILL.md 中，具名诊断指出对象与首行；第二次 prepared。本轮固定基础 digest 不变，最终工具镜像 sha256:72d13e10ccb191c751b9aa86c44df840509af9378ac230be7154c806bd1da8c6，shared_environment.status=hit，复用 b369a43e... 与环境 sha256:cb50e4d0a1d0bb065ddcf409067c8dfe698d4f0b6c6b90bd62824f1e4beed56d。

执行 11 条中 9 passed：正常直接转换的 text_regex 已正确匹配留存 SDF（不再误拒最终 LF）、未知格式拒绝、环境检查，以及全部五条原生检查的原样映射均通过。额外三个 planner 自写 native-* 检查中两个失败：native-real-obabel-and-baseline 实际 exit0、pass:true、Python 3.11.18，却要求精确子串 `"python": "3.11"`（含结束引号）；native-retained-ethanol-structure 要求 counts 行前三个 split 数为 3,3,2，实际是 3,2,0。原版作者结构检查对同一输出正确通过，原脚本/输入及结构义务没有缺失。

这是两项额外测试谓词/程序错误，不能据此宣称业务实现缺陷，也不能跳过两项后把 run72 改成成功。独立 audit 识别正确 SDF、版本与拒绝；missing 为 batch_not_ready、not_all_cases_passed、current_qualification_failed，整体 passed=false。核心业务契约 complete 不代表全部执行记录通过。原生检查摘要确实只提供截断 argv，模型是否逐字依据其复写无法从返回值确定；改写与原程序不同、计数和版本断言错误则有直接证据。

轮后改进：原生摘要显式 argv_preview/preview_only/automatically_mapped，统一说明原程序及断言由执行器原样映射，规划器不能从预览猜测替代程序；仍须自建符合门禁的直接 normal/rejection 用例，所有原生检查及五类义务保留。新增回归确认截断预览不会替换实际完整程序。stdout_contains 失败增加具名 missing_literals 诊断，保持精确比较；stdout-literal-diagnostic-offline-replay.json 用原 case/stdout 重放失败，无模型、Docker 或业务调用。

此前在独立工作树开发的正则正例预检已在本轮结束后合入：可选 example_source_path 必须来自已读输出样例，模式必须匹配；四项回归及 run71 留存数据重放通过。它不授予执行成功、不放松业务内容，也不是 run72 轮内生效的代码。新增 registered observed_openbabel_run72 保存真实版本、counts 和错误谓词，下一轮重新执行全部义务。轮后 **628 OK (3 skipped)**，日志 acceptance-run72-postflight-tests.log；三个自检与五来源封套 preflight 全绿。下一轮全新 run73，不恢复失败轮，不 push。

## run73：8/9，原生检查与正则预检生效，旧比较协议缺口被实测触发

起点 eb29042，构建 20261029T192234-686f929a，北京时间 19:22:34–19:36:30，failed，6 次 admitted 调用（3 原生、3 规划）。首版 top-level invalid_input 错写成对象，per-operation aggregate 已是 required；第一次补丁仍给对象，被类型诊断拒绝，下一次改为 required 字符串后 prepared。不能把这次正确拒绝误判为 run68 的旧草稿补丁漏洞复发。

基础固定 digest 不变，shared_environment.status=hit，复用 b369a43e...；最终镜像 sha256:ce98766b5c5595a9d1df9da82978758caa51f92f820080697b9b4d8f56cb55ad。执行 9 条中 8 passed：环境、help、正常 SDF 与全部五项原生检查通过。规划器没有再重构原生程序，正常模式显式声明 example_source_path=sources/observed_openbabel_run71/observed-ethanol.sdf，正例门禁通过，当前新产物的结构模式也通过；这是本轮实际使用新预检，不是离线模拟。

唯一失败 unknown-output-format-rejection 实际 exit2，stdout 的 ok:false、error="obabel: cannot write output format!"、exit_code:1 与期望原始字符串完全相同，包括最终 LF。然而旧 runner 的 kind=stdout_equals 实现是 text.strip()==expected_value，只 strip 实际值；带首尾空白的 expected_value 对任何输出均不可能满足。这是比较协议披露/预检不足，不能简单归为模型未引用来源，也不是原工具拒绝失败。保留旧比较语义；新增锁定前可满足性校验，指名 case、stdout_equals.value 与真实规则，外层 case.stdout_equals 同样处理。空白敏感协议仍可用严格 text_regex 验证；JSON 方案必须保留全部原始业务值，不删除 ok/error/exit_code 或降低拒绝要求。

stripped-equality-preflight-offline-replay.json 使用原 case/stdout 证明原始二者相等、旧比较仍 false、新门禁可在冻结前具名拒绝；0 模型、Docker 或业务执行，不修改旧锁定数据或失败结论。独立 audit 仍 passed=false（batch_not_ready、not_all_cases_passed、acceptance_incomplete、current_qualification_failed）。新封套保留五来源，比较规则来自框架自身，既有 run69 原始 stdout 已完整提供拒绝值，无需为同一数据增加来源。

轮内另在独立工作树修复结构化回执汇总：旧 summary 错标原生模型且缺 usage，实际详细 DeepSeek 回执正确；新实现将已准入的同一 ticket 绑定实际 provider receipt，保留预算规则、原始 token 键和费用范围，参见 ../pipeline/model-call-accounting.md。此修复在 run73 结束后合入，不能声称本轮已经使用新汇总。轮后 **635 OK (3 skipped)**，三个自检与五来源封套 preflight 全绿；日志 acceptance-run73-postflight-tests.log。下一轮全新 run74，不恢复、不 push。

原四成功场景以当前代码（5895eec）的严格资格/镜像元数据审计仍全部通过：prior-four-current-audit-after-run73-20261029.json，各原目录保存 current-audit-after-run73-fixes.json。此为留存原始证据复核，不是四个新的生成或业务执行批次，不发模型请求。

## run74：8/8，全链路与当前严格资格通过

起点 c103bc1，构建 20261029T194522-1929c499，北京时间 19:45:22–20:00:28，ready，6 次准入调用（3 原生、3 规划）。首版两条引用未保留原 Markdown tokens，具名诊断修正；第二版 output_format_supported 检查错指 args[4]（flag），诊断明确指出 pattern/用例/索引，改指实际值 args[5] 后 prepared。没有轮内编辑、失败后 resume 或第二次构建。

固定 python@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd；共享环境 hit b369a43e... / sha256:cb50e4d0a1d0bb065ddcf409067c8dfe698d4f0b6c6b90bd62824f1e4beed56d。最终 image.id=sha256:a65227fdd4f7f501348dffa9653b4b50bea320362ffa4604ee4ec338e4100f1a。构建、环境继承与 package 字节核验通过。

execution/report.json 全部 8 条 passed：环境版本、正常直接 SDF 转换、未知格式拒绝，以及五项原生检查。原入口/原始 CCO+CRLF 不变；实际 SDF 有 3 个重原子（2 C、1 O）、2 个单键和 C-C-O 拓扑/完整终止记录，容器退出后文件保留。拒绝实际 exit2，ok:false、error 与上游 exit_code 均保留。acceptance.complete/coverage_complete=true，无 gaps/blockers，scientific_correctness=not_evaluated。

独立审计首次进入版本探针分支，暴露审计脚本误用 obabel --version：它打印版本但因缺输入退出 1。保存 acceptance-audit-before-version-flag-fix.json，改为与来源/已通过用例一致的 -V；仍要求 exit0 和真实版本内容。只重做独立元数据审计，不重做业务或模型调用。acceptance-audit.json 最终 passed:true、missing:[]。正式库 accepted/chem-openbabel-convert 当前 qualification.accepted=true；冻结 bundle、镜像及库资格复核保存在 current-audit-after-run74-fixes.json / current-library-inspection-after-run74-fixes.json。

新结构化回执汇总在本轮实际生效：3 条 runtime_planning 正确显示 deepseek_api/deepseek-v4-pro、耗时、原始 usage、request_count=1；native 三阶段仍显示 gpt-6-astra。usage_fully_reported=true 的范围仅是已准入调用回执，不宣称全部底层 vendor requests/重试计费完整。

轮后合入隔离开发的聚合类型具名诊断与原生未知字段拒绝。后者静态反例表明旧映射会丢掉不支持的额外断言，现保留约束并要求正确表达；合法 candidate 路由字段经回归补齐。五个成功批次的全部 30 项原生声明符合新契约，当前映射与原锁定完全一致，没有改旧用例。最新主分支 **639 OK (3 skipped)**、三个自检全绿，日志 acceptance-run74-postflight-tests.log。总索引 current-acceptance-results.json 为五批次/72 条 passed，旧失败记录保留，不 push。当前范围与共享层边界见 current-acceptance-20261029.md。
