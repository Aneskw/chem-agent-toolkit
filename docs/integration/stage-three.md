# 阶段三：迁移 Docker 执行验收并接入主流程

工作区：`E:\Users\27343\Docker\chem-agent-toolkit-integration`，分支
`integration/docker-stage3`。从阶段二 `d6b882d` 开始，阶段一为 `e9a4353`。
本阶段开始时集成区干净，未发现适用 AGENTS.md；远端只读核对仍为
`e117c434f54d11fd24e3e5566f187a8f4a41a87f`，没有静默更新基线。
旧代码按 Git `d5b77dc5d91711567af1960530d03739a5c442bf` 读取，原 Docker
工作区的 92 项历史删除/归档没有混入。没有远端推送、发布或 PR 合并。

## 迁移映射

阶段二已经迁移 `planner.py`、`acceptance.py`、`coverage.py`、模型调用/网络辅助，
并完成 preparation/local/service 的构建适配。本阶段继续复用，不复制第二份。

| 旧实现（d5b77dc） | 当前位置 | 保留行为 / 必要适配 | 验证 |
|---|---|---|---|
| runtime_package.WindowsProcessJob / process / stop_process_tree / cleanup_scope | runtime/runner.py；local.process 调用同一进程管理 | Windows Job、POSIX 进程组、超时清理、归属标签；补充部分日志/清理回执持久化 | 迁移 cleanup/ownership 测试、真实超时探针 |
| runtime_package.invocation / run | runtime/runner.py | 只读容器、非 root、资源限制、输入输出挂载、强制清理；新增冻结来源挂载和声明 cwd | 真实 10 项 RDKit、超时及容器无残留 |
| runtime_package.run_case / retain_outputs | runtime/runner.py | fixture、预期退出码、实际文件读回、输出留存；目录换成动态证据；取消隐藏总输出字节配额 | 迁移 stdout/file 用例、真实文件输入输出 |
| runtime_package.subset / output_matches / relation 检查块 | runtime/runner.py | 类型、数值容差、JSONL、语义结果/拒绝断言、关系断言；抽取 relation_matches 供证据重算共用 | 迁移 22 项旧测试，错误输出真实拒绝 |
| runtime_acceptance.* 与旧 runner.acceptance_coverage/input_check/select_usage_case | 阶段二 runtime/acceptance.py + coverage.py | 继续使用来源引用、适用操作、正常/非法输入、业务覆盖判定，未重新实现 | test_migrated_execution 的 AcceptanceV2/Interface 测试 |
| runtime_model_lifecycle.validate / states 的执行部分 | runtime/execution.py | 按锁定用例执行、状态汇总、镜像内来源文件哈希；旧包/七章节模板/发布耦合拆除，改收 RuntimeRequest | 实际镜像字节检查及 10 项业务/接口检查 |
| runtime_model_lifecycle.evidence / verified_image 的核验部分 | execution.evidence + local.verify_current | 来源/输入/契约身份、锁定结果重算、当前镜像 ID 与保留 tag；旧全局路径改冻结 envelope+动态 attempt | 真实 tag 改指向、删除、重建；4 种输入漂移 |
| strict_acceptance.reports_pass | runtime/strict.py + contracts.qualify | 保留数量、acceptance v2、current validated 检查；只在重新核验真实证据后调用 | 伪 passed 标志不能过关、统一库晋升/撤销 |
| 旧 test_acceptance_v2 / test_runtime_interfaces / test_runtime_hardening / test_runtime_linux；test_runtime_model.fixture_plan | tests/pipeline/test_migrated_execution.py | 提取原测试函数和断言，旧发布 fixture 替换为当前验证器；没有移植旧 CLI/包协议 | 22 项，其中 2 项 Windows 跳过后在 Linux 补测 |

迁移保留的是执行与验证内核；旧 lifecycle 的创建、修复总控和发布体系没有移植。
NativeSession、author/review、资源补充、逐候选循环及 catalog 事务仍是 partner 新版。

## 接口与耦合变化

- `LocalExecutor.validate(request, build_receipt)` 从占位接口变为真实容器验收。
  `execute_prepared` 默认 build 后执行；`build_only=True` 仅保留阶段二诊断脚本的历史范围。
- 新版 configured/generated 和 reviewer 请求的检查冻结进同一 acceptance 契约，
  映射解释器、交付包、来源、cwd、输出。主流程关闭宿主业务检查。
- 环境失败回已有 planner，内容/调用失败回原作者和独立审阅，资源缺口保留阻塞。
  环境修复保持源码与锁定检查不变，重试保留旧证据并遵守显式预算/无进展终止。
- `contracts.qualify` 增加证据上下文，原 store 的 adopt/reconcile/install 调用它。
  不另建入库器。动态 content_revoked 撤销当前内容通过，普通 runtime 恢复不能绕过。
