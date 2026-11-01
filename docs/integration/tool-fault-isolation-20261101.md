# P1-1：完整 ToolArtifact 并发与故障隔离

基线 `48bb4bc`，分支 `pipeline-with-shared-docker`。**本轮约定的本机范围已完成**：
最终真实轮 `tool-fault-isolation-20261101-05` 通过，针对性 53 项及完整 731 项回归
（728 通过、3 跳过）通过，三个提示自检通过。未改模型后端、提示/schema 或预算，无需 freeze。
机器索引见 [tool-fault-isolation-results-20261101.json](../../validation/deepseek-api/tool-fault-isolation-results-20261101.json)。

本轮是 **0 模型的真实 Docker 基础设施实验**，不是新发现/编写/独立审阅的化学 Skill 批次。
使用原有标准库 fixture，追加每轮随机 nonce，使制品、闭包及镜像属于本轮；fixture 的内容门禁
明确标为 deterministic fixture，不冒充原生 Agent 审阅。所有冻结、源码/镜像、锁定用例、
执行及当前 qualify 检查照常执行。P0 两个真实生成描述符 Skill 的完整目录摘要和当前资格
前后不变，保留其原独立审阅证明，没有重新生成或继承资格到新候选。

## 已有覆盖与新增缺口

已有 `test_shared_tool.py` 覆盖 request/recipe/具体身份、记录损坏、daemon/image miss、
所有者锁、构建失败/取消、当前验收及显式版本绑定；`verify_shared_tools.py` 已有线程并发。
交付恢复实验已有真实合同重验，但镜像缺失、daemon 漂移及执行前中断是具名注入，
不能当作本轮要求的实际镜像删除、业务中途打断证明。

本轮新增独立进程竞争、原子 rename 前的实际 tmp 文件观察、持锁时另一进程超时/取消、
实际工具 Docker build 失败/超时/取消、实际业务容器运行中断、专用镜像删除/同身份恢复。
没有用环境层命中代替完整工具层命中。

## 修复

- 嵌套共享环境的 `finally` 原来无条件 `lock.unlink()`。修复前离线回归复现了替换锁被删；
  现在写入 `PID:UUID` token，释放前检查当前 token 和链接，取消不删除已观察到的其他所有者锁。
- `runner.process()` 的取消现在与超时一样终止并等待本进程树，监督式执行还清理自身 scope；
  `runner.run()` 同时保留取消的执行 scope、直接 Docker 容器删除结果与原始异常。
  当前 LocalExecutor 的业务执行直接调用 Docker；没有假设它一定启动外层 runner.py。
- 工具 build/bind 取消仍传播 `KeyboardInterrupt`，但先保存 `caller_cancelled` 和 request_key；
  receipt 保持 `runtime_blocked`，不会虚构已完成构建或资格。锁仍只由原所有者释放。

8 项新增有效回归覆盖替换环境锁、取消等待者、临时记录不可见、工具构建超时不发布、
进程取消/超时清理、无 scope 不清他人容器、直接 Docker 取消证据，以及中断实验 worker
的实际库入口。离线测试的 Docker/模型均有替身或禁止调用。

## 最终真实轮

| 场景 | 确认结果 |
| --- | --- |
| 同一闭包/要求，两个独立 Python 进程 | 两者先各自冻结 miss；工具 build 合计 1，绑定同一 artifact，分别执行 2/2 |
| 发布暂停 | 在真实 `write_json` 已写 tmp、尚未 rename 时暂停；只读 resolver 返回 miss，不读取 tmp |
| 持锁时超时 | 另一进程在原 4 秒 deadline 内失败，0 构建、资格 false，原 token 不变 |
| 持锁时取消 | 独立等待进程收到具名 KeyboardInterrupt 注入，未发布、未删除原锁 |
| 真实工具构建失败 | attempt 内生成 Dockerfile 注入 exit17，Docker build 非零，`build_failed`、资格 false、无登记 |
| 真实工具构建超时 | attempt 内 RUN 延时，原 8 秒 build deadline 产生真实 TimeoutExpired 和进程清理；无登记、资格 false |
| 活跃构建取消 | 真实 build 输出 `P1_BUILD_RUNNING` 后注入 Python KeyboardInterrupt；清理进程，保存 `caller_cancelled`，无登记 |
| 实际镜像丢失 | 只对不在事前镜像集合中的本轮 nonce 镜像先 save 再 rm；resolver miss，已绑定候选零用例执行、资格 false，无替换构建 |
| 同身份恢复 | Docker load 本地归档，原 image ID、artifact 和登记字节不变；另一个全新导入库不继承资格，重新执行 2/2 |
| 业务中途打断 | `docker ps --no-trunc` 观察到实际 `python /opt/skill/package/main.py` 正在运行后注入；pending journal 留存，资格 false |
| 中断容器清理 | 当前回执保存 Job 终止客户端、删除该具体任务容器 exit0；相同 scope 下 `docker ps` 无残留 |
| 中断恢复 | 复制中断库到新目录，新 attempt 重执 2/2；原中断目录完整 manifest 不变 |
| 旧绑定隔离 | 先前 fixture 版本、登记及 P0 A/B 包、来源、库、执行证据的摘要不变；P0 A/B 当前资格均 true |

