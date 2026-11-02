# 批量创建前审查（2026-11-02）

基线 `b4f809a`，分支 `pipeline-with-shared-docker`，初始工作区干净。用户授权原配置
`validation/scoped-contracts/skill-a.json` 的 **1 个 Skill 首轮验证**，保持 Codex 与
16/600/3600/2400 封套，新建运行/库/证据，不改来源、不 push。

## 已确认并修复

1. stop_on_runtime_failure 原先只退出当前 Skill 的修复循环，仍编写下一项。现在首次
   build_failed/execution_failed 后停止批次，保留现有记录，剩余已选项 deferred，
   CLI/summary 附具体候选和原因；关闭开关仍继续独立候选。
2. 运行时模型 guard 原先只记内存，NativeSession 的检查点可能少记该轮开销。现在请求前
   写原 agent-state，完成/失败/取消后保存完整账本。上限 4 的恢复会话正确计入 3 原生＋
   1 运行时并拒绝新调用。没有加重试、扩预算或切换后端。
3. load_config 原先浅覆盖 runtime_defaults，预检与执行则一层合并，可能拒绝合法覆盖。
   三处共用 models.runtime_spec，仍校验实际对象及未知字段，不做任意递归兼容推断。
4. 已声明可执行构建和原生 API 模式零模型检查 jsonschema 缺失，报告
   host_dependency_missing。未使用运行时的草稿/发现保持延期路径；新增依赖声明，不安装包。

修复前 confirmed-regression.log：5 项中 4 项失败，证明停止/预算缺口。最初替身没有模拟
原生阶段自己的持久化，已修正并重新确认；两份日志均保留。静态检查怀疑的入口缺陷空
receipt 未在普通路径复现（prepare 会产生受阻 attempt），未冒称修复或添加绕过逻辑。

最终离线 `batch-readiness-regression-20261102-01`：**845 项，842 通过、3 跳过**；
65 项针对性通过，新增 8 项。三个提示自检及平台契约通过，未改提示/schema 或刷新 freeze。
新旧模式、独立审阅、布局、来源、镜像及资格门禁均保留。

## 环境、真实首轮及整理

零模型本机观察：Python 3.14.3、jsonschema/PyYAML、Codex executable 可用，ChatGPT 登录
状态成功；Docker 29.8.2 Linux/x86_64 可用，约 8.1 GB、12 CPU。原账户/认证输出不保存，
没有额外付费探针；登录本身不替代模型完成或资格证明。

本轮目录 `E:/Users/27343/Docker/batch-first-skill-20261102-01`。配置检查和零模型就绪通过
后才生成；普通 CLI，全新 state/library/shared registries，无手工 acceptance_plan、绑定
或旧资格。已有 Docker/BuildKit 缓存保留，不称冷启动。最终真实结果、源/配置摘要及清理清单
见 [证据索引](../../validation/batch-readiness/results-20261102.json)。

最终首轮 `20261102T214839-77668282`：rdkit-descriptor-rule-screening，**13/13** 当前锁定
用例，ready/accepted。发现、编写、独审、联合运行时规划各 1 次，共 **4 个准入阶段**；
环境和工具 build 各 1 次，没有额外模型探针、第二生成批次或继承旧 passed。独审 session 与
编写 session 不同；新检查点的 4 条回执与 summary 完全一致。

公开 check 按原配置核验精确 5 文件布局通过：根 requirements.txt，以及 SKILL.md、
scripts/screen.py、calc_descriptors.py、rules.json。后验只读核对真实输出：乙醇 46.069、
selected=true，苯酚 94.113、selected=false，六个描述符字段齐全，供受体均 1，policy_id
及阈值 50.0 正确；非法、空和空白输入均实际 exit 2。没有追加业务执行或放宽断言。
新工具登记当前 available，反向引用恰为新库 1 个绑定/1 个 attempt。原配置及来源摘要不变。

清理已完成：12 个缓存目录、152 个未跟踪字节码文件，共 2,716,777 字节。每个递归删除前
重新核验绝对路径位于当前 repo、无链接、只含未跟踪 .pyc；保留逐文件摘要清单。源码摘要与
通过回归/真实生成时完全一致。未清理 Docker、库、共享登记、失败轮、.env 或未知临时数据。

tracked 文件约 10 MB，没有 tracked .env/.pyc/.tmp/.bak，当前凭据值扫描通过。
README、使用/配置/状态/代码索引已更新，不以旧 647 项结果、旧 DeepSeek 配置或历史
“工具复用未实现”作为当前说明。[操作手册](../pipeline/batch-operations.md)集中给出预算、
失败、恢复和清理规则。只清理可再生字节码；未知用途的历史临时目录和失败证据保留。

## 使用边界和后续改进

适合**受控、串行、小批量**；不是任意工具或无人值守大并发全面就绪。扩大前仍需队列/
并发准入、跨 build 总预算、提供方配额/成本告警及失败分类汇总。catalog 独占锁和同名修订
冲突需明确处理，同一 run 不并发 resume。新持久化不补造历史旧检查点丢失的模型事实，旧轮
恢复先对账。动态加载、外部资源、更多 executable 结构仍需单独闭包协议与真实验证。

这些后续能力未混入本轮，资格未放宽。本轮只本地整理/提交；目标仍为
origin/pipeline-with-shared-docker，远端只读观察 b5ad543。推送等待用户审阅最终提交和结果
后明确确认。
