# 只读反向引用：实现和真实库验证（2026-11-02）

基线 `e2f4ac6`，分支 `pipeline-with-shared-docker`。新增 `references.query` 本地管理操作，
data 协议 `chem-references/v1`；旧管理封套/CLI 保持兼容。实现只扫描显式库和共享目录，
每次重建内存派生索引，不另建 catalog、执行链或平台服务。

[字段与边界协议](../pipeline/reverse-references.md) ·
[可复核索引](../../validation/reverse-references/results-20261102.json) ·
[普通 CLI 验证程序](../../validation/reverse-references/verify_cli.py)

## 具体实现

工具目标用 request_key/artifact_id，环境目标用 recipe_key/image_id/daemon_id；不会把同一
请求下的不同工具版本、同一配方下的不同实际环境合并。catalog 当前修订、history、未列入
catalog 的冻结快照及所有规范 attempt 目录都可观察。返回具体修订/冻结摘要/路径、catalog
角色、工具及环境版本、attempt、文件证据和扫描范围。

静态关联复用原 shared_tool 的闭包/具体制品校验。首次构建冻结时可能没有具体 artifact，
必须通过绑定同一冻结身份的 receipt 取得具体版本；完整 request、配方、镜像、build-log 与
catalog 已记录的 attempt manifest 都核验。旧自包含 receipt 可形成直接环境引用，不伪造
完整 ToolArtifact。损坏冻结不产生确认绑定，仅保留明确标注的 catalog 声称及错误证据。

不调用 get/reconcile/recover/locked、qualify、执行器或模型。锁/事务/临时发布只报告，不
等待、删除、改写或修复。查询后的目录成员、记录摘要及冻结树复查用于标记 scan_changed，
不承诺跨文件原子快照。只有 filesystem_reads=true；availability/qualification 恒为 null。

查询成功不代表范围完整。显式空目录数组为 not_scanned，指定但缺失/损坏为部分观察；
global_complete 恒为 false。引用只说明潜在依赖，不推导资格或“可删除”；尤其依赖环境
记录缺失不证明派生工具镜像必然无法运行。没有持久索引、删除、GC、镜像操作、HTTP 或远端分发。

## 实际普通 CLI

最终证据目录：`E:/Users/27343/Docker/reverse-references-cli-20261102-03`。
重放须使用不存在的新证据目录：

```powershell
python validation/reverse-references/verify_cli.py E:/operator/new-reference-evidence E:/Users/27343/Docker/scoped-contract-cli-20261102-01 E:/Users/27343/Docker/local-management-cli-20261102-02
```

程序只准备 DTO 并调用 `python -m creation_pipeline manage REQUEST.json`。原始输入精确为：

- `scoped-contract-cli-20261102-01/a/library`、`b/library`：原真实生成 A/B。
- `local-management-cli-20261102-02/a/library`、`b/library`：此前公开导入并重新独立验收的副本。
- `local-management-cli-20261102-02/missing-image-library`：此前镜像观察故障导致执行受阻的库。
- `scoped-contract-cli-20261102-01/shared-tools`、`shared-environments`：对应共享登记。

这里的五个库只包含 **2 个不同 Skill 修订在 5 个库中的绑定副本**，不能写成新生成 5 个
Skill。9 个 attempt 是历史已存在的引用证据；本轮新模型生成、新业务执行、模型调用、环境/
工具构建和 Docker 命令均为 0。Docker guard 仅计数并约束意外调用，没有当前镜像探测或缓存清理。