最终轮完整执行 **10/10**：并发 A/B 各 2、镜像恢复 2、慢工具基线 2、中断恢复 2。
中断 attempt 已完成的环境检查另记为部分观察，不当作完整通过。缺失镜像失败 attempt 零用例；
构建失败/超时/取消与等待失败也不计为通过。当前 build 调用为环境 **0**、工具 **5**，
包含三次故障调用，不是五个成功镜像或五次依赖安装。保留已有 Docker/BuildKit 缓存，不声称冷启动。

具体入口：

```powershell
python -m unittest tests.pipeline.test_fault_experiment tests.pipeline.test_process_cancellation tests.pipeline.test_shared_environment tests.pipeline.test_shared_tool -q
python validation/deepseek-api/verify_tool_fault_isolation.py E:/Users/27343/Docker/tool-fault-isolation-20261101-05
python -m unittest discover -s tests -q
python validation/deepseek-api/verify_prompt_contract.py
python validation/deepseek-api/verify_acceptance_prompt.py check
python validation/deepseek-api/verify_planner.py check
```

复验须换全新证据根，脚本拒绝已存在目录；测试使用工作副本同级的可写 TEMP。
脚本明确禁止 runtime/model 与 native Agent 入口调用；恢复阶段禁止 LocalExecutor.build，
防止偷偷重建缺失具体版本。原 P0 A/B 只读保护源默认是同级 `descriptor-layout-cli-20261101-05`。
`--worker` 是本实验进程入口，参数、PID、脱敏日志、源码快照均保存，不是普通用户 CLI 工作流证明。

## 失败轮不覆盖

- `-01`：离线修复前替换锁回归失败；首次默认临时目录还有沙箱权限错误，随后使用工作区 TEMP
  的日志单独留存，明确复现实际锁删除缺陷，未把权限错误当产品缺陷。
- `-02`：独立进程并发及锁隔离已完成，后续故障配方被原 `code-dependent steps` 协议正确拒绝。
  修正实验方式，改为只向 attempt 生成上下文注入故障；未放宽产品配方协议或改冻结来源。
- `-03`：构建故障及镜像删除/恢复已完成，中断 worker 错读不需要的 fixture record，实验失败。
- `-04`：中断钩子误等外层 runner.py，故障没有注入；实际业务正常完整执行后依法取得资格。
  这不是“中断仍授予资格”的产品失败，也不能计作中断验证成功。补回归，改为观测实际 Docker 调用。
- `-05`：上述修复后的完整独立轮通过。失败轮目录未 resume/restart，未删除失败证据或降低用例。

最终离线日志在 `tool-fault-postflight-20261101-02`；较早 729 项的通过日志单独保留，
不当作最终 731 项证明。所有失败根、成功根及最终测试日志有机器索引和完整文件 SHA256 清单。

## 支持边界

验证的是本机同 daemon 的精确镜像及 cooperative Python 取消/超时；当前主机是 Windows
Python + Docker Desktop Linux/amd64。没有测试断电、OS 强杀整个 pipeline、磁盘满/fsync 持久性，
也没有模拟恶意并发进程在 token 检查与 unlink 之间替换文件。强杀遗留锁不会按年龄自动抢占。
本轮没有引入自动清锁、自动 GC、远端平台或 OCI 制品分发。

Docker save/load 仅用于本轮专用镜像的本地故障备份恢复，不是 pipeline 的可移植 envelope/OCI
交付接口。仍不支持缺镜像时用同配方的新镜像替代已绑定版本；恢复依赖原归档、同 image ID 与
当前 daemon 核验。归档和实验镜像保留作证据，没有清理用户镜像、缓存、全局 Docker/Git 配置。
