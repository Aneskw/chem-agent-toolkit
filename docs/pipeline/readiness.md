# 零模型就绪预检

`python -m creation_pipeline readiness CONFIG` 只读观察现有配置、来源、Docker 及显式指定的工具版本。
普通 build 自动在 NativeSession 创建和推理前执行；本地明确缺口直接返回 phase=readiness、0 模型，
不创建构建状态目录。远端/表格来源未获取时标记 deferred，正常资源获取后再次检查；续接计划和
checkpoint 在恢复来源后、模型前检查。原 `build --preflight` 仍只校验配置，不悄悄改变旧接口。

响应 version=1，status 为 ready/blocked/deferred；checks/gaps 含 object、path、expected、actual、
code、status、reason。model_calls=build_calls=0，qualification=not_granted；ready 仅表示本次观察
未发现已知阻止条件，不证明 provider 授权、模型后续生成内容、构建成功或业务资格。

来源沿用 intake 的保留/凭据排除规则；逐文件读取与摘要、显式文件摘要和有限预算均检查。
声明的 Python 入口、可静态定位的本地 import 与 JSON 文件通过与交付相同的静态检查器。
交付后完整包和来源仍重新进入 describe，不用预检的局部观察代替最终实现闭包。
来源路径与计划包路径不能唯一映射时具名 tool_support_unresolved；不猜测字节兼容。
当前支持直接目录内对应路径；远端或来源表获取尚未完成时返回 source_mapping_pending。

显式 tool_artifact 检查参考身份、记录自洽、已知声明/要求/来源以及当前 daemon/image 元数据。
未显式指定的自动发现仍在当前 Skill 编写、审阅和来源核验之后精确解析，预检不会制造完整命中。
Open Babel 完整 executable/插件/数据/rootfs 检查可能创建隔离容器，预检明确延后该项；后续默认
available/verify_current 的完整核验不变。预检不 pull/build/create/run、修复系统或更改资格。

`readiness --offline` 不调用 Docker；`--mode discover`、`--mode draft` 或 draft_only 配置允许
Docker 缺失并明确 deferred。普通 build 中显式 executable/shared_tool/plan 或 required 执行需求
需要 Docker。无已声明运行需求的编写仍可继续，待真实需求明确后走原运行时门禁。
这些离线路径不能安装一个尚未通过当前业务验收的可执行 Skill。

错误码包括 configuration_invalid、source_unavailable/empty/unreadable/digest_mismatch、
source_budget_exceeded、model_client_unavailable/model_configuration_invalid、docker_unavailable、
tool_support_unresolved、tool_request_mismatch/tool_source_mismatch/tool_artifact_unavailable。
source_acquisition_pending/source_mapping_pending、runtime_deferred、artifact_availability_deferred、
external_identity_deferred 是待核验观察。错误保留具体路径、期望与实际值；证据沿用 redact/write_json。

公开 CLI 证据：`E:/Users/27343/Docker/readiness-cli-20261102-01/results.json`，9 项，0 模型、
0 构建。模拟 Docker 缺失只向子进程设置专用不存在的 DOCKER_HOST，现有 daemon/cache 不变；
模型 executable guard 阻止意外调用。测试不依赖真实模型响应或旧资格。
