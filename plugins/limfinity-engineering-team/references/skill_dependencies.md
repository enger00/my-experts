# 技能依赖清单 · Limfinity 工程专家团

绑定方式：**运行时按名调用全局技能**（不复制副本，避免版本分叉）。
共依赖 17 个全局技能。机器可读版见 `skill_dependencies.json`。

| 成员 | 阶段 | 技能数 | 依赖技能 |
|---|---|---|---|
| `limfinity-integration-engineer` | 数据集成工程师 | 0 | —（依赖包内 `references/` 深度文档，非全局技能） |
| `limfinity-cloud-backend-engineer` | 云后端与同步工程师 | 1 | `limfinity-cloudbase-sync` |
| `limfinity-miniprogram-engineer` | 小程序前端工程师 | 0 | —（依赖包内 `references/` 深度文档，非全局技能） |
| `limfinity-infra-ops-engineer` | 基础设施运维工程师 | 0 | —（依赖包内 `references/` 深度文档，非全局技能） |
| `limfinity-compliance-delivery` | 合规与交付工程师 | 16 | `chinese-formal-report-docx`, `docx`, `docx-official`, `pptx`, `pptx-official`, `xlsx-docx-chart-embed`, `excel`, `pdf-processing-pro`, `markitdown`, `style-rewrite`, `sop-writer`, `regulatory-drafter`, `mindmap-html-generator`, `markdown-mermaid-writing`, `iso-13485-certification`, `hipaa-compliance` |

## 季度漂移检测

重跑 `skill-asset-audit` 的 `scan_skills.py` 更新技能索引后，再重跑本脚本，比对 `skill_dependencies.json` 中的技能是否仍然存在于索引中。若某技能消失，说明上游已删除或改名，需更新对应成员 MD。
