# Open Babel 完整工具共享：普通 CLI 验证

基线 `5e91f64`。本轮增加 `shared_tool_image_v2` / `openbabel-debian-image-v1`，
支持原始 Open Babel 转换包装脚本及 Debian 标准插件/数据布局。
[协议与架构](../pipeline/openbabel-external-tool-protocol.md) 说明声明、实际身份、闭包及资格边界。
可复核索引：[结果、计数与 1,139 个文件 SHA256](../../validation/deepseek-api/openbabel-shared-tool-results-20261101.json)。
原始模型/冻结/逐用例文件在本机独立证据目录保留，索引记录其绝对位置；没有将全部原始文件重复提交。

执行只使用普通 JSON 配置和 `python -m creation_pipeline`，没有脚本注入 record、prepare、seal
或资格状态，没有手工 plan/acceptance_plan。只读审计脚本检查 CLI 已产生的记录及当前资格。
配置沿用原 Codex CLI gpt-6-astra / DeepSeek deepseek-v4-pro 组合；每批 16 次准入调用、
600 秒单次、3600 秒整批及原 2400 秒运行准备封套不变，供应商重试也不变。

## 实现及支持范围

请求键仍由规划前已知的源码/数据闭包、接口、上游版本要求、平台、策略与限制产生。
具体配方与实际制品身份分开；新的实际身份包括执行文件摘要和版本、dpkg 包版本清单、
动态库路径/摘要、插件/数据路径，以及完整镜像文件清单的规范摘要、数量和逻辑字节数。
完整文件闭包覆盖间接加载的库和数据，不能只凭可执行文件的版本字符串复用。
本机 Docker image ID 不作为 OCI manifest digest；本轮没有远端分发、自动兼容合并或 GC。

外部执行支持受限于原包装程序 AST；任意 subprocess、shell、自定义插件布局、BABEL_*/LD_*
覆盖和外部挂载均不在支持面。原 v1 的 subprocess 禁止规则继续有效。
身份探测是独立只读/无网络的元数据容器，使用 root 与 DAC_READ_SEARCH 读取私有系统目录；
实际转换继续非 root、只读、无网络、每用例独立容器及输出。不会在宿主机执行转换或安装依赖。

命中后仍独立发现、编写和审阅，验收专用模型编制当前合同；发布、规划前绑定、运行前后和
当前资格核验都检查具体镜像及外部身份。模型不能声明实际身份或继承另一 Skill 的通过记录。
CLI `runtime-tools-inspect` 可显示实际执行文件、闭包及插件/数据摘要，离线状态仍为 historical_unverified。

## 失败轮与离线修复

- `E:/Users/27343/Docker/openbabel-external-identity-20261101-01`：无模型基础设施探测失败。
  缺少读取能力，无法枚举 APT 私有目录；原始命令、stderr 和 failure-audit.json 保留。
- 同级 `openbabel-external-identity-20261101-02`：补充只读能力后，两次观察完全一致。
- 同级 `openbabel-external-identity-20261101-03`：最终观察器补齐规范路径/运行时路径拒绝检查后，
  两次观察再通过。原样例镜像覆盖 6,238 个文件、905 个链接；这是逻辑文件统计，不是磁盘占用。
  三个轮次均无模型、无构建或转换，不计入完整生成批次。
- `E:/Users/27343/Docker/openbabel-shared-cli-20261101-01`：首个 A 完整生成批次失败，
  4 次模型调用，8/9 通过。`interface-four-flag-direct` 设置了 output_file=ethanol.sdf，
  却以 kind=json 断言 stdout 的 ok 字段；比较器按原规则读取留存 SDF，故拒绝。
  工具身份/镜像核验、实际 SDF 结构、未知格式拒绝和五项原生检查均已通过，不能据此授予资格。
  原失败用例、输出、冻结合同和制品记录全部保留，未恢复或重启该轮。

修复在现有规划反馈循环中校验该适配器的明确 SDF 格式标志，冻结前具名指出用例、字段和通道冲突。
比较器保持原规则；模型应给真实 SDF 使用有来源的 text_regex，stdout JSON 单独断言。
反馈保留本轮草稿，用例不能删除，业务 argv/fixture/退出码/输出文件及 stdout 条件不能改弱，
其他已验证用例不能更改。重复无进展或预算耗尽继续阻止，不增加预算。
另补齐构建截止后自有身份容器清理，并在单元测试覆盖该超时边界。

