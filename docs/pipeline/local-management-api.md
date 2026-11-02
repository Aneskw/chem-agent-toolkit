# 本地管理接口 v1

Python：`creation_pipeline.management.dispatch(request)`；CLI：
`python -m creation_pipeline manage REQUEST.json`。`contract()` 返回离线契约清单，对照文件
`validation/local-management/contract-v1.json` 有可执行契约测试。此接口是本地调用方 façade，
不新增 catalog、执行器、构建器、HTTP 服务、远端协议或多租户权限系统。
路径是本机操作者有权访问的绝对、无链接路径；不是可以直接暴露给租户的主机路径接口。

## 版本化封套

```json
{
  "api_version": "chem-local-management/v1",
  "request_id": "operator-001",
  "operation": "tool.availability",
  "params": {
    "registry": "E:/operator/shared-tools",
    "reference": {"request_key": "<64小写hex>", "artifact_id": "<64小写hex>"},
    "offline": true
  }
}
```

placeholder 必须换成具体身份。api_version 必须完全匹配，request_id 是 1–128 字符的 ASCII
字母/数字及 `._:-` 标识（首字符字母/数字）；未知 operation/字段、非 boolean offline 拒绝。
每个成功或失败调用都返回同一封套，接口错误不混入旧 CLI 的原生错误结构：

```json
{
  "api_version": "chem-local-management/v1",
  "request_id": "operator-001",
  "operation": "tool.availability",
  "ok": true,
  "observed_at": "<UTC ISO8601>",
  "data": {"available": null, "availability": "historical_unverified"},
  "error": null,
  "evidence": [{"path": "<本地记录路径>", "kind": "tool_artifact_record", "sha256": "<文件摘要>"}],
  "side_effects": {"docker_observation": false, "builds": false, "model_calls": false}
}
```

上例 data/side_effects 为节选；完整响应始终含清单声明的九个顶层字段。data 是各操作的投影，
native/observation/observations 保留底层结果和 Docker 元数据命令结果，不将其伪装为新的原生状态。
evidence 的 path/kind/sha256 指向实际输入/登记/冻结/attempt 文件；不存在的观察路径 sha256=null。
摘要表示本次读取的文件字节，未签名、未复制，也不构成永久可用性证明。输出使用现有 sanitized/redact。

失败 error 精确含 code/object/field/expected/actual/reason/source_refs/raw。raw 保留底层 reason、
异常类型或原始结构化结果，失配 details 不删除；source_refs 与响应 evidence 对应。
例：selection_failed 的 raw.observation.reason 仍是 selected_request_mismatch，原始
mismatches[field,expected,actual] 全部保留。missing image 的执行错误保留原 receipt/gaps，并指向
当前 attempt 的 report/build-log；不把它改成笼统的可重试网络错误。

基础 code 包括 request_invalid、descriptor_invalid、request_changed、selection_failed、
artifact_invalid、host_unavailable、not_found、lock_conflict、operation_failed、execution_failed、
execution_blocked、cancelled。已有 RuntimeBlocked 的具名 code 如 binding_unresolved、
revision_changed、independent_review_required 继续透传；客户端必须保留不认识的原 code/raw，
不能据此自动重试、加预算或切换后端。

新 CLI：ok=true → exit 0；request_invalid → exit 2；其他错误 → exit 1。
**exit 0/ok=true 只代表操作完成**：resolve miss、镜像 unavailable、qualification=false 和离线
unknown 都可以是成功观察。request_id 仅关联日志，不是幂等键或结果缓存；重复 execute 创建新 attempt。

## 六个操作与调用顺序

| operation | 必需 params | 可选 params | 委托及边界 |
| --- | --- | --- | --- |
| tool.describe | context, entry, declaration | requirements, constraints, runtime_limits, tool_compatibility, caller_constraints | 扫描现有 context/package 与 context/sources/<id>；通过 preparation.bind 从真实字节推导来源映射，再用 shared_tool.describe，不接受客户端自称 identical 的 binding |
| tool.resolve | descriptor, request_key | registry | 重新描述并与上次 request_key 对照，再调用原 resolve；miss 是正常观察，不规划/构建，不绑定 Skill |
| tool.select | descriptor, request_key, reference | registry | 同样重算当前请求，再调用原 select，仅该具体版本；不兼容/缺失/损坏/不可用报 selection_failed，不 fallback |
| tool.availability | reference | registry, offline | read_record 验证具体记录和文件名身份，原 available 检查当前 daemon/image；离线只核验历史记录 |
| skill.execute | library, name, expected_revision, expected_freeze_sha256 | 无 | 原 resume_build(reuse_image=true, allow_diagnosis=false)；锁内重查 revision/freeze；新 attempt 执行当前锁定合同，不构建、不调用模型，不自动诊断/修复 |
| skill.qualification | library, name | offline | 在线原 store.get/reconcile/qualify 的当前结果；离线 catalog/check 的静态历史核验，accepted=null |