| 最终操作 | 结果 |
| --- | --- |
| 工具版本反查 | 5 个具体冻结绑定、9 个 attempt；无扫描诊断 |
| 具体环境反查 | 1 个 ToolArtifact 版本、同样 5 个绑定与 9 个 attempt |
| 再次重建索引 | matches 和 index 与上次相同，无原记录修改 |
| 只指定一个库、共享类别留空 | 1 个绑定；登记状态 not_scanned，不发现其他库 |
| 不扫描库、仅共享目录 | 工具存在，绑定列表空且 libraries 明确未扫描，不声称无引用 |
| 同 request 不同 artifact_id / 同 recipe 不同 image_id | 均没有错误匹配；global_complete 仍 false |
| 追加不存在的库 | 保留 5 个已确认绑定，范围不完整，缺失目录未创建 |
| 隔离损坏 catalog | JSONDecodeError 原因与文件摘要，范围不完整 |
| 隔离损坏工具登记 | 不信任该登记，仍保留原冻结/receipt 的 5 个具体引用；明确缺少匹配登记 |
| 指定空环境目录 | 仍能观察 5 个依赖绑定，但明确环境登记不在扫描范围内 |
| 隔离副本上的外来锁与事务 | 保留 1 个绑定，报告 catalog_pending，不恢复或删除 |
| 隔离锁和半成品发布 | 报 publication_pending，不把临时 JSON 当已发布工具 |
| 隔离副本的冻结 JSON 资源漂移 | 该库不产生确认绑定；保留未核验 catalog 声称，报告具体 freeze.files 期望/实际 |

共 14 次普通 CLI 操作，完整请求、stdout、stderr、调用计数、耗时和诊断逐操作保存。
正向全范围查询耗时工具 2.359s、环境 2.244s；这是当前已存在文件上的完整性扫描，期间有
并行离线回归，包含 CLI 启动和重复摘要核验，不作冷启动或性能加速结论。

每次查询前后比较其输入完整 manifest；所有七个原始输入目录开始/结束字节和已有文件
mtime 均相同。故障准备只作用于新证据目录中的副本/记录，不修改原来源、旧失败库、资格、
锁、工具登记或镜像。本轮不调用在线资格查询，因此也不以“重新查询资格”改写旧状态。

## 保留轮次与修复原因

首轮 `reverse-references-cli-20261102-01` 的首次查询如实返回部分结果，但验证断言失败：
扫描器误把 inputs 的内容修订计数限定为 1，拒绝真实 bindings=2。现有
`preparation.rebind` 明确按内容变化递增 version；修复为原正整数计数＋摘要核验，不放宽
delivery/freeze/tool ABI 等真正协议版本。该轮完整操作和 failure-summary.json 保留，原输入
字节保持不变，未 resume 或 restart。

独立新轮 `…-02` 的 14 次操作通过；随后增加嵌套损坏 JSON 与 report 漂移检查，最终代码
再在独立 `…-03` 完成 14 次操作。最终证据只采用 `…-03`，不累计轮次数当验收样例数。
离线初期替身缺 runtime_limits、需要 symlink 权限的问题另在
`reverse-references-offline-20261102-01/initial-notes.json` 保留；使用完整限制及 reparse
观察替身修正测试，没有删弱产品检查。

## 支持边界

当前支持原生 catalog v2、freeze v1、已支持的 ToolArtifact ABI/策略及环境 recipe v1，
并能报告历史和中断 attempt。非规范库布局、绝对/越界/链接引用、缺失或损坏对象都明确报告；
安装信封和原生 output 目录没有自动作为 library 扫描。未验证全主机、远端或多租户范围。
文件观察未签名，不是并发原子快照；不根据关系授予资格、合并版本或推断删除安全性。

最终 `reverse-references-regression-20261102-01` 全套 837 项：834 通过、3 跳过，无失败或
错误；针对性 79 项通过，其中新增反向引用 31 项。三个提示自检和平台接口交叉核验均通过。
完整命令、日志和 SHA256 见本轮证据索引。提示/schema 未改变，未刷新提示 freeze；原管理、
旧自包含交付、恢复和作用域回归继续保留。管理机器操作清单仅增量加入 references.query；
历史证据里的旧清单摘要应按其原提交版本核对，不能拿更新后的工作树替代历史快照。
