# 小批量创建操作

先创建一个真实 Skill，核对独立审阅、锁定用例和当前资格，再逐步扩大。当前是串行 pipeline，
不是生产队列或多 worker 调度系统。

本轮用户指定 `validation/scoped-contracts/skill-a.json`：max_candidates=max_builds=1，
model_calls=16、单次 600 秒、全轮 3600 秒、准备 2400 秒、repair_rounds=2。原生及运行时
都用原配置的 Codex，保留独审和资格检查，不修改原配置/来源/失败用例。准入阶段数不是 HTTP
次数、token 硬上限或费用。每轮用新的 state/library/evidence；不 resume 历史失败轮。

```powershell
$config = "validation/scoped-contracts/skill-a.json"
python -m creation_pipeline build $config --preflight
python -m creation_pipeline readiness $config
# NEW_ROOT 为全新独立目录，预检通过后才生成。
python -m creation_pipeline build $config --state-dir NEW_ROOT/state --library-dir NEW_ROOT/library --keep-debug
python -m creation_pipeline check NEW_ROOT/state/outputs/BUILD_ID --config $config
python -m creation_pipeline library NEW_ROOT/library --name SKILL_NAME
```

--preflight 只验证配置。readiness 零模型检查已知来源、支持范围、客户端、Docker 和缺失的
jsonschema，不安装依赖、不修系统、不授予资格。登录状态不代替推理完成；未知需求或待获取
来源仍可能 deferred。后续完整闭包和资格门禁继续执行。

共享目录可通过单命令进程环境 CHEM_AGENT_SHARED_TOOLS、CHEM_AGENT_SHARED_ENVIRONMENTS
指定，不改全局配置。新登记目录不等于冷缓存，已有镜像和 BuildKit 缓存保留。

扩大候选数前显式设置整批及候选的调用/时间/修复预算。生产默认没有聚合限额，多个 build
之间也没有总预算。发现、编写、独审、关联、环境/验收规划、诊断均可能消耗阶段；工具命中
不代表全部模型为零。配置、预检、执行使用相同的一层 runtime-default 映射合并，不做任意
递归兼容合并，未知兼容要求仍保守拒绝。

stop_on_runtime_failure=true 在首个 build_failed/execution_failed 后停止整个批次，保留
记录并把剩余候选列为 deferred，不消耗后续编写/独审预算。按既有契约不覆盖每一种
runtime_blocked 或内容失败；同时查看退出码、实体状态、deferred 与具体原因。

运行时模型准入在请求前写入原 agent-state 检查点，失败/完成/取消后保存完整账本，恢复不
自动补回消耗的配额。--extra-turns 才是显式扩展。旧代码检查点可能缺运行时准入，先对照
原 summary/model_metrics 审计，不能假定新修复使旧账本完整。

先保留失败 output/summary/record/freeze/attempt，再 runtime-inspect。runtime-resume 可能
调用模型或重建；不以重试、加预算、改需求或删用例消除失败。安装、导入和迁移仍走原资格链。
同请求发布有所有者锁，catalog 有独占锁；同名修订会冲突，同一 run 不应并发 resume。
无人值守大批仍需另行设计队列、并发准入、campaign 预算、配额告警和失败汇总。

只清理本工作副本源码/测试中可再生的纯 .pyc/__pycache__，先核验绝对路径、链接和 tracked
状态并记录清单。保留 .env、.pipeline 数据、真实库、共享登记、镜像、BuildKit 缓存、失败轮
和证据。成功 run 可先 clean --dry-run 审核；失败/待恢复 run 不自动删除。只本地整理，
用户审阅具体提交并确认后才 push。
