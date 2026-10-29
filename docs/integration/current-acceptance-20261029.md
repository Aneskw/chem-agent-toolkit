# 当前验收结论与共享层交付（2026-10-29）

当前混合后端下已有五个独立成功批次，共 72 条 Docker 执行记录全部 passed。最新 Open Babel run74 已满足 prepared、固定 digest、镜像构建、全部业务/原生检查、独立审计、轮后回归和实验记录要求。共享范围扩展后的当前组合版本离线 **647 OK (3 skipped)**，三个自检全绿；没有 push。

当前受测功能提交 2c1313c，最新组合日志 shared-environment-wait-combined-tests-20261029.log；后续文档/索引提交不改变受测实现。最新同键等待与真实重建证据见下。

这证明已测试场景能走通当前合并的 pipeline，不是所有 Skill 首次自动成功、全阶段 DeepSeek 或独立科学有效性证明。前四成功轮不因本次复核变成新的执行；失败轮及其原始结果全部保留。原生阶段使用 Codex CLI gpt-6-astra，结构化阶段使用 DeepSeek deepseek-v4-pro。

## 成功批次

| 场景 | 成功轮 | passed/total | 业务证据 |
| --- | ---: | ---: | --- |
| 描述符 A | 59 | 15/15 | 原入口、乙醇数值、非法输入拒绝、实际 JSONL 文件 |
| 描述符 B | 62 | 16/16 | 同来源的独立生成/规划/执行，完整文件与拒绝义务 |
| 原子映射 | 64 | 22/22 | 正常/离去基团、重复/缺失/额外映射与语法拒绝、混合文件 |
| ASE 几何 | 65 | 11/11 | 实际坐标距离、检查完成但约束失败、非法请求、输入保护 |
| Open Babel | 74 | 8/8 | 真实系统 executable、原入口转换与留存 SDF、未知格式拒绝、字节保护 |

机器索引：[current-acceptance-results.json](../../validation/deepseek-api/current-acceptance-results.json)。五个 output 的冻结 bundle、当前镜像身份与各自正式库资格均重新核验通过。每个证据根保存 current-audit-after-shared-wait.json 和 current-library-inspection-after-shared-wait.json；这些复核只做元数据探测，不重新执行业务或发模型请求。

## run74 的硬证据

根目录：`E:\Users\27343\Docker\acceptance-openbabel-run74-20261029`，build `20261029T194522-1929c499`。受测实现起点 c103bc1，19:45:22–20:00:28，ready，6 次准入调用（3 原生、3 结构化规划）。结构化回执汇总现在正确显示实际 DeepSeek 模型、耗时和原始 token 字段；usage_scope 区分最终响应与全部供应商请求/费用。

- 规划先具名修正引用，再修正 output-format 参数索引，第三次 prepared。材料冻结，基础为 python@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd。
- image.id：sha256:a65227fdd4f7f501348dffa9653b4b50bea320362ffa4604ee4ec338e4100f1a。共享环境 hit b369a43e... / sha256:cb50e4d0a1d0bb065ddcf409067c8dfe698d4f0b6c6b90bd62824f1e4beed56d，核验 ENV/WORKDIR/层及工具包字节。
- execution/report.json 全部 8 条 passed。原脚本和 CCO+CRLF 输入保持原字节；正常 SDF 经直接模式及原生解析检查，含 3 重原子（2 C、1 O）、2 单键、C-C-O 连通性和完整终止记录。未知格式实际 exit2，JSON ok:false、上游 error 和 exit_code 均保留。
- 独立 acceptance-audit.json 为 passed:true、missing:[]，包括冻结/当前资格、真实 SDF、原入口身份和独立 obabel -V 元数据。首个审计误用了 --version，失败回执另存 acceptance-audit-before-version-flag-fix.json；修复审计参数后仅重做元数据核验，没有重跑或更改业务测试。
- 本轮全部五项原生检查通过。合入后续严格字段校验后，五成功批次共 30 项原生声明仍合法，并与原锁定映射完全一致；证据 native-check-conformance-accepted-five-20261029.json。最新主分支轮后日志 acceptance-run74-postflight-tests.log 为 639 OK (3 skipped)，三个自检全绿。

