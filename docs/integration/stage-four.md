# 阶段四交接：持久化恢复、迁移重验与证据更新

固定基线 `52bac06324455d2702e6fa5eac8e81af947a17a0`，独立集成分支
`integration/docker-stage4`，仍使用 `chem-agent-toolkit-integration` 工作区。
开始时 Git 干净，未发现适用 AGENTS.md。只读远端核对仍为 partner
`e117c434f54d11fd24e3e5566f187a8f4a41a87f`，没有切换审阅基线。
旧实现按 Git `d5b77dc` 阅读；原 Docker 项目 92 项历史删除未混入。
未推送、发布或合并远端。阶段三代码、交接和实际证据已核对。

## 复用与迁移映射

| 原有能力 | 本阶段处理 | 保留的行为 / 验证 |
|---|---|---|
| 新版 service.resume_build / prepare_revision、LocalExecutor | 继续调用，增加自动选择和持久化操作记录 | 不发现、不编写；环境变更仍走原 prepare；实际恢复调用记录 |
| 旧 inspect_run.inspect 的输入保护和运行阶段选择 | recovery.inspect_candidate / choose_build 接到同一 service | 区分准备、重建、重验和需审阅，实际来源/镜像核验后决定 |
| 旧 lifecycle.validate(reuse_build) | 复用 build 回执、现有 verify_current 与全套 validate | 已完成镜像可复用，旧用例 pass 不复用；build_failed/execution_failed 真恢复 |
| 旧 relocate_runtime.relocate | recovery.relocate + import_candidate | 先核对字节再改状态，保留历史，撤销继承资格，锁定测试不变；真实 ZIP/安装 envelope 迁移 |
| 旧 lifecycle.reset_observations / archive_execution / invalidate_current | 现有 execution、qualify、catalog 历史字段继续承接 | 历史事实不删除；新尝试、当前资格与当前主机分别记录 |
| 旧 runtime_transaction.commit_generated / preserve_runtime_on_failure | 不复制第二套事务；组合既有 store.commit / recover、独立冻结修订 | staging/backup、Windows 目录替换、失败回滚及保留失败证据 |
| 旧 runtime_package.cleanup_scope | 直接复用 | 清理属于中断 attempt 的本地容器，保留清理回执；真实遗留容器试验 |
| 旧 test_runtime_consistency 的复制/提交/回滚失败场景 | test_runtime_recovery.MigratedTransactionTests | 保留旧文件恢复、新目标移除、回滚失败保留 journal/backup 等关键断言 |
| 旧 test_runtime_hardening 的来源漂移保护 | test_runtime_recovery 的对应场景 | 变化在 Docker/模型调用之前被拒绝，不能继承通过 |

旧运行目录、bindings、发布器和 CLI 不作为依赖。迁移的是恢复判断和不变性保障；
执行、断言、入库、事务仍只有阶段一至三已建立的那套实现。

## 必要增量

- `runtime-resume` 自动选择核验后的构建结果，或重建；继续调用 `resume_build`。
  `runtime-validate/build/prepare` 原入口保留，没有第二套恢复执行器。
- catalog 在 Docker 之前保存 `pending_runtime`。异常退出后归档部分尝试，保留
  stdout/用例/输出/构建诊断；同内容新证据更新 `runtime_history/recovery_history`。
- 显式死锁恢复只处理已退出的本机 PID，保留旧锁；活进程或无法确认退出的锁拒绝接管。
  实测修正了 Windows “进程已退出但句柄仍可打开”的判断，不能把这种句柄当活进程。
- 默认资格增加库路径绑定；当前执行证据还核对 Docker engine ID。路径/主机变化不继承通过。
- `runtime-relocate` 接受完整新版库；`runtime-import` 接受新版输出或安装 runtime envelope。
  首轮入库前中断也有预写恢复记录，可显式转入持久候选区；不要求成功 summary 或完整 bundle。
- 导入始终保留已知内容撤销，不替换已有同名候选，不以历史 execution_passed 自动入正式区。
- 缺资源与接口不支持分开记录。外部数据/权重/凭据即便缺少引用，也同时明确标注传递契约未实现。
- 正常读取型 Skill 迁移只核验来源/内容，不需要 Docker；草稿仍不获得正式资格。

