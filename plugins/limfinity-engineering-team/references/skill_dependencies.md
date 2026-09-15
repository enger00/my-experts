# 技能依赖清单 · Limfinity 工程专家团

绑定方式：**运行时按名调用全局技能**（不复制副本，避免版本分叉）。
共依赖 30 个全局技能。机器可读版见 `skill_dependencies.json`。

| 成员 | 阶段 | 技能数 | 依赖技能 |
|---|---|---|---|
| `limfinity-integration-engineer` | 数据集成工程师 | 12 | `limfinity-query-builder`, `limfinity-subject-crud`, `limfinity-value-ops`, `limfinity-udf-config`, `limfinity-workflow-ops`, `limfinity-messaging-errors`, `limfinity-communication`, `limfinity-file-ops`, `limfinity-reports-templates`, `limfinity-picker-ui`, `limfinity-integration`, `wps-dbsheet-integration` |
| `limfinity-cloud-backend-engineer` | 云后端与同步工程师 | 1 | `limfinity-cloudbase-sync` |
| `limfinity-miniprogram-engineer` | 小程序前端工程师 | 1 | `limfinity-miniapp-ui` |
| `limfinity-infra-ops-engineer` | 基础设施运维工程师 | 0 | —（依赖包内 `references/` 深度文档，非全局技能） |
| `limfinity-compliance-delivery` | 合规与交付工程师 | 16 | `chinese-formal-report-docx`, `docx`, `docx-official`, `pptx`, `pptx-official`, `xlsx-docx-chart-embed`, `excel`, `pdf-processing-pro`, `markitdown`, `style-rewrite`, `sop-writer`, `regulatory-drafter`, `mindmap-html-generator`, `markdown-mermaid-writing`, `iso-13485-certification`, `hipaa-compliance` |

## 知识分层（重要，避免误判为重复）

本团的知识来自**三层**，**职责不重叠**，不得互相替代：

| 层级 | 载体 | 内容性质 | 例 |
|---|---|---|---|
| **DSL/API 参考层** | 上表所列全局技能（按名调用） | Limfinity **通用** 脚本 API 与表单/报表/工作流方法签名 | `send_email`、`open_spreadsheet_file`、`show_message`、`qb.compare`、`advance_workflow`、`params[:udf_config]` |
| **集成实操层** | 全局技能 `limfinity-integration`、`wps-dbsheet-integration` | **REST API 全路径**、WPS/KSO-1 鉴权、接口清单与排错顺序 | `POST /api` + `gen_token`/`import_subjects`/`run_script`；WPS KSO-1 签名与 refresh_token 续期 |
| **项目实战层** | 包内 `references/*.md` | 本项目**实测踩坑**与架构结论 | 取值水合坑、`0x05189`、Supabase 同步、Taro 构建铁律 |

**判定依据一（DSL/API 参考层，2026-09-14 全量核验）**：包内文档对 `send_email` / `call_external_service` /
`open_spreadsheet_file` / `create_zip_file` / `show_message` / `show_alert` / `qb.compare` /
`qb.and` / `qb.state` / `advance_workflow` / `start_workflow` / `udf_config` / `skip_UDF` /
`display_field` / `run_report` / `extra_data` / `qb_filters` / `AmCharts` / `search_guid` /
`tool_groups` / `Liquid` 的命中数**均为 0**——即该层知识在包内完全缺失，仅存在于全局技能。

**判定依据二（集成实操层，2026-09-15 核验）**：包内文档对 `REST API` / `import_subjects` /
`subject_details` / `search_subjects` / `调用接口清单` / `排错顺序` 命中**均为 0**；`KSO-1` /
`refresh_token` **仅出现在 `wps_limfinity_sync.rb` 代码内**，文档层从未解释该鉴权流程。
→ 该层同样属包内缺失，须走全局技能。

**已核验为「包内已充分覆盖、故不声明」的技能**：`limfinity-vm-ops`
（包内 `limfinity_vm_ops.md` 12KB 为其超集，6 个主题一一对应且更详细）。

> ⚠️ **冲突项**：`raise_message` 语义两处不一致。全局技能 `limfinity-messaging-errors` 称其为
> 「中断脚本、无 stack trace 的友好提示」；包内 `run_script_push_sync.md` §实测称「**会抛异常**」
> （本环境行为）。以**包内实测为准**，全局技能仅作方法签名参考。

> ⚠️ **外部分叉提示**：全局技能 `limfinity-integration` 自带一份 `limfinity_subject_fields.md`，
> 与本包同名文件**字节相同**（21295 B）。二者会各自演进 → 改字段表时须**同步两处**，或明确以本包为准。

## 季度漂移检测

重跑 `skill-asset-audit` 的 `scan_skills.py` 更新技能索引后，再重跑本脚本，比对 `skill_dependencies.json` 中的技能是否仍然存在于索引中。若某技能消失，说明上游已删除或改名，需更新对应成员 MD。