`openbabel-shared-cli-20261101-01/failure-diagnosis.json` 离线重放原失败计划，
确认新检查可在冻结前拦截。全新 `openbabel-shared-cli-20261101-02/a` 成功：8/8、
4 次模型准入调用，环境/工具构建各 1 次。配置和业务义务与失败轮完全相同。

`openbabel-shared-cli-20261101-02/b` 后续确实自动命中同一制品，环境规划 0、两类构建 0，
独立验收模型 2 次（首份引文不逐字匹配，自动反馈修正），全部模型准入调用 5 次。
实际 8/9，通过的业务转换、SDF、拒绝及五项原生检查不能掩盖失败环境探针：它把
`subprocess.check_output(['obabel','-V'], text=True).strip()` 原样放入 JSON，却要求包含闭合引号的
`"Open Babel 3.1.1"`；实际值为 `Open Babel 3.1.1 -- Jan  4 2023 -- 09:58:24`。
当前比较器正确拒绝，B 未获资格。该失败轮与原用例均保留，未恢复或重启。

修复给验收专用模型提供已核验的 ToolArtifact 执行文件事实（没有旧验收或 passed），
并对已识别的直接 JSON 元数据探针在冻结前检查这一序列化矛盾。修正必须保留真实探针程序、
完整版本及空格边界、Python 系列/路径条件和其他全部用例，不能退化为只查 Open Babel banner。
归一化版本等其他程序不会被猜测判错；实际执行仍不可省略。比较器未修改。
有意更新版本探针说明及事实上下文提示后，按 planner freeze → acceptance freeze → check 顺序更新快照。
`b-failure-diagnosis.json` 保存旧计划的零模型离线重放及新增诊断。

全新 `openbabel-shared-cli-20261101-03` 只重新完整生成 B，普通配置与失败 B 相同，
使用 `-02/shared-tools` / `-02/shared-environments` 作为正常主机共享目录。
成功 A 保留原始生成凭据，并在当前代码下独立复核及公开导入/恢复重验；其 ToolArtifact 的
源码、镜像、闭包观察器均未因验收编译提示更新而改变，不需要重新规划或构建工具。
原 A 的生成代码摘要与新 B 的代码摘要分别记录，不将 A 当作又一次新生成。

另有独立基础设施对照 `E:/Users/27343/Docker/openbabel-external-data-drift-20261101-01`：
派生镜像仅给 `/usr/share/openbabel/3.1.1/patterns.txt` 追加 47 字节。
执行文件 SHA256/版本、包清单及动态库摘要保持一致，完整文件闭包变化，身份比较拒绝。
该轮 1 次基础设施 build、零模型、零业务转换，不发布工具，不混入 A/B 的环境/工具 build 计数。
原镜像及用户已有缓存保留。

## 操作入口

普通配置见 [A](../../validation/deepseek-api/openbabel-shared-cli/openbabel-a.json) /
[B](../../validation/deepseek-api/openbabel-shared-cli/openbabel-b.json)。两者运行要求、接口和原始来源相同，
只有文案风格不同。真实成功对照为 `-02/a` 与 `-03/b`：

| 观测 | 成功 A | 成功 B |
|---|---:|---:|
| 实际执行 / 当前资格 | 8/8，通过 | 9/9，通过 |
| 发现 / 编写 / 独立审阅准入调用 | 各 1 | 各 1 |
| 组合环境及验收规划 | 1 | 0 |
| 当前验收专用模型 | 0 | 2 |
| 全部模型准入调用 | 4 | 5 |
| 环境 / 工具 build 调用 | 1 / 1 | 0 / 0 |
| 整批秒数 | 735.770 | 779.967 |
| 构建或核验绑定秒数 | 11.441 | 4.808 |

两个包的文案与验收合同摘要均不同，原脚本和 CCO+CRLF 输入摘要相同。具体工具版本均为
`22183828d1ab03b585b48374d98a1ed063d72aca032f27613acc88aad87e3278`，请求键
`e911e0a86ef655dd0e1b999f646246ad19ae9ec1354b384d51f74016d59e468f`；实际本机镜像为
`sha256:71a84530ca39cb67015f1a384a0f43d1ec8f1340163c9b5de1d1cfcfb7b795e1`。
实际 Open Babel / libopenbabel7 Debian 版本均为 `3.1.1+dfsg-9+b3`，执行文件摘要
`57584125b4946eea824d3bfa75c3fce2c018efa680368e1bdfdbf9c121784876`。