- `runtime-validate` 复用绑定镜像重新执行；`runtime-build` 重建并执行；
  `runtime-prepare` 建新环境修订；有来源支持的 oracle correction 必须独立审阅后才改契约。
- 默认查询、安装只取 accepted。镜像/tag 失效会降回 candidates；历史通过仍可追溯。
  安装同步提供冻结构建材料和动态证据，交付目录本身不塞入动态日志。

## 新增而非旧代码原样迁移的能力

1. Native 检查到容器的路径/解释器映射，适配 partner 的直接文件交付接口。
2. 冻结包外的执行证据、raw assertion 重算与 catalog 当前资格连接，取代旧包内状态文件。
3. 同一 candidate 的内容失败撤销、镜像丢失降级、明确恢复和安装 runtime envelope。
4. 源码支持的 oracle correction 入口复用 partner 独立审阅，并保存审阅/契约历史。
5. 超时部分输出和清理回执随动态证据保存；审阅器补充检查不会因禁止宿主执行而丢失。

这些是新旧接口衔接所需的适配，不是重新创建一套执行断言、业务覆盖或主流程。
外部权重/数据/凭据传递缺少执行契约时明确阻塞；仅“文件存在/环境变量存在”不算资源可用。

## 验证及可复查证据

- 开始时新版基线：142 项通过，见 `validation/stage3/baseline-tests.log`。
- Windows 回归：176 项，成功、其中 2 项 POSIX 测试跳过；见 `windows-tests.log`。
  22 项为迁移旧保障。当时 12 项接口/政策测试；最后补充执行失败后继续下一候选的调度测试，
  定向 13 项全通过，见 `interface-tests.log`（当前共 177 个用例，未无理由重跑整套）。
  原 4 项纯 Python 宿主检查单测保留原断言，
  通过测试专用适配器隔离；另测生产路径只声明容器检查。它们不充当 Docker 验收。
- Linux 容器补测 3 项权限/清理单测通过（包含 Windows 跳过的 2 项），见 `linux-tests.log`。
- 真实 Native 独立内容审阅通过，见 `independent-review.json`。初次审阅曾拒绝缺少可执行
  命令/解释边界的说明，保留 `initial-review-rejection.json`；修正文档及来源引用后重新独立审阅。
  未复用与改动计划不匹配的旧审阅。
- 真实 RDKit 10 项全部通过：依赖版本导入、实际入口 help、乙醇、甲烷图计数、空输入拒绝、
  文件正常输出、混合空行拒绝、交付脚本原生检查、冻结来源文件输入及输出、非空非法 SMILES。
  Python 依赖仅在容器内安装，没有宿主 RDKit 或 mock 替代。
- 真实 tag 改指向 → 默认查询撤销；恢复 tag 后仍需显式重验；镜像删除 → 撤销；
  从冻结输入重建并重跑 10 项 → 晋升。原阶段二镜像未删除。见 `recovery-results.json`。
- 交付文件、来源、锁定输入和 catalog 契约的独立漂移副本均不能保留当前资格，历史仍保留。
- 故意修改新候选的 canonical SMILES 输出，原锁定期望不变：真实构建成功，
  实际业务检查失败，分类为 content，进入候选区；正常候选继续 accepted。见 `wrong-result.json`。
- 真实 2 秒超时保留 stdout 和容器已写出的文件，归属容器检查无残留；见 `timeout/`。
- 移到 `validation/stage3/rdkit-library` 后重新核验，无临时目录依赖；
  当前镜像、修订及结果在 `summary.json`。该库是验证样例，不是默认生产 skills 库。

`verify_saved_evidence.py` 会查询当前 Docker 状态；换主机或删除镜像后预期撤销资格，
不能把保存的 summary 当永久有效证明。重现命令及详细目录/状态见
`docs/pipeline/docker-execution.md` 与 validation 下四个真实探针脚本。

## 阶段四承接边界与未覆盖事项

- 继续使用 RuntimeRequest、LocalExecutor 四接口、service 三个恢复入口、统一 qualify/store；
  不引入旧 checkpoint/bindings/ZIP 兼容层。
- 本阶段真实验证走了 Native 独立审阅 → 新版准备/冻结 → build/validate → store/recovery，
  没有再跑一次完整实时模型发现、编写、自动环境/内容多轮修复的整批端到端实验。
  主流程调度和 partial/断言保护有机制测试；真实双候选成功/失败有独立执行和同库记录。
- oracle correction 的拒绝/来源/锁定保护有机制测试，未制造真实错误预期并让模型改期望，
  不宣称真实 correction 闭环已验证。
- 远程服务/GPU、外部权重和数据挂载契约、凭据传递、服务探测仍未实现，必须保持阻塞。
  预留接口不代表这些能力存在。CPU 样例不能证明 GPU 或一般科学正确性。
- 旧版外部工作区/归档不依赖、不删除；默认维护的集成代码没有第二套旧主流程。

阶段三到此停止，不自动实施下一阶段。
