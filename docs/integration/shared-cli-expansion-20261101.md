# 普通 CLI 的完整工具复用验证

后续已有有限 Open Babel v2 协议及真实 CLI 对照，见
[Open Babel 完整工具共享](openbabel-shared-tool-20261101.md)。本报告的预检拒绝结论属于当时 v1 范围；
v1 规则未放宽，新声明和实际支持面由 v2 报告说明。

基线 `20f0c67`。本轮从普通配置与 `python -m creation_pipeline` 入口验证，未调用实验脚本
注入 record、prepare、seal 等内部状态，未提供 plan/acceptance_plan，未复制旧资格。
原 Codex CLI / DeepSeek 后端和每批 16 调用、600 秒单次、3600 秒整批封套保持不变。

独立证据根：`E:/Users/27343/Docker/shared-cli-expansion-20261101-01`。
配置见 `validation/deepseek-api/shared-cli-expansion/`；索引见
[真实结果与文件 SHA256](../../validation/deepseek-api/shared-cli-expansion-results-20261101.json)。

## 描述符真实结果

| 路径 | 新业务用例 | 总模型调用 | 环境规划 | 验收专用规划 | 环境/工具 build |
|---|---:|---:|---:|---:|---:|
| A 首次生成 | 15/15 | 9 | 5 | 0 | 1/1 |
| B 自动命中 | 14/14 | 6 | 0 | 2 | 0/0 |

A 的组合规划同时负责验收；不是额外 5 次验收调用。两批均独立发现、编写及新会话审阅，
编写均使用原预算内的修正轮。B 自然进入 acceptance_only，既不手工提供合同，也不复用 A 的测试。
SKILL.md 与验收合同摘要分别不同，脚本及 requirements.txt 字节保持来源一致。
依赖文件实际位于 resources/requirements.txt，并非配置文案要求的包根位置；两份布局一致，
但不能宣称完全遵循了该位置要求。末次字节审计按实际路径核验，结果单独保留。
具体 ToolArtifact 为 `19aafbc0aaf373bebd96dadf9c14fbdaf24fafd02141bb1aec05dfb0403f737f`，
request_key 为 `2d43cfd60317b0ae2ca8d84c527a8ae788902f27f503f24f5da73599bca92af0`。
最终只读 qualify 复核两批通过。共两批、29 条成功用例、15 次模型调用；不并入历史批次。

实际步骤（在仓库执行，证据根每次必须全新；下文 `$root` 为该新根）：

```powershell
$env:CHEM_AGENT_SHARED_TOOLS="$root/shared-tools"
$env:CHEM_AGENT_SHARED_ENVIRONMENTS="$root/shared-environments"
python -m creation_pipeline build "$root/descriptors-a.json" --preflight
python -m creation_pipeline build "$root/descriptors-a.json" --state-dir "$root/a/state" --library-dir "$root/a/library" --keep-debug
python -m creation_pipeline build "$root/descriptors-b.json" --state-dir "$root/b/state" --library-dir "$root/b/library" --keep-debug
python -m creation_pipeline runtime-inspect "$root/a/library" --candidate chem-rdkit-descriptors
python -m creation_pipeline runtime-resume "$root/a/library" --candidate chem-rdkit-descriptors
```

先将已提交配置复制至新根。A 成功后才执行 B。`runtime-resume` 对成功 A 进行原锁定合同重验，
返回 execution_passed、accepted=true；恢复前 availability 中 business_acceptance=not_run，
可用性不冒充资格。这次恢复另计，不算第三个生成批次。没有恢复失败生成轮。

## 负例、导入及反馈修复

使用 `runtime-import <A output> <独立 library> --candidate chem-rdkit-descriptors` 导入两份候选，
均为 not_run/candidate_saved，随后用 `runtime-prepare --spec` 选择同一具体版本：

- RDKit 要求由 2024.9.6 变为 2024.9.5：selected_request_mismatch。
- 入口 argv 增加 --smiles CCO：selected_request_mismatch。
- 两次均 runtime_blocked，具名列出引用、请求及 expected/actual；不替代版本，不获得资格。

通过 `install <A output> --destination <新目录>` 安装后，分别验证三种不同对象：
安装根目录不是 runtime-import 的封套入口，明确拒绝；修改展示 skills/ 下脚本不改变
runtime/<name>/frozen 内原冻结工具，后者可导入但仍撤销资格；修改封套自身
frozen/package/scripts/calc_descriptors.py 后，导入拒绝。
这属于冻结源码完整性负例，不声称完成“改变源码后重新生成新版本”的实测。

此次修复将笼统的 Frozen ... changed 错误补为具体路径、期望/实际 SHA256 与字节数。
判定逻辑仍比较完整清单，不因诊断使用路径映射而允许重复记录。CLI 另新增运行准备及执行阶段提示，
避免长时间显示上一阶段“审阅”。A 运行时尚未加载该提示改动，B 已实际显示两条新提示。

沙箱内 Docker 不可访问导致的 inspect/qualify 失败、临时目录权限导致的首次自检失败均保留日志；
使用工作区临时目录及有 Docker 权限的相同命令复核，不把它们统计为业务失败或新模型批次。

## Open Babel 的明确边界

真实原脚本调用外部 obabel，而 closed-python-bundle-v1 明确禁止外部可执行文件及 subprocess。
本轮没有移除该资格保护，也没有宣称 Open Babel 完整工具共享成功。
新增配置预检复用同一声明校验，在付费生成前报告
`shared_tool.requirements.executables ... actual=['obabel']`，提示显式使用旧自包含模式或受支持工具。
测试确认此错误不会进入 build。旧自包含 Open Babel 支持不受影响，保留全套旧模式回归。

尚未完成：Open Babel 两个完整生成的共享命中批次、外部 executable 的版本/闭包协议扩展，
以及改变源码后的全新生成对照。本轮支持结论限于描述符 Python 闭包。后续需要定义可执行文件、
动态库及数据依赖的确定性身份后再扩展；不涉及 OCI 分发或远端平台。

不清理 Docker 缓存；本轮 build 次数不是依赖安装实际执行次数，也不宣称冷启动性能。
独立审阅、源码绑定、锁定合同与实际 qualify 检查全部保留。

最终代码完整回归 690 项：687 通过、3 跳过，无失败；三个提示自检通过，未改提示或重新 freeze。
索引保存 48 个证据/代码文件哈希。原始大型证据留在本机独立目录，配置、摘要和索引提交入库。
