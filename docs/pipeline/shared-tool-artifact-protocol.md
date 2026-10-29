# 精确 Tool 制品复用：下一阶段协议草案

状态：设计草案，尚未实现。当前第一阶段共享依赖环境与薄工具镜像已经实现；这里定义其后续精确 Tool resolver 的协议和接入边界，不将设计视为功能完成。

## 可复用对象和绑定

分开 EnvironmentArtifact、ToolArtifact、SkillBinding、ExecutionAttempt。EnvironmentArtifact 对应已核验的依赖环境；ToolArtifact 包含工具实现闭包、固定运行接口和具体环境；SkillBinding 把当次冻结 skill 的入口证明映射到具体 ToolArtifact；ExecutionAttempt 保留当前测试、镜像身份和独立输出。Skill 文案与验收不放入环境身份，但仍进入 skill 自己的冻结指纹与资格。

ToolArtifact 的最小记录必须包含协议版本、实现闭包 manifest（相对路径/sha256/mode）、源绑定、接口 argv/工作目录/资源能力、environment artifact identity、构建计划与审阅凭证，以及本机 daemon/image 身份。portable OCI identity 必须是独立类型和真实观察值，不能将 image ID 填入 manifest digest 字段。

request_key 在规划前产生：实现闭包、显式需求、目标平台和相关策略版本。声明闭包缺失、无法确认 import/数据/可执行依赖或含未绑定资源时，返回可解释 miss；不从一个主脚本 hash 推断所有传递依赖。环境尚未选定不妨碍按 request_key 查找多个已经接受的候选制品；只有完整要求一致、策略有效、制品可用时精确命中。不能跨不同显式版本要求或无声采用 latest。构建 recipe_key 和实际 artifact identity 分别保留，不能将 request_key 当作可重现构建证明。

旧实现的 revision 标签与镜像内 package manifest 检查是现有强约束，不能删除它们后直接“命中”。新 shared_tool_image 模式需要独立 ABI：工具文件存固定 /opt/tools/<tool-id>/，资格同时核对冻结 skill 包、源入口摘要、映射的工具入口和镜像工具 manifest。模型不能自证路径映射。旧 self_contained_image 模式继续原路径和原验证。两种模式必须在安装包、executor、证据和 qualify 中端到端识别；不混用旧 receipt。

命中只省略缺失工具的环境规划/构建，不省 skill 的内容审阅、来源/接口核验、当前验收用例编制与执行。已有工具的 passed 标记最多是工具回归历史，不是新 skill 的验收结果。命中后仍在每任务新建的非 root、只读、独立输出、默认无网络容器中运行；没有常驻 worker 或跨请求 Python 状态。

## 发布、失败与可移植性

按 request/recipe 单飞创建，已完成记录原子发布，观察记录与制品版本分离。并发未完成返回 busy 或有界等待，不能读取 partial；锁接管须可靠确认所有者。环境镜像缺失是环境 miss，ToolArtifact 源/接口不匹配是工具 miss，当前业务失败是新 SkillBinding 不合格。新构建失败不回写旧制品，不改变旧 skill 的具体绑定。

本机引用只保证同 daemon 的可用性。若要对外导出，选择并实现 OCI registry manifest 引用或自包含 OCI archive；导入后验证完整内容身份并重新建立本机观察。没有导出/导入实现时不能称为便携共享工具包。原 self-contained bundle 的可用性不能被新模式默默降级。

## 接入顺序与验收

先冻结 typed ToolArtifact/SkillBinding 协议和保守 request key，接入独立 registry + readonly resolve；再接 prepare/service/executor/qualify/install 的新模式，最后增加 planner 前精确命中。暂不增加自动兼容合并与 GC。

必须有真实测试：两个 skill 文案不同而完全同工具，第二个 ToolArtifact 命中且两次业务独立执行；不同源码/接口/资源/策略/平台拒绝错误复用；不同工具共环境；镜像丢失/daemon 漂移/记录损坏 fail closed；并发只发布完整制品；新 skill 用例失败不污染旧资格；旧绑定可继续运行；新模式导出/导入或明确拒绝不支持的交付形式。分别度量 planner 次数、环境 build、工具 build 和业务执行，不能把环境命中当成 Tool resolver 完成。

## 2026-10-29 官方资料核对

- https://github.com/opencontainers/image-spec/blob/main/manifest.md ：manifest 通过 descriptor 引用 config 和有序 layers；portable manifest identity 是独立对象。
- https://github.com/opencontainers/image-spec/blob/main/config.md#imageid ：当前规范不再统一规定各实现如何生成 ImageID，因此本机 Docker identity 必须注明实现/daemon，不能泛化为 OCI 配置哈希或 manifest digest。
- https://docs.docker.com/engine/containers/run/ ：镜像与容器有不同生命期；默认 ENTRYPOINT 与运行时 command 组合决定实际执行。共享镜像不要求共享容器；仅检查 command 数组是否重复出现脚本会误判默认入口。

上述协议取舍是对当前代码的设计推导；不是这些规范已经替 pipeline 实现或证明的功能。
