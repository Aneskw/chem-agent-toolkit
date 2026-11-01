# 必需交付路径与资格协议

新生成的交付使用 delivery protocol **2**。运行模式仍可选原自包含模式或本机共享工具模式；
交付协议版本和 ToolArtifact ABI 是不同对象，升级路径门禁没有更改共享工具 ABI。

调用方明确提出的文件位置是交付契约。相同内容出现在其他目录不满足要求，
Windows 上存在的大小写近似路径也不能代替冻结的精确路径。要求不由作者或 planner 改写。

`artifacts/layout.py` 在配置预检和每个候选编写前，直接读取原始 `prompt`、`task`、
`constraints`、`notes`，以及适用的运行要求/约束，编译 `delivery_layout`。候选覆盖仅适用于
该候选；默认要求适用于所有候选。当前确定性文本语法支持：

- `Deliver exactly SKILL.md, scripts/main.py and deps.lock;`（或 Ship/Package exactly/only）；
  也支持 `Deliver EXACTLY two files: ...` 和 `交付仅包含：...`。
- `Required files: scripts/main.py, resources/input.dat;`，规定必需文件但允许其他文件。
- `` `deps.lock` must be at package root. ``、`deps.lock is required in the package root.`、
  `` `deps.lock`必须位于包根目录。 ``。

明确列表不符合可解析语法、路径不安全或彼此冲突时，预检具名拒绝，不让模型猜测清单。
仅提及依赖声明文件、来源文件或例子不会自动增加交付路径要求。对于其他措辞、含复杂
标点的文件名或明确的机器配置，可以使用通用字段（不需要手工验收计划）：

```json
{
  "constraints": {
    "delivery_layout": {
      "required_files": ["deps.lock", "data files/input.bin"],
      "exact_files": ["SKILL.md", "scripts/main.py", "deps.lock", "data files/input.bin"]
    }
  }
}
```

两个键均可省略其一；`exact_files` 同时规定全部文件必须存在。通配符、目录存在性、负向
路径规则及任意自然语言解释不在 v1 路径子协议的确定性范围，不能宣称已经穷尽需求语义。
显式路径优先于默认五类目录规则；凭据排除、安全相对路径、文件/包大小限制仍然生效。
`SKILL.md` 仍由原有包结构检查强制要求，不对低层运行时工具材料额外施加 Skill 结构。

冻结对象 `inputs.layout={version:1,payload,sha256}` 保存原文快照、原字段/引用、必需文件和
可选完整文件集，进入独立 fingerprint 和 revision ID。校验器从原文快照重新编译并比较
契约，避免删除一个必需文件后仅重新计算 layout hash 即可通过。作者收到同一对象，
helper finish 和 host finish 使用同一门禁；独立审阅继续检查实际包和原始来源。

准备环境前按实际包再检查。失败的 `delivery_layout_mismatch` 指向 content 路径并撤销
内容通过；不会先消费环境规划模型调用。最终 `qualify` 在 no-execution 分支和 Docker
证据分支之前检查文件清单，旧 passed/accepted 标记不能豁免。`runtime_request` 再检查
冻结清单；实际包与冻结清单的对应仍由原有 byte manifest、镜像内清单和执行器核验。
安装、导入及恢复沿用冻结对象，不给新的交付继承执行资格。

错误包括 code、具体 path、expected、actual、同名其他路径、实际交付清单和原字段/引用。
精确列表出现额外文件也单独报错，不静默移动文件，不改原需求或原始来源。

普通命令可重审历史交付：

```text
python -m creation_pipeline check OUTPUT_OR_PACKAGE --config ORIGINAL_CONFIG.json
```

该命令不调用模型、不执行业务、不授予新资格、不修改旧包；新输出已有冻结要求时同时
核验冻结契约和提供的配置，外部宽松配置不能覆盖冻结要求。无 `--config` 的新输出使用
自身冻结要求。standalone package 的结构检查也不等于安装或执行批准。

旧 delivery protocol 1 继续按原冻结协议读取。没有记录调用方原文的历史包无法可靠还原
位置要求，不能宣称通过了新门禁；请提供原配置做静态审计，或以原要求生成并独立审阅、
执行新修订。本轮不自动改写旧 freeze/revision/资格，也不把历史 Docker 通过变成路径证明。
包路径改变会改变工具实现闭包，因此不能命中路径不同的旧 ToolArtifact；不同 Skill 的
文案、测试和原始请求仍各自冻结，完整工具命中也不省略这些检查。
