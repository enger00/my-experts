---
name: title-review-material-audit
description: Operational playbook for auditing NU2B senior title application materials — directory intake and completeness checking, PDF/document evidence pipeline, paper metadata parsing (author/affiliation/journal), duplicate & shared-achievement detection, and the local query service. Load whenever the task involves the application material database, matching PDF originals to declared achievements, flagging cross-applicant shared papers/projects, batch Word-to-PDF conversion, or any re-run of the audit scripts under E:\办公文件\高级职称审核.
---

# 职称申报材料核查作业手册

本技能是"高级职称评审专家团"（nu2b-title-review-team）的**作业侧**知识库，与 `title-review-policy`（政策侧：条款、权重、门槛数值）互补。

**凡涉及"材料怎么收、怎么判、怎么查、怎么标"的问题，一律先查本技能的 references/。** 这些规则全部来自 2026 年度 229 人真实材料的实战踩坑，重跑时直接照做即可，不要重新试错。

## 作业根目录

`E:\办公文件\高级职称审核\`（下文 `$R` 指代该目录）。所有脚本以 `_` 开头，均为**单文件、零依赖**（除 PyMuPDF / LibreOffice），可直接 `python <script>.py` 重跑。

## 资料清单

| 文件 | 内容 | 何时查 |
|------|------|--------|
| **references/batch-runbook.md** | **新批次受理作业 SOP（审核方视角）**：启动前六问、角色分工矩阵、P0–P6 七阶段与各 Gate、交付物清单、最小可用路径 | **收到新一批材料时先看这篇**，按它编排全局 |
| references/material-intake.md | 材料目录归集、完整性核查判据与判定局限、2026 年度终稿结果 | 收材料、判缺件、出核查报告 |
| references/pdf-pipeline.md | 扁平化目录规范、PDF 索引与 doc_id、Word→PDF 转码、按正文识别论文、院文献库对接 | 找原文、转码、配附件、预览 404 |
| references/shared-achievement.md | 三类"重复/共用"判定：串档、跨申报人共用、同人占名额 | 做共用角标、判重复申报 |
| references/paper-meta-parsing.md | 作者/单位/刊名解析规则与全部踩坑、本院（二附院）判定口径 | 判第一作者、通讯作者、是否本院 |
| references/review-service.md | 查询服务架构、数据库表、HTTP 接口、前端改动双检铁律 | 改服务、加字段、加角标、导出 |

## 使用规则

0. **新批次第一件事**：读 `references/batch-runbook.md`，按 P0–P6 编排；先向用户确认"启动前六问"，确认后再执行。**不要一上来就动手跑脚本**。
1. **先分清"政策口径"与"作业口径"**：分值、权重、年限查 `title-review-policy`；判据、脚本、踩坑查本技能。
2. **只读铁律**：主库 `_apply_db.sqlite3` 以 `mode=ro` 打开，是**连接级**只读（ATTACH 的库同样不可写）。任何写操作一律走独立可写库（`_review.sqlite3` / `_split.sqlite3` / `_sr_doc.sqlite3` / `_papermeta.sqlite3`）。
3. **改库前先备份**：主库已有 12 个 `.bak_*` 即为此铁律的产物。
4. **只出清单不自动改**：凡判定结果可能改变他人材料归属/认定的（串档改指、共用角标），默认 dry-run 出 CSV，经人工确认后再 `--apply`。
5. **判定局限必须在交付物中声明**：系统只能判"有无该文件"，不能判内容是否填写、是否盖章、是否落在时间窗；无语义文件名（如 `534-1141-1-SM.pdf`）无法识别。