接口、命令、目录和错误语义见 `docs/pipeline/runtime-recovery.md`。

## 实际验证

验证来源是阶段三真实独立审阅过的 RDKit 交付；未修改 Skill、来源、环境计划或锁定断言，
也没有新增模型审阅来重新编写同一 Skill。模型调用禁止断言与实际记录均为 0。

1. 把 Docker 指向不存在的本地管道，产生真实 `runtime_blocked`，持久化候选后删除
   本次创建的临时来源/工作目录；恢复正确端点，仅恢复构建/执行，10 项检查通过并晋升。
   没有停止用户的 Docker daemon 或其他容器；没有用 mock 成功代替执行。
2. 同修订重复运行：复用已核验镜像，执行全部 10 项，catalog 更新为新 attempt，旧证据留存。
3. 工作进程在构建和执行阶段 `os._exit`：退出码 73、遗留真实锁和部分文件；显式恢复死锁，
   根据完整回执选择构建或重验，保留中断尝试，不重新发现/编写。
4. 构建客户端实际超时形成 `build_failed`；环境探针客户端实际超时形成环境类
   `execution_failed`。移除故障后复用仍有效的历史构建、重新验收，源码/契约不变。
   故障注入只改变调用时限，不伪造结果、不放宽断言。内容失败仍须修复与独立审阅。
5. 最终 catalog 写入注入失败：没有错误晋升，catalog/活动目录回滚到持久 pending 状态；
   完成的构建和执行文件仍在，下一次恢复成功。另测回滚本身失败时 journal/backup 留存。
6. 完整库 ZIP 解压到新路径，默认查询不继承 accepted；删除旧库后显式重验，10 项通过。
   冻结修订 ID、freeze hash、来源、环境和验收契约完全相同。
7. 当前安装 runtime envelope 导入新库时先进入 candidates；删除原临时安装目录，
   从新库复用绑定镜像重验，10 项通过；不能因为文件相同忽略新的证据。
8. 强制退出的工作进程留下一个真实、明确归属的运行容器：恢复时用旧 cleanup_scope 移除，
   保留容器 ID/清理日志，再真实重验通过。只操作测试自己创建的带标签容器。
9. 最后再次真实构建/执行，核验新增构建检查容器标签路径；两份持久库的当前/历史/部分证据
   全部重新校验，正式资格有效。当前结果以 `validation/stage4/summary.json` 为准。

测试记录：

- 开始基线：177 项，成功，2 项 POSIX 在 Windows 跳过。
- 全量回归：191 项，成功，2 项 Windows 跳过；收尾改动定向 31 项和 14 项成功。
- Linux 容器内 7 项事务/POSIX 测试成功，覆盖上述跳过项。
- 新增 14 项恢复/迁移/事务测试保留关键断言；现有资源测试只增加“不支持契约”的断言，未删除旧保障。
- `git diff --check` 与提交前持久证据字节核验，防止换行转换破坏冻结指纹。

## 证据和运行边界

`validation/stage4/` 保存：`results.json`、`failed-stage-results.json`、`import-results.json`、
`orphan-results.json`、`final-build.json`、`summary.json`、测试日志，以及两份包含全部必要
冻结输入和运行历史的样例库。`verify_saved.py` 可重新核验；样例库不是默认生产 skills 库。
若移动路径、删除镜像或改变引擎，当前资格应失效，不能把这次 summary 当永久证明。

实际迁移验证在同一主机的不同路径和 ZIP 上完成；引擎身份变化的拒绝有机制测试，
没有宣称已在第二台机器或远程节点实测。远程 GPU、外部资源挂载、凭据传递、服务探测
仍未实现；没有 CPU/mock 替代目标验收或购买算力。GPU 无支持时仍是明确阻塞。

现有 Native 创建 checkpoint/resume 负责发现/编写进度；运行阶段用上述候选恢复入口。
本阶段未改写 Native 调度器，未重复跑完整实时模型发现/编写实验。已冻结内容可以直接
导入恢复，无需依赖已清理的原工作区，也不兼容旧 ZIP/bindings/七章节模板。

阶段四结束，后续阶段继续使用这些接口和统一 catalog；不自动进入下一阶段。
