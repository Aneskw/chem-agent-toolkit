# 分支发布前复查（2026-11-03）

用户授权发布至现有 origin/pipeline-with-shared-docker；本轮正常快进，没有 force push、
改写历史、修改主分支或发布远端服务。原来源、模型后端、预算、独立审阅、验收及资格门禁保留。

## 已定位并修复

1. GitHub 工作流原先在 job env 引用不支持的 runner.temp，首轮 jobs=0。现从步骤的
   RUNNER_TEMP 创建独立空目录，再通过 GITHUB_ENV 设置 CODEX_HOME，不复制任何认证。
2. 取消回归的 MagicMock 未指定 pid，其整数索引为 1。测试只 mock 了 stop_process_tree，
   漏掉 runner.process 的 finally 中真实 os.killpg，导致 Linux 托管任务及日志收集器被影响。
   现在使用具体假 PID，并在系统信号边界 mock，继续核对原取消/超时异常、scope 与清理记录。
3. 生产清理加入共用组信号门禁：只接受具体 int、PID>1，拒绝调用者自身进程组；本机校验
   terminate_tree 与独立可携带 runner 都调用同一门禁。正常的新会话子组仍按原语义终止。
   两项新回归覆盖保留/强转/自身组拒绝及合法子组的原信号参数，没有删除原断言。

Linux libc 将 killpg 的组参数取负传给 kill；参数为 1 会进入 kill(-1) 的权限范围广播
语义，不能作为安全替身。[killpg 手册](https://man7.org/linux/man-pages/man2/killpg.2.html)、
[kill 手册](https://man7.org/linux/man-pages/man2/kill.2.html)。受控 POSIX 命名空间对照只用
mock 原语：旧版调用 1 次，参数整数索引 1；新版调用 0 次并报告具体 PID 错误。
没有在真实用户进程上重放危险信号。Windows 分支使用 Job Object；PID 隔离容器中的
PID 1/调用进程例外可能掩盖同一缺口，因此此前通过不替代本轮修复证明。

## 最终检查与范围

本轮最终针对性、完整回归、三个提示自检、平台契约及逐文件证据摘要见
[修复证据索引](../../validation/publication/signal-guard-results-20261103.json)。
执行中使用新目录，去掉真实模型认证和客户端 PATH，没有付费模型调用、Docker 环境或
工具构建，没有借用旧 accepted。
最终本地全套 **861 项：858 通过、3 跳过**；针对性 **50 项：49 通过、1 跳过**；
三个提示自检、平台契约和原 83 份交付证据字节核验均通过。没有改动提示/schema 或刷新 freeze。

GitHub CI 继续 Windows/ubuntu-latest × Python 3.11/3.14 的原完整发现集合；新增的
测试监管器复用现有 runner.process，用独立会话运行 unittest，保留真实退出码和线程栈，
内部 18 分钟截止低于原 job 20 分钟。其子进程成功/失败/超时和 POSIX 自有组边界会先自检。
临时 72 模块诊断工作流、单用例探针和临时 --module 参数已删除；没有用拆分结果替代完整
回归，也没有通过更换发行版消除失败。实际远端结果以
[分支 Actions](https://github.com/Aneskw/chem-agent-toolkit/actions?query=branch%3Apipeline-with-shared-docker)
对应修复提交为准，不提前把尚未完成的 CI 写成成功。

本机 Docker daemon 当前未运行；普通 CLI 的新目录验证确认 doctor 明确返回
Docker/docker_unavailable，模型和构建计数均为 0、qualification=not_granted。
未修复系统或清理现有镜像，没有新增 Docker 业务验收。新电脑仍需自己的兼容客户端、
认证/模型权限及 Linux/amd64 Docker，随后完成第一次独立审阅和当前资格检查。

## 失败记录与清理

- [41479254046](https://github.com/Aneskw/chem-agent-toolkit/actions/runs/41479254046)：工作流上下文错误，jobs=0。
- [41480049712](https://github.com/Aneskw/chem-agent-toolkit/actions/runs/41480049712)、
  [41555115730](https://github.com/Aneskw/chem-agent-toolkit/actions/runs/41555115730)：Windows 通过，Linux 超时/取消且日志缺失。
- [41557790125](https://github.com/Aneskw/chem-agent-toolkit/actions/runs/41557790125)：Ubuntu 24.04 对照同样出现问题，未认定发行版根因。
- 临时模块诊断先停留在策略用例附近；原五个用例、整模块、runpy/计时器和初始监管调用均
  单独通过，后续元数据将范围定位到进程取消回归。早期环境假设不是最终结论。
- 已过时运行先保存状态再取消，失败轮未 resume/restart；修复后使用新提交独立运行。
  [原发布审查](../../validation/publication/results-20261103.json)、
  [中间诊断](../../validation/publication/ci-diagnostic-20261103.json)及
  [平台对照](../../validation/publication/ci-platform-comparison-20261103.json)是当时快照，保留未覆盖。

待发布历史曾核验 384 个新增 blob、1119 个跟踪文件，未发现真实凭据。旧包按提交名保留；
最终源码包从最终 Git 提交另行生成并解压核验。不将 .env、.pipeline、venv、字节码、
运行库或缓存镜像打包。不删除凭据、运行/失败证据、其他工作副本、共享制品或全局缓存。
