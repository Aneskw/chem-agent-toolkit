# v3 JSON Skill：公开 CLI 交付与恢复

基线 a7ed138（用户确认保留 Codex planner）；当前已有真实 A/B 各 16 条锁定用例。
本轮不重新生成 Skill 或验收计划，只在新地点执行各自原合同。产品代码尚未修改。

完成目录 `E:/Users/27343/Docker/v3-delivery-cli-20261102-03`：**192/192，12 个独立 attempt**，
0 模型、0 实际 Docker build；原 A/B 全目录字节不变且当前资格仍通过。
机器索引见 `validation/v3-delivery/results-20261102.json`。

每份 Skill 六条成功路径，均执行 16/16：

1. 从正式输出安装完整包与 runtime envelope，导入新库后显式 runtime-resume。
2. 复制合格库到新位置，runtime-relocate 撤销资格，再 runtime-resume。
3. 原生输出 runtime-import 到另一新库，runtime-validate。
4. runtime-build：核验具体共享版本后新执行，不按历史配方替换版本。
5. 已完成候选显式 runtime-resume，创建独立新 attempt。
6. 缺失镜像负例之后，另建全新库从干净 envelope 导入并恢复；失败库不重跑。

安装、导入、查询、迁移、恢复全部使用 `python -m creation_pipeline`，没有调用内部 adopt/seal/
prepare 或写入 accepted。导入与迁移后的 runtime-inspect 都是 accepted=false；执行前安装拒绝；
只有新地点、新 attempt 的实际执行与当前 qualify 通过才恢复资格。内容审阅凭据仍对应未变字节，
执行资格不继承。原 revision、freeze 与具体 ToolArtifact 保留，历史执行不冒充新执行。

每份 Skill 的五条负例均按预期拒绝，共十条：JSON 原字节漂移、绑定记录漂移、镜像缺失观察、
裸包导入、归档/OCI 导入。前两项在隔离 envelope 副本修改，不重算 freeze；错误指出具体文件路径
和 expected/actual 摘要/字节数，目标库在拒绝前未创建。

镜像缺失采用专用、每命令生效的 Docker executable 边界代理：仅当 inspect 指向已绑定 image ID
才返回 No such image，其余命令委托真实 Docker。每份记录到两次故障观察，返回 runtime_blocked、
accepted=false、image_unavailable_or_changed，且新业务用例数为 0。**这是明确故障注入，不是真实
删除用户镜像**。正常镜像保留，旧绑定未变；另一个新库恢复并通过，不能把失败库的状态改为通过。

`CliGuard.cs` 同时阻止模型子进程并只记无敏感载荷的计数标记；所有 CLI 输出经现有 redact，
证据用 sanitized/write_json。全矩阵实际 build 与被触发模型命令均为 0。历史 receipt 中 build_calls
仍表示最初 1/1 构建，不计为本次调用。不存在的共享 registry 路径用于整个矩阵，表明 envelope
内完整绑定足以核验同 daemon 的具体镜像，不依赖原 registry 偶然在磁盘上。

辅助脚本先有两处状态枚举断言错误：把服务/执行报告 execution_passed 混为 summary ready 或用例
passed。01、02 各实际执行 16/16，随后脚本停止；完整保留，不作为完成矩阵证明，也不 resume。
核对生产状态定义并离线复核后，全新 03 才完成 192 条。额外 32 条单列，合同和断言未降低。

支持范围是同 daemon、具体镜像仍可核验的本地 envelope/原生输出、路径迁移及显式重验。
没有 OCI/归档分发、跨主机自动恢复、裸目录资格继承或缺失镜像的透明重建；这些路径明确拒绝。
本轮没有修改原始来源、全局配置、镜像或 BuildKit 缓存。后续整体回归另行记录；原 v1/旧自包含
模式继续保留，不能将其历史实测计数重新标成本次 v3 生成批次。
