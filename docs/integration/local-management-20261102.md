# 本地管理接口：实现与验证（2026-11-02）

基线 `96fa7d0`，分支 `pipeline-with-shared-docker`。新增 `chem-local-management/v1` 本地
Python/CLI façade，复用现有来源绑定、共享工具登记、store、resume_build、执行器及 qualify。
没有第二条执行链，没有 HTTP、远端仓库、OCI 分发或多租户系统；只本地提交。

接口及完整示例见 [协议](../pipeline/local-management-api.md)，机器契约见
[contract-v1.json](../../validation/local-management/contract-v1.json)，本轮可复核索引见
[results-20261102.json](../../validation/local-management/results-20261102.json)。

## 实现边界

| 操作 | 结果与约束 |
| --- | --- |
| tool.describe | 从真实 package/sources 推导来源映射和精确请求；不接受客户端自行注入 binding |
| tool.resolve | 重算请求后调用原精确解析；miss 是观察，不构建、不绑定、不授予资格 |
| tool.select | 指定 request_key/artifact_id，只选该版本；不兼容具名失败，不自动 fallback |
| tool.availability | 原当前 daemon/image 检查；offline 仅历史登记完整性，available=null |
| skill.execute | 必须指定 revision/freeze，原 writer lock 内再次核对；原锁定用例创建新 attempt；不构建、不自动诊断、不调用模型 |
| skill.qualification | 在线原 get/reconcile/qualify；离线只检查静态历史，当前 accepted=null |

版本化封套同时定义九个响应字段、八个错误字段、原始 reason/raw 及文件摘要引用。
built 是历史 build receipt；available 是当前目标观察；passed 是本次实际用例结果；
accepted 是原当前资格，四者互不代替。退出码 0 表示观察/操作完成，不能替代查看资格字段。
在线资格查询可能恢复 catalog 事务、协调失效状态或移动 accepted/candidates；v2 外部工具
可用性检查可能启动专属临时探测容器，均明示副作用。离线查询不授予当前资格。

执行证据有一处实质修复：服务在原 writer lock 内返回当前冻结/attempt 快照，异常/中断也保留
对应快照；façade 不在返回后从可能已更新的 catalog 读取其他执行的 attempt。单元测试模拟
catalog 已指向后一次执行，响应仍引用自己的 receipt；真实 CLI 再检查每次响应的 receipt
及 evidence_snapshot 与该次执行路径一致。catalog 文件摘要只是响应时的观察，未承诺跨文件
原子事务或永久可用性。旧 service 默认不返回新增快照，旧 CLI 原生输出保持兼容。

## 普通 CLI 与实际 Docker

最终新目录：`E:/Users/27343/Docker/local-management-cli-20261102-02`。
复用基线已真实生成的 v5 描述符/JSON 资源 Skill A `rdkit-descriptor-rule-screening` 与
B `descriptor-rule-screening`，来源为 `scoped-contract-cli-20261102-01`。本轮是已有合同重新
验收及管理接口基础设施实验，**没有新增模型生成批次**，不把历史审阅或模型调用算作本轮执行。

普通调用入口全部是 `python -m creation_pipeline manage REQUEST.json`，旧导入/查询入口
另使用 `runtime-import`、`runtime-inspect`。可重放步骤：

```powershell
python validation/local-management/verify_cli.py E:/operator/new-evidence-directory E:/Users/27343/Docker/scoped-contract-cli-20261102-01
```

第一个参数必须不存在。脚本仅准备请求 DTO、调用公开 CLI、读取回执与计数，不注入 catalog、
binding、acceptance_plan 或资格。编译专属 guard 代理真实 Docker，仅计数/阻止模型和构建；
负向镜像实验在确切 inspect 边界返回不存在，不删除真实镜像。成功业务用例全部实际在 Docker 执行。

