# 技能依赖清单 · 20387体系文档专家

绑定方式：**自包含**（本专家不按名调用任何全局技能）。
共依赖 **0** 个全局技能。机器可读版见 `skill_dependencies.json`。

| 专家 | 阶段 | 技能数 | 依赖技能 |
|---|---|---|---|
| `biobank-20387-doc-expert` | 生物样本库体系文档工程师 | 0 | —（自包含：以 python-docx 直接读写 docx） |

## 判定依据（2026-09-15 实测）

本包为**单体专家**（`expertType: agent`），职责是 ISO 20387 / CNAS-CL10:2020 体系文档的撰写、校对、
责任分工编排与公文排版（管理评审报告、内审报告、内审检查表等）。其 docx 能力为**内置自实现**：

- `agents/biobank-20387-doc-expert.md` §六 给出完整 python-docx 修订模式（run 级文本替换、
  `qn('w:eastAsia')` 中文字体设置、合并单元格写文本、表格重建与 `tblBorders` 边框）。
- §五 给出公文格式硬约束（A4、方正小标宋简体标题、仿宋_GB2312 正文、行距固定值 28 磅、页码域）。

**关键词命中检测**（全包 `*.md` / `*.json`）：对任一全局技能名（`chinese-formal-report-docx`、
`docx`、`docx-official`、`pptx`、`pptx-official`、`pdf`、`table-1-generator`、`sop-writer` 等）
命中**均为 0**；全包大小写不敏感检索 `skill` / `技能`，仅命中 `references/regression_cases.md`
的泛化表述（"技能或参考资料更新后执行回归"），**无任何具体技能名**。

→ 结论：**本包零全局技能依赖，完全自包含**。清单据实为空，**并非"尚未补录"**。

> ⚠️ 若后续希望公文排版与全局技能 `chinese-formal-report-docx`（用户标准公文模板）保持一致，
> 需显式改造 agent 提示词并同步更新本清单 —— **当前不属于依赖关系**。

## 相关但不属"技能依赖"的资源

| 资源 | 说明 |
|---|---|
| IMA 知识库「生物样本资源中心」（QM 2.0、SMP-001~035、SOP-001~012、30 份标准/法规 PDF） | 外部知识库，非技能 |
| `references/regression_cases.md` | 本包回归用例（R1–R3） |
| 项目工作日志 `E:\办公文件\20387\.workbuddy\memory\YYYY-MM-DD.md` | 版本迭代留痕 |
| `clinical-translational-team` 合规成员 | **跨专家路由**：20387 体系文档撰写由其转交本专家；属专家间协作，非技能依赖 |

## 季度漂移检测

本清单 `total_skills = 0`，无需比对全局技能索引存在性；
但应复核 agent 是否新增了对全局技能的按名调用 —— 若有，须同步更新本清单与 `dependency_baseline.json`。