descriptor 与 tool.describe 的 params 同形，不能提交任意未经当前材料核验的 request JSON。
context 通常是已准备/冻结的 runtime/context；entry 相对 package。declaration 沿用原完整
shared_tool 声明。runtime_limits 只允许 memory/cpus/pids，走原 planner.options 校验。
v5 tool_compatibility 使用配置形式的 v1 对象，未分类 requirements/constraints 和完整
caller_constraints 仍保守参与工具身份；该操作不接收/编制 skill_contract 或验收计划。
描述只是当前观察，不是原子文件锁或合格 Skill。resolve/select 重算字节能识别调用间漂移；
后续正式准备、冻结和执行仍做原全部核验。

推荐顺序：describe → resolve 或 select → availability（可单独刷新）→ 原 build/runtime-prepare
完成当前内容审阅、当前验收编制及具体绑定 → execute → qualification。
精确选择只返回 binding_persisted=false；真正 SkillBinding 仍由原准备/冻结及 receipt 形成。
本接口不新增注册、自动 bind、工具构建或代替独立内容审阅的捷径。

```json
{
  "api_version": "chem-local-management/v1",
  "request_id": "execute-001",
  "operation": "skill.execute",
  "params": {
    "library": "E:/operator/library",
    "name": "descriptor-rule-screening",
    "expected_revision": "rev-<64小写hex>",
    "expected_freeze_sha256": "<64小写hex>"
  }
}
```

必须先选定具体 revision/freeze，且服务在原 writer lock 内再次核对；不是只在 façade 先检查
然后无条件执行。漂移报 revision_changed，含字段、期望、实际。需诊断/审阅时明确
independent_review_required，不能借独立执行改变业务合同或触发模型费用。
服务还在同一 writer lock 内返回 evidence_snapshot，冻结引用及本次 runtime/pending_runtime
引用据此生成；不能在返回后重新读取 catalog 的最新 attempt 冒充本次执行证据。
中断/执行异常也携带其持锁上下文中的快照。catalog.json 的摘要是响应时读取的目录文件观察，
不承诺与其他进程的新事务形成跨文件原子快照；具体冻结/attempt 引用始终指向本次快照。
无完整已绑定 build 时拒绝；镜像缺失时不重建替换。恢复/新准备仍由旧显式 CLI 授权入口处理。

## built、available、passed、accepted

- built 是原 build receipt 的历史构建事实；本接口不构建。record_verified 只证明当前登记格式/
  指纹有效，不等于本次构建成功，不等于镜像内容已完成执行前全量检查。
- available 是当前目标的观察；工具 resolve/select/availability 检查 daemon/image 元数据，
  原 v2 另检查 executable/plugins/data/rootfs。不是当前 Skill 业务通过，也不是新的绑定。
- passed 只由新实际 execution_passed 映射；当前用例、source/锁定合同/镜像全量核验沿用原执行链。
- accepted 是原当前资格结果；passed=true 仍可 accepted=false。离线返回 null，绝不以历史
  accepted 或 catalog zone 代替当前资格。合法无需执行 Skill 仍由旧资格分支处理，不虚构 passed。

## 查询副作用、取消与兼容

side_effects 声明可能发生的动作，不是精确命令计数。describe 无 Docker/写入；registry 三个
观察操作不建目录/锁/镜像、不写 catalog。在线 v2 探测会创建并清理专属临时容器，所以不能将
所有查询称为完全没有 Docker 副作用。offline availability 不调用 Docker。

在线 qualification 沿用 store.get：会取 catalog 锁、恢复中断事务、reconcile，可能迁移 accepted
到 candidates、更新失效/延期状态和证据观察；Docker 资格核验也可能运行临时探测容器。
离线 qualification 不加锁、不 recover/reconcile、不写目录、没有 Docker；验证静态字节完整性，
historical 明确是历史，不提供当前资格。并发快照没有统一 TTL 或跨操作事务保证。
不存在的 library 查询先拒绝，避免由读操作创建空 catalog。

execute 写 attempt/journal/catalog，可能清理其原服务持有的中断 scope。取消沿用原 runner/service
清理、pending journal 和所有者锁语义；封套报 cancelled 并引用已存在证据，不授予资格。
不自动抢锁、不 resume 失败测试、不删除其他 Skill 或工具版本。request_id 重复不抑制独立执行。

现有 build、runtime-*、library、install、check 的参数、原生输出和默认恢复/模型诊断行为保持。
service 的新增参数默认仍沿用旧行为；仅管理 execute 选择 validation-only 且要求具体版本。
支持旧自包含与已有 v1–v5 工具/交付协议，继续由其现有检查器决定可用性；管理版本不是 Tool ABI。
未来平台可以适配这些本地 DTO，但不能直接将受信路径、无鉴权同步调用当作多租户/HTTP 服务。