实际操作顺序：describe → resolve → select → 在线/离线 availability → 新隔离 library 导入 →
在线/离线 qualification → 错 revision 拒绝 → execute → qualification → 旧 runtime-inspect。
A 用相同 request_id 再执行一次，证明 correlation 标识不复用旧执行。每次导入后的当前资格
为 false，重新实际执行后才为 true；保留原冻结的独立审阅和当前合同，未改弱用例。

| 项目 | 最终观测 |
| --- | --- |
| 公开 CLI 操作 | 30 次，包括旧 CLI 兼容与负向路径 |
| 独立 Docker 执行 | A 17/17、A 再次 17/17、B 17/17；合计 51/51 |
| 模型/构建调用 | 全部操作累计均为 0；guard 台账逐操作检查 |
| 具体工具 | A/B 同一 request_key `4ff3ae19…`、artifact_id `7030f864…`；完整身份在请求/原始回执 |
| 新 attempt | 3 个不同目录，同一 A request_id 也产生不同 attempt |
| 原 Skill / registry | 开始/结束完整 manifest 相同，旧绑定与登记未修改 |

执行封装耗时 A=32.049s、A 再次=35.478s、B=31.765s，包含原输入/镜像核验、业务用例及资格
检查。属于当前已预热镜像/缓存上的操作记录，不是冷启动性能或新一轮生成加速结论；没有清缓存。

## 负向结果与保留证据

- A/B 错 revision 均 exit 1 / revision_changed，包含 expected/actual 与冻结证据；未执行业务。
- 改变未分类约束后指定旧具体版本，exit 1 / selection_failed，保留底层
  selected_request_mismatch、全部 mismatch 与原登记/输入引用；不 fallback。
- 未知 API 版本 exit 2 / request_invalid，不调用模型、构建或业务执行。
- 独立 `missing-image-library` 导入后，在该 image inspect 边界注入缺失，exit 1 /
  execution_blocked；新 report 没有业务 cases，当前资格为 false。未重跑或修复该失败目录，
  真实镜像、A/B 及原 registry 均保留。此处是受控故障边界注入，不能冒称真的删除镜像实验。
- `local-management-cli-extra-20261102-01` 仅创建隔离损坏 catalog，公开离线资格查询 exit 1，
  raw 保留 JSONDecodeError，evidence 含该损坏文件 SHA256，Docker/模型调用均为 0。
- 单元测试另覆盖未建目录、损坏登记、daemon 漂移、取消、锁内 revision 漂移、离线不恢复、
  passed=true/accepted=false、禁止自动诊断及兼容旧默认诊断路径。

原型轮 `local-management-cli-20261102-01` 同样 51/51，保留但不叠加为最终轮验收数字。
它早于持锁证据快照修复；最终证明使用独立新目录 `…-02`。离线初期测试替身缺 evidence 字段和
错误测试模块名的失败说明保存在 `local-management-regression-20261102-01/initial-fixture-notes.json`，
未通过放松产品校验消除失败。早期完整回归目录也保留，不代替最终代码证据。

## 回归与限制

最终 `local-management-regression-20261102-03`：806 项，803 通过、3 跳过，无失败/错误；
管理/恢复/作用域针对性 48 项通过，其中新增管理接口 20 项。三个提示自检及平台契约交叉核验
全部通过，没有修改提示/schema 或刷新 freeze。全套保留旧自包含模式回归。

当前只支持本机受信操作者的绝对无链接路径和同步调用。查询没有 TTL、跨操作原子快照或
多租户授权；不把本机 Docker image ID 称为 OCI manifest digest。describe/select 不持久化
SkillBinding，不编写新验收合同；新生成仍走原完整审阅与验收阶段。管理 execute 只执行已有
完整绑定和冻结合同，缺 build、需诊断/审阅或制品不一致时阻止；修复/重建用已有显式入口。
本轮未重新付费生成新 Skill，也未重复验证所有历史 ABI 的真实 Docker 交付路径；这些边界
由原协议检查和全套回归保留，不能从本轮 v5 对照外推远端或任意工具兼容。
