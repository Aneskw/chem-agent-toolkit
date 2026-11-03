# 新机器安装与首次创建

目标：其他使用者获得完整源码后，用自己的环境和账号本地创建 Skill。无需原作者的目录、
.env、模型认证、共享登记、Docker 镜像或已生成库。获取包含本指南/init/doctor/bootstrap 的
明确提交或发布版本；本地未 push 的提交不会出现在 GitHub 的旧分支中。

## 前置环境与支持范围

- Python 3.11+、Git；JSON 配置只需 requirements.txt，YAML 可选。
- 本地 Docker daemon 必须报告 Linux amd64/x86_64。Windows 使用 Linux 容器模式。
  ARM/Apple Silicon 默认 daemon 与 Windows 容器模式目前拒绝；不能只加 --platform 就称支持。
- 可执行 Codex 客户端在 PATH，使用使用者自己的账号认证，并选择自己有权限的模型。
  只有桌面界面、没有可执行客户端不满足要求；桌面附带 executable 在 PATH 且能力检查通过亦可。
- 安装依赖、获取基础镜像和 Docker 构建依赖需要相应网络。network=false 限制来源获取，
  runtime_network=false 限制业务容器网络，不能理解为首次依赖安装也无需网络。

客户端安装按 [OpenAI 官方 CLI 文档](https://learn.chatgpt.com/docs/codex/cli)，认证使用
[自己的登录方式](https://learn.chatgpt.com/docs/auth)。先在本机完成认证，再选择本账号模型。
不共享认证缓存，不复制他人的 .env。DeepSeek 是另行显式配置的选项，不作失败回退。
本项目不自动安装 Codex/Docker、不登录、不修改全局代理或权限。

## Windows x64

在 PowerShell 中进入下载/clone 的仓库根目录；路径可以包含空格。

```powershell
python scripts/bootstrap.py
.\.venv\Scripts\python.exe -m creation_pipeline init --model YOUR_MODEL --output .pipeline/configs/descriptor.json
.\.venv\Scripts\python.exe -m creation_pipeline doctor .pipeline/configs/descriptor.json
```

无需激活脚本或修改 PowerShell execution policy；后续始终使用同一虚拟环境解释器。
若 python 指向旧版本，使用自己的 Python 3.11+ 路径或 py -3.11 运行 bootstrap。

## Linux x64

进入完整仓库根目录，系统 Python 须提供 venv/ensurepip 支持：

```sh
python3 scripts/bootstrap.py
.venv/bin/python -m creation_pipeline init --model YOUR_MODEL --output .pipeline/configs/descriptor.json
.venv/bin/python -m creation_pipeline doctor .pipeline/configs/descriptor.json
```

bootstrap 显式创建独立 .venv，验证 sys.prefix 后只在其中安装依赖，不安装主机化学包。
系统缺 venv 支持时由管理员按该发行版方式准备，不自动 sudo 或修改系统 Python。
Git 须由使用者预先安装；doctor 会具名报告 host_git_missing，不代装系统软件。
--venv 可选自定义位置；--yaml 额外安装可选 YAML 解析器。已有非虚拟环境目录、链接根或
解释器 prefix 不一致均拒绝，不删除既有目录。失败原因会脱敏输出。

## 配置、预检与生成的边界

init 读取公开相对路径示例，把来源路径按新配置位置重算，将同一个用户模型写入原生及
结构化阶段；不改历史配置、原来源、预算、接口或业务要求，不覆盖已存在文件。推荐配置
放在仓库内 .pipeline/configs；搬迁时整个源码树和生成配置的相对布局一起移动。
本轮公开模板的实现来源仍在仓库 validation/sibling-json/source，不能仅复制 examples 子目录。

doctor 先执行原 readiness，再用版本、exec/resume 帮助和 feature 列表检查项目实际使用的
参数及隔离能力。缺少 --ignore-user-config、schema 输出或必需特性时具名阻止；不删除隔离
检查来兼容旧客户端。[官方参数参考](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
和实际本地帮助是依据，不根据“装了某个版本”猜测兼容。

doctor 不发模型请求、不检查账户内容、不验证模型权限、不构建、不授予资格。
ready 只表示已知前置条件和已声明能力通过；deferred 不是完整可执行就绪。
--offline 跳过 Docker 探测，合法用于配置诊断，不等于可开始业务验收。
用户修改配置后，生成前再次 doctor；普通 build 仍执行原 readiness 和所有冻结/资格门禁。

在线 doctor 为 ready 后，才执行会使用模型预算的 build。以 Windows 为例，Linux 替换解释器：

```powershell
.\.venv\Scripts\python.exe -m creation_pipeline build .pipeline/configs/descriptor.json --state-dir .pipeline/state --library-dir .pipeline/library --keep-debug
.\.venv\Scripts\python.exe -m creation_pipeline check .pipeline/state/outputs/BUILD_ID --config .pipeline/configs/descriptor.json
.\.venv\Scripts\python.exe -m creation_pipeline library .pipeline/library --name ACTUAL_SKILL_NAME
```

查看实际 build_id、Skill 名称、summary 和当前 qualification；不保证名称/测试数量与作者的
历史试验相同。不要继承别人的 passed，或把 registry JSON 的存在当作当前可用性。
无需跨主机 OCI 分发：新机器从源材料本地规划/构建；后续同机精确命中按原协议复用。

## 验证范围与常见问题

离线回归/提示自检不需要模型认证；CI 没有模型凭据，不运行付费生成。新增 Windows/Linux
Python 3.11/3.14 workflow 只有在实际运行后才可称 CI 通过。项目的隔离环境、客户端诊断和
Linux 基础设施结果见 [隔离启动报告](../integration/portable-startup-20261102.md)，不能替代
用户机器上的第一次独立审阅和验收。实际已检验 Windows/Python 3.14 与 Linux/Python 3.11；
本轮没有新增付费生成，认证和模型权限须由使用者确认。未验证 macOS 主机运行。
CI 为 Windows/ubuntu-latest × Python 3.11/3.14，具体通过结果以 Actions 为准。此前 Linux
超时已定位到取消测试遗漏真实进程组信号隔离；已修复替身并加入保留 PID 拒绝门禁，
恢复原滚动标签重新验证，未跳过原用例。参见 [发布复查](../integration/publication-check-20261103.md)。

模型不可用：核对自己客户端/账号和 model 字段，不借用原作者认证或自动切换后端。
缺 Python 依赖：确认使用 .venv 的 Python。Docker 不可用/ARM：按报告的平台原因处理。
网络受限：使用自己的镜像/代理策略，不默认使用作者的 7897 端口，不改全局 Docker/Git。
缺旧工具镜像：新创建走受支持本地构建；导入旧共享工具交付不等于跨机镜像分发，仍可能明确阻止。
本轮不支持自动安装系统工具、ARM、新远端服务或通用动态加载；不自动 GC/清理镜像或旧证据。
