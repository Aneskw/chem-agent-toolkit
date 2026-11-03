# 分支发布前复查（2026-11-03）

用户确认推送至现有 `origin/pipeline-with-shared-docker`。复查起点 `b759408`，工作区干净；
远端 `b5ad543` 为其祖先，22 个本地提交正常快进发布，没有 force push 或修改其他分支。

重新运行本轮 Windows/Python 3.14 离线检查：859 项，856 通过、3 跳过、无失败或错误；
unittest 本体 473.811 秒。三个提示自检、平台契约、83 份证据字节核验全部通过。
检查 71 个 Python 文件语法、待发布历史的 384 个新 blob、当前 1119 个跟踪文件；
未发现实际私有凭据或待清理的字节码/环境文件。令牌格式扫描仅命中测试中的纯数字占位符。
本轮没有付费模型调用、环境或工具构建，没有改变原来源、预算、验收或资格门禁。

源码 ZIP 的 Git commit 注释、SHA-256、安装入口、相对配置及无多余临时成员均复核通过。
旧 ZIP 对应 b759408；工作流修复后的新 ZIP 按最终提交单独命名，不覆盖旧证据。
忽略目录 .env、.pipeline、validation/deepseek-api/runs 是凭据或运行/失败证据，未删除、
未加入 Git。没有清理 Docker 数据、其他工作副本、共享制品或本机全局缓存。

## GitHub 首轮校验与修复

正常推送 b759408 后，GitHub [首轮运行](https://github.com/Aneskw/chem-agent-toolkit/actions/runs/41479254046)
立即失败、jobs=0。具体错误：offline.yml 第 20 行 job env 中的 `runner.temp` 上下文不受
支持；本地 YAML 语法解析未覆盖 GitHub 表达式上下文，不能代替远端工作流校验。

工作流改为 setup-python 后的 Python 步骤：从 RUNNER_TEMP 创建新的空目录，再通过
GITHUB_ENV 设置后续 CODEX_HOME；不存在 job 级 runner 表达式。含空格路径的本地实测
确认绝对路径、目录为空；重复目录明确拒绝，不借用账号认证、不删除旧目录。
不修改生产执行链或测试用例。首轮失败保留，新提交触发独立运行，不重跑失败轮。

修复后的 Windows/Linux × Python 3.11/3.14 四个任务以
[分支 Actions](https://github.com/Aneskw/chem-agent-toolkit/actions?query=branch%3Apipeline-with-shared-docker)
实际状态为准，本文件不提前将其记为通过。

本轮本地日志、检查结果及首轮 CI 原因见
[证据索引](../../validation/publication/results-20261103.json)。发布不会使新用户继承原有资格；
新电脑仍需准备自己的客户端/认证、支持的 Docker 平台，并完成第一次独立验收。

## 第二轮 Linux 诊断

b857b21 的运行 41480049712：Windows/Python 3.11、3.14 均通过完整 859 项及后续自检；
Ubuntu 两个任务均有 GitHub 注释确认超出原 20 分钟上限，取消后日志端点仍缺失，尚未
确定具体阻塞点。没有将其记为通过，也没有放宽超时或重跑失败轮。

下一独立轮仅为 CI 增加监管与诊断：validation/run_offline_suite.py 复用既有 runner.process
在独立进程会话中运行原 unittest discovery，输出详细用例名，每 120 秒输出线程栈；
测试进程上限 18 分钟，低于原 job 的 20 分钟。保留退出码，超时清理自有进程组，拒绝在
业务执行 scope 内启动。正常/失败/超时的本地短进程检查通过；原生产链和用例均未改变。
新一轮真实结果仍以 Actions 为准。
[诊断证据](../../validation/publication/ci-diagnostic-20261103.json) 保留上轮注释与取消记录。

检查过程中本机 Docker daemon 当前不可用，未尝试修复系统或清理缓存；本轮未新增
Docker 业务验收，源码包解压/CLI 预检与离线回归不依赖其可用。
