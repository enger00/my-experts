# 技能依赖清单 · 会务礼宾专家团

绑定方式：**包内自有技能 + 运行时按名调用全局技能**（不复制全局技能副本，避免版本分叉）。
共依赖 **1** 个技能 —— 且为**包内自有** `award-seating`；**外部全局技能 0 个**。机器可读版见 `skill_dependencies.json`。

| 成员 | 阶段 | 技能数 | 依赖技能 |
|---|---|---|---|
| `meeting-protocol-team-team-lead` | 礼宾总监（主理人） | 0 | —（编排与汇编，不直接调用技能） |
| `xizheng` | 排席专家 | 1 | `award-seating`（**包内 `skills/` 物理内嵌**，非全局技能） |
| `zhenwuwu` | 质检官 | 0 | —（跨表逐格核查，依赖输入文件与铁律清单） |
| `liubizheng` | 公文专家 | 0 | —（依赖 `references/gongwen-writing-guide.md`，非技能） |

## 技能归属说明（重要）

| 技能 | 归属 | 载体 | 声明位置 |
|---|---|---|---|
| `award-seating` | **包内自有** | `skills/award-seating/`（`SKILL.md` + `assets/` 打印模板 + `scripts/` 生成器） | `plugin.json` 的 `skills` 字段 + `agents/xizheng.md` frontmatter `skills: [award-seating]` |

> 与其他专家包不同，本团的 `award-seating` **不是全局技能**，而是随包分发的物理技能；
> 因此**不存在版本分叉风险**，也**不出现在** `~/.workbuddy/skills/` 下。包内不得再复制一份到全局，
> 也不得从全局反向覆盖。

## 判定依据（2026-09-15 实测）

1. `agents/xizheng.md` frontmatter 显式声明 `skills: [award-seating]`；
   `.codebuddy-plugin/plugin.json` 的 `skills` 字段声明 `./skills/award-seating`，物理目录存在且完整
   （`SKILL.md` + `assets/打印单模板.xlsx`、`打印模版.docx` + `scripts/` 4 个脚本）。
2. 全包大小写不敏感检索 `skill` / `技能`：除 `award-seating` 自身外**未出现任何全局技能名**
   （`chinese-formal-report-docx`、`docx`、`docx-official`、`pptx`、`pptx-official`、
   `xlsx-docx-chart-embed`、`pdf` 等命中均为 0）。
3. `liubizheng`（公文专家）依据 `references/gongwen-writing-guide.md`（507 行）与 GB/T 9704 规范
   起草公务文书，走**内置参考资料**而非全局技能。

→ 结论：**外部全局技能依赖为 0**，本团自包含（唯一技能 `award-seating` 为包内资产）。

> ⚠️ 若后续希望公文产出统一走全局技能 `chinese-formal-report-docx`（用户标准公文模板），
> 需显式改造 `liubizheng` 提示词并同步更新本清单 —— **当前不属于依赖关系**。

## 内部资料红线

`references/gongwen-writing-guide.md` 属**内部资料，不得随任何交付物外发**（见主理人 SOP
与 `liubizheng` 角色定义）。该约束与技能依赖无关，但属交付合规铁律，故在此并列提示。

## 季度漂移检测

`award-seating` 为包内技能，无需比对全局技能索引；但应复核各成员是否新增了对**全局技能**的按名调用
—— 若有，须同步更新本清单与 `dependency_baseline.json`。