## 共享层已经实现的部分

当前关系为 Skill → 已核验依赖环境 → 薄工具镜像 → 每任务隔离容器。相同固定配方跨 Skill/批次复用环境；每个 Skill 继续有自己的冻结材料和业务资格。安装失败不登记半成品，不修改旧绑定。缓存按实际 daemon/image 身份核验，标签仅作传输，未锁完整依赖闭包的环境不宣称可重复重建。

当前可显式配置同主机共享目录 CHEM_AGENT_SHARED_ENVIRONMENTS，跨多个 pipeline 工作副本使用；缓存位置不写入冻结材料。公共双 checkout/双进程测试在全新 shared-registry-cross-checkout-20261029-02 通过：1 次环境构建、2 次薄工具构建，第二进程 hit 同一环境，两个隔离输出正确；0 模型/化学调用，系统环境设置未修改。

并发补强：两个同键请求现在于原构建时限内等待/复查，不直接 busy 停止；过期或取消不删除别人的锁，崩溃锁不按年龄抢占。真实双 checkout/双进程 shared-registry-concurrent-checkouts-20261029-01 已制造实际文件锁争用，两个原请求均自动完成，无需操作者续跑；仅 1 次环境构建、2 次薄构建。另修正预算耗尽后仍可能启动薄构建的边界。新的真实 Open Babel 显式重建补验 shared-runtime-rebuild-compatibility-20261029-03 仍为环境 hit、仅 1 次薄构建，8/8 当前合同执行通过，0 模型且原包/冻结/源库资格/缓存记录不变。这些不是新的生成批次。

已通过真实 Docker 两工具复用、ENV/WORKDIR/层继承、构建失败隔离和同键并发试验。RDKit 两原工具共用一次环境构建、生成两个薄镜像，四条化学业务检查通过；基础设施/并发试验不冒充新的完整 Skill 生成验收。run69–73 的五轮观测为 2 次环境构建调用、3 次 hit、5 个薄工具镜像；不从调用数推导安装次数、速度或磁盘收益。

安装/迁移补验也已通过：公共脚本在全新 `shared-runtime-install-compatibility-20261029-02` 中确认旧通过标记不被导入/复制继承，两次重验 16/16；`shared-runtime-rebuild-compatibility-20261029-02` 中显式重建仍命中环境，只调用一次薄工具构建，8/8 再次通过。两项均 0 模型，原正式库资格、原包和环境缓存记录不变。这些重验不增加独立生成批次数，原五批次 72 条计数保持原范围。

设计及证据：[共享层设计](shared-tool-layer-current-design.md)、[共享环境协议](../pipeline/shared-environments.md)。后续[精确 ToolArtifact 解析协议](../pipeline/shared-tool-artifact-protocol.md)已设计，但完整 Tool 制品复用、规划前跳过环境模型、自动兼容合并、常驻 worker、结果缓存和跨主机 OCI 制品发布尚未实现。当前不把全部 Skills 塞进一个会原地升级的环境，也没有删除旧镜像。

## 最新代码复核的补强

真实轮次驱动修正旧草稿补丁、CRLF 材料保真、自包含原生检查、文件/JSON 通道、正则正例预检、不可满足的等值期望及具名诊断。原比较器和源码/覆盖约束保留，未靠删除失败用例或放宽业务义务换取成功。

额外静态反例发现未知原生检查字段会被忽略：已改为按公开字段契约具名拒绝，并将同一字段集传给作者和审阅。首轮回归暴露合法 candidate 路由字段缺失，修正后 639 项全绿；没有将失败测试改成通过期望。说明见[原生检查字段](../pipeline/native-check-fields.md)。