B 首份验收草案把 invalid_input 枚举写成解释句，现有检查自动反馈要求使用 `required`，
第二次编制后冻结成功。新版实际首轮模型材料含已核验执行文件事实、空 previous_plan，
bound_environment 不含历史验收字段；`observed-identity-input-audit.json` 保存实际发送材料审计。
本轮没有人工填写或修改验收计划。版本序列化新检查的错误分支由原失败 B 的离线重放及回归验证，
不把新 B 的枚举修正冒充该新检查在模型中的触发记录。

B 的总时间较 A 长：多一次验收调用且用例数量不同，不能据此归因整体加速比。
4.808 秒是核验绑定耗时，build 调用仍为 0。环境和镜像已经预热，原缓存未清理。
完整镜像清单的字节数属于逻辑文件统计，不是 Docker/WSL 实际磁盘占用；本轮不据此新增存储结论。

整个新协议生成活动共 **4 批、18 次模型准入调用**：2 批成功、2 批失败。
成功资格对照为 17/17；两个失败轮各 8/9，未获资格且不并入成功对照。
元数据探测、数据漂移对照和原合同重验都没有新模型调用，另行计数。

在仓库目录执行，先将两份普通配置放入全新的绝对 `$root`：

```powershell
$env:CHEM_AGENT_SHARED_TOOLS="$root/shared-tools"
$env:CHEM_AGENT_SHARED_ENVIRONMENTS="$root/shared-environments"
python -m creation_pipeline build "$root/openbabel-a.json" --preflight
python -m creation_pipeline build "$root/openbabel-a.json" --state-dir "$root/a/state" --library-dir "$root/a/library" --keep-debug
python -m creation_pipeline build "$root/openbabel-b.json" --state-dir "$root/b/state" --library-dir "$root/b/library" --keep-debug
python -m creation_pipeline runtime-tools-inspect --root "$root/shared-tools"
python validation/deepseek-api/audit_openbabel_shared_cli.py "$root"
```

A 当前资格通过后才启动 B；发生失败时保留全轮证据，修复后使用新根。
本轮跨根审计使用 `audit_openbabel_shared_cli.py <新 -03 根> --previous-a <成功 -02 根>`。
该参数只读取成功 A，既不恢复失败 B，也不复制 A 的验收计划或通过标记。
审计直接检查原脚本/输入字节、留存 SDF 的 3 重原子（2C/1O）、2 单键及 C-C-O 连通性、
终止记录和实际未知格式 exit 2 / JSON ok=false / 上游 exit_code=1 及原错误值。
这属于源支持的算法与接口验收，不是物理或实验科学有效性证明。

## 旧模式与证据纪律

`E:/Users/27343/Docker/openbabel-legacy-recheck-20261101-01` 通过公开 runtime-import
将历史自包含交付导入新库（not_run/candidate_saved），再 runtime-resume 独立执行原锁定合同：
8/8、accepted=true，复用已核验镜像、零模型/构建。这是现有合同重验，不算新的生成批次。
历史目录和原始只读来源均未修改。所有基础设施轮、失败生成轮、成功生成轮及旧合同重验分开计数。
Docker 与 BuildKit 原有缓存保留；构建调用不等于安装命令实际执行次数，也不宣称冷启动。

新协议 A 在最新代码下也通过独立 `runtime-import` / `runtime-resume`：导入 not_run，
再执行原锁定合同 8/8、accepted=true，action=validate，零新模型/构建。
证据位于 `-03/retained-a-recheck`，原 A 库不修改，不恢复失败轮。
恢复复制的历史 build 计数不能当本次计数；本次依据实际选择的 validate 路径。
两次拒绝负例通过公开 inspect/import/prepare：版本改为 3.1.2、或改变入口 argv，
均 selected_request_mismatch、零新模型、无资格，原工具登记清单未变。
新 B 成功后再只读核验，原失败 A/B 仍均不合格，成功 A/B 当前资格均通过。

最终完整回归 **701 项：698 通过、3 跳过**，三个提示自检通过。
源码修改、未知 subprocess/shell、库/插件/数据变化、记录/镜像/daemon 故障与超时清理的
离线回归和实测范围在可追溯索引中分别标明；不把离线故障注入当作真实业务执行。
尚不支持任意外部程序、其他发行版/架构、自定义插件或数据目录、跨主机 OCI 分发。
