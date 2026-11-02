# 新使用者本地启动验证（2026-11-02）

基线 `797f0f2`，分支 `pipeline-with-shared-docker`。本轮目标是完整源码的本地安装和首次
配置，不改变生成、独立审阅、工具匹配、冻结、执行及资格链，不新增模型调用或预算。
发布前须由用户确认；未 push 的功能不会出现在 GitHub 旧分支里。

## 交付内容

- `scripts/bootstrap.py`：用户显式调用，在独立 venv 安装声明的验证依赖；默认 JSON，
  `--yaml` 可选。拒绝链接、非 venv 目录及解释器 prefix 不符。重复调用不覆盖正在运行的
  venv Python。不会安装 Codex/Docker、主机化学包或修复系统。
- `init --model MODEL --output CONFIG.json`：普通 CLI 生成相对路径的描述符配置；必须
  提供自己的模型，原生及结构化阶段一致设置。不会覆盖配置、提供旧绑定/acceptance_plan、
  继承资格或改写原来源。实现要求、业务合同、精确布局及 16/600/3600/2400 封套与原配置一致。
- `doctor CONFIG [--offline]`：复用 readiness，补充 Git 及实际客户端所需的 exec/resume
  参数、feature 名称检查。只执行版本、帮助和 feature 列表，缺失对象具名阻止。
  不验证认证、账户权限或模型质量；不构建、不修复、不授予资格。普通 build 保留原门禁。
- 新机器指南、可携带示例、凭据模板说明；Windows/Linux × Python 3.11/3.14 离线 CI 定义。
  workflow 尚未在 GitHub 运行，不将本地验证写成 CI 成功。

公开入口见 [新机器安装](../pipeline/new-machine-setup.md) 和
[描述符示例](../../examples/descriptor-screening/README.md)。必须取得整个仓库，不能只复制
input.json/examples；来源仍是原 `validation/sibling-json/source`。配置与来源一起移动，
保留相对布局；本轮 init 跨 Windows 驱动器具名拒绝，不改成作者绝对路径。

## 隔离方法与失败证据

Windows 不是第二台物理电脑：从候选源码导出到含空格的新目录，排除 .env/.pipeline/.venv
等被忽略的运行数据；独立 venv、空 CODEX_HOME、移除认证环境变量及原客户端 PATH。
导出同时记录逐文件 SHA-256；测试从新副本导入 creation_pipeline。历史已提交的测试/证据
保留，但没有导入历史库、镜像或资格。最终当前源码与导出源输入复核一致。

Linux 使用本机已有官方 Python 3.11 slim 镜像的本地 image ID，输入只读挂载，复制到
容器内 /workspace，输出挂载新证据目录。无 Docker socket、认证、共享登记或原化学环境。
首次安装 Git、venv 验证依赖及锁定 RDKit 依赖；临时代理仅用于本轮网络。基础镜像已预热，
不是冷拉取实验；没有清理任何现有镜像/缓存。专用容器运行后移除，原 Docker 数据保留。

失败轮完整保留，不 resume/restart：

| 轮次 | 结果 | 具体原因及修正 |
| --- | --- | --- |
| Windows `portable-checkout-20261102-01` | 857 项，1 失败、3 跳过 | 原生生命周期替身只替换执行器的 Codex resolver，零模型 readiness 正确因缺客户端阻止。测试补齐 resolver 替身，产品门禁不放宽。 |
| Linux `portable-linux-20261102-01` | 857 项，2 失败、30 错误、1 跳过 | slim 镜像缺少已声明 Git，导致来源登记等 31 项异常；另 1 项为同一 resolver 测试依赖。新轮只在隔离容器显式安装 Git，doctor 增加 host_git_missing。 |

首次独立稳定客户端探测还发现：自定义 CODEX_HOME 必须是已存在目录，空但不存在的目录会
使 feature 查询失败。实验控制器显式创建自己的空目录后重验，不复制作者认证；产品诊断
保留原始脱敏失败原因，不自动修复用户配置。

修复后独立新轮：

| 验证 | 当前结果 |
| --- | --- |
| Windows `portable-checkout-20261102-02` | Python 3.14.3；859 项，856 通过、3 跳过；三个提示自检、平台契约、init/preflight/doctor 均通过。 |
| Linux `portable-linux-20261102-02` | Python 3.11；859 项，858 通过、1 跳过；同样四个自检及普通 CLI 通过；原始来源业务工作负载 5/5。 |
| 针对性 `portable-review-20261102-02` | 67 项，66 通过、1 跳过；新增初始化/诊断/venv 回归 14 项，无真实模型。 |
| 默认 JSON `portable-json-20261102-01` | 全新 venv 只装 requirements.txt；jsonschema 存在，PyYAML 不存在；init、preflight 通过。 |
| 官方 Codex 稳定版 | 独立 npm prefix/cache 安装 0.166.0，空认证目录；四个本地能力探测通过，在线 doctor 为 ready。认证、权限均 not_checked。 |

Windows 全套 unittest 本体 523.313 秒、外层进程记录 529.115 秒；Linux 本体 107.247 秒、
外层 108.557 秒，具体原始值见证据。平台/Python、文件系统和同时运行的工作负载不同，
不能当作跨平台性能排名。Windows 主机 pip 缓存和 Docker/BuildKit 缓存保留，未控制为冷；
Linux 基础镜像已预热，容器内 venv/化学依赖新安装。本轮没有测冷启动/磁盘节省。

全套日志包含负向用例故意输出的拒绝消息；以 unittest 的退出码和最终汇总为准。
Python 3.14 的 is_reserved 弃用警告仍在，尚未更换接口；没有将警告写成失败或隐去。
未修改提示/schema 或刷新 freeze。最终后续变更仅文档、脱敏证据、只读核验脚本及控制器
首行说明；原有 .gitattributes 规则保留。
生产代码、测试及初始化模板与本轮导出字节一致，证据索引按这些对象单独核验。

## 证据口径及限制

完整命令、退出值、耗时、脱敏日志、输入摘要与失败轮引用见
[机器可读证据索引](../../validation/portable/results-20261102.json)。
绝对证据路径是本机实验定位信息，不是新用户配置所需目录。
`python validation/portable/verify_evidence.py` 仅按相对路径复核发布证据字节，不查询本机
镜像或资格。证据文件禁用 Git 换行转换；源输入摘要记录的是实验工作副本实际字节，
不要求其他系统的文本工作副本具有相同换行。

本轮模型准入 0、完整模型生成批次 0、环境/工具镜像 build 调用均 0；Linux 的 apt/pip
依赖安装单独记录，不能称为“零安装”。原描述符实际运行 5 条为基础设施工作负载，不是
生成 Skill 的验收或新资格；独立审阅/验收模型的真实首轮仍引用
[上一轮结果](batch-readiness-20261102.md)，不挪用其 accepted。

支持目标：Windows x64 / Linux x64 源码工作副本，用户自己的兼容可执行 Codex 客户端及
认证/可访问模型，Docker daemon Linux amd64。只有桌面 UI 不满足自动化入口条件。
ARM、Windows 容器、远端分发/OCI、自动系统安装、wheel 发布及跨机继承资格不在本轮范围。
Linux 容器离线回归不替代新 Linux 主机 Docker/客户端/账号的完整首次生成；Windows 隔离
副本也不能证明所有全新电脑的网络和账户可用。首次真实运行仍须独立审阅和当前资格检查。
