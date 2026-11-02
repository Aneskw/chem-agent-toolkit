# 同目录 JSON 资源：shared_tool_image_v4

本轮只增加固定 `Path(__file__).with_name("rules.json").read_text(encoding="utf-8")`。
v3 只识别 resolve().parent / 字面量链；相同源码在 v1/v3 下仍拒绝。已有多模块、完整来源哈希
和 JSON 文件进入闭包均不重复计作新增。v4 不是通用 pathlib、动态加载或任意资源读取能力。

选择依据是只读真实样例中的资源定位方式：
`chem-agent-toolkit_newpipeline/models-skills/open-models/localtransform-forward-prediction/scripts/preflight.py`
使用 `Path(__file__).with_name('requirements.json')`；retroprime 的 preflight/推理入口也有同类用法。
这些模型工具还依赖外部 checkout/权重/subprocess，整体仍不在支持范围内，本轮没有导入它们或
修改来源。标准路径语义参考 [Python pathlib](https://docs.python.org/3.11/library/pathlib.html#pathlib.PurePath.with_name)。
真实执行样例另在 validation/sibling-json/source 中组合原字节 RDKit 描述符模块、依赖和规则，
使用新 screen.py 包装入口验证这个有限路径结构；不声称历史描述符原先采用该结构。

声明的完整字段与 v3 相同，policy 必须是 `closed-python-sibling-json-v1`，选择 ABI v4：

```json
{
  "module": "scripts/screen.py",
  "path": "scripts/rules.json",
  "sha256": "57f8da82b4c7eec60fb37001152a57e8fc9a38624e7a6ee9462a04b600be34ba"
}
```

这是 bundled_data 列表的单项，不能单独作为完整 shared_tool 配置。module/path 相对包根，
均须安全、无链接且实际存在；资源必须是声明摘要对应原始字节的 UTF-8 JSON。
只允许 unaliased `from pathlib import Path`；with_name 参数是单个非空字面量文件名，不能含
斜杠、绝对路径或 ..，结果必须与该模块声明的同目录 path 完全一致。
每项声明必须实际读取。read_text 只允许显式 encoding=utf-8，无位置参数或其他关键字。
不支持默认编码、resolve/parent 链与 with_name 混用、Path 别名、中间变量、重绑定、反射、写操作。
异常绑定、模式匹配和 with_name 属性改写亦拒绝。源码必须通过原闭包、import/显式版本检查。
未知结构报 shared_tool.bundled_data 或 shared_tool.closure，保留 module、期望与实际路径。

入口仍为唯一 byte-identical 来源脚本，argv 和资源要求都保持显式声明；工作目录 /opt/skill，
Linux/amd64，resources=[]，runtime_network=false，executables=[]，本轮不扩展这些约束。
所有包实现文件和全部来源继续以 path/sha256/bytes/mode 进入 request；当前 SKILL.md 排除出工具
身份但仍进入当前 Skill 冻结与资格。声明、依赖、接口、策略、运行限制也进入 request_key。
具体构建配方是 recipe_key，观察到的 daemon/image/环境及制品记录共同构成 artifact_id。
本机 Docker image ID 仍不是 OCI manifest digest；资源摘要不证明业务正确性或授予资格。

规划前自动 resolve 或显式 select、锁内重查和核验发布复用原机制。命中只省环境规划及两类
构建，仍有当前文案的独立审阅、验收专用模型、当前来源/布局/入口与完整镜像字节核验、锁定合同
的独立实际执行和 qualify。预检复用同一静态规则，已知路径/摘要错误在付费调用前报告。

资源改而声明未改先报 expected/actual SHA；声明同步更新、源码、依赖或接口改变均是新 request，
自动 lookup miss，显式旧版本 selected_request_mismatch，不切换版本或写旧绑定。未知时拒绝，
不能从 Python 的运行成功倒推闭包完整。这是有限源码形态协议，不是任意 Python 安全证明。

外层 ToolArtifact 字段与 v1/v3 相同；SkillBinding、delivery protocol 2、RuntimeRequest 和
ExecutionAttempt 字段不变，无平台数据库迁移。v1/v2/v3 继续按自己的规则读取和核验，旧工具
不能通过改 ABI 标签成为 v4。旧客户端不认识 v4 应拒绝，不能剥离声明或降级继承资格。
普通 CLI 安装/导入/迁移继续携带完整冻结 envelope；执行资格仍先撤销再新 attempt 重验。
不提供 OCI/远端分发、任意动态 import、任意 subprocess、自动 GC 或跨主机透明恢复。

真实配对、负例和回归证据见 [本轮验证报告](../integration/sibling-json-tool-20261102.md)。
