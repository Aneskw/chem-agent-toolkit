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
