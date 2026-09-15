# _archive —— 已归档专家包（不加载）

本目录下的专家包**已从 `marketplace.json` 摘除注册**，不会出现在 WorkBuddy 的专家列表中，也不参与加载。
仅作历史留档与回溯，**不再维护**。

---

## limfinity-engineer

| 项 | 值 |
|---|---|
| 归档日期 | 2026-09-15 |
| 归档时版本 | v1.13.1 |
| 形态 | 单体专家（`expertType` 单值，1 个 agent） |
| 取代者 | `plugins/limfinity-engineering-team`（v1.2.0，6 agents 团队型） |
| 归档理由 | 与团队包知识重叠度约 90%，且两包同时注册导致使用歧义 |

### 重叠实况（2026-09-15 实测）

- **11 个同名 references 中，10 个字节完全相同** —— 团队包由本包拆分而来，继承了全部深度文档。
- 唯一不同的是 `regression_cases.md`，且属**同名不同物**：
  - 本包版 = 「单点能力」回归用例（v1.13.1，59 行）
  - 团队版 = 「团队协作链路」回归用例（v1.1.0，72 行）
  - ⚠️ 已留存于本归档，勿与团队版互相覆盖。
- **归档前已迁出本包独有资产**（见下），确保无知识丢失。

### 独有资产已迁往团队包

| 本包资产 | 迁往 | 形式 |
|---|---|---|
| `references/display_description_archive.md` | 团队包同名文件 | 字节保真复制 |
| `references/quick_prompts_archive.md` | 团队包同名文件 | 字节保真复制 |
| `agents/limfinity-engineer.md` 的**索引层**<br>（40 科目分组索引、知识域定位、接入即用资源） | 团队包 `references/domain_index.md` | 重构为导航层（不复制正文，避免形成第二知识源） |
| 首页个性化 3 个文件路径 | 团队包 `references/domain_index.md` §四 | 补录（团队 §9 速查未收录） |
| 「控件 → FieldType 映射」表 | **未迁** —— 团队包 `limfinity_subject_fields.md` §〇 版本更完整（含备注列） | — |

### 团队包同步修复（因拆分漏改）

团队包的 `references/expert_maintenance.md` 曾从本包继承，通篇为单体结构（指针指向 `agents/limfinity-engineer.md`、
硬编码基线「CRLF=323」为本包指标）。已于 2026-09-15 重写为团队六处同步版本。

### 恢复方式

如确需恢复，执行两步即可（目录已在 git 中，历史完整）：

1. 把本目录移回 `plugins/`；
2. 在 `.codebuddy-plugin/marketplace.json` 的 `plugins` 数组补回条目：

```json
{
  "name": "limfinity-engineer",
  "source": "./plugins/limfinity-engineer",
  "description": "…（原 description，可从 git 历史 62606a5 取回）"
}
```

> ⚠️ 恢复前请确认：团队包已成为唯一维护目标，两包并存会再次引入「改一处、另一处静默落后」的风险。

---

## wps-limfinity-integration

| 项 | 值 |
|---|---|
| 归档日期 | 2026-09-15 |
| 归档时版本 | v1.1.0 |
| 形态 | 单体专家（`expertType: agent`，1 个 agent） |
| 取代者 | `plugins/limfinity-engineering-team` 的成员 `limfinity-integration-engineer`（集成工程师） |
| 归档理由 | 与团队包集成工程师职责重叠；两包并存导致「同一件事两个入口」，且单体包知识面更窄 |

### 重叠实况（2026-09-15 实测）

- `agents/wps-limfinity-integration.md` 的 DSL 铁律、WPS OAuth 约束、增量比对策略，团队包
  `agents/limfinity-integration-engineer.md`「关键铁律」已**逐条覆盖**（多选 Dictionary 传数组、
  冒号无空格、无 `private`、`puts` 不回显、空值跳过、无则新增/有变化更新/相同跳过）。
- `references/wps_limfinity_sync.rb`（14,786 B）与团队包同名文件**逐字节完全相同**。
- `references/regression_cases.md` 为**同名不同物**：本包版 = WPS/腾讯文档接口回归（R1–R3），
  团队版 = 团队协作链路回归。本包版已迁入团队包（见下）。
- `avatars/`、`README.md`、`plugin.json` 属包壳，无知识价值。

### 独有资产已迁往团队包

| 本包资产 | 迁往 | 形式 |
|---|---|---|
| 腾讯文档智能表 `smartsheet` = `smartbook/v2` 接口路径<br>（`POST /openapi/smartbook/v2/files/{fileID}/sheets/{sheetID}`） | 团队包 `references/wps_tencent_docs_sync.md` §二 | 重写（原包仅散文提及，未给接口路径） |
| 消费者个人账号鉴权**死路** + 企业应用自建表 / HiFlow 微信授权 webhook 桥接 | 同上 §二 | 重写 |
| Helper 脚本架构 `wps_list_rds2` + `require_script` + 参数化四件套 | 同上 §三 | 重写 |
| WPS 鉴权硬约束（`client_credentials` 恒 403、scope/redirect_uri 预登记、企业账号互授、`fields` 紧凑 JSON） | 同上 §一（并同步补入团队包 agent「关键铁律」） | 整理为表格 |
| 回归用例 R1–R3 | 同上 §五 | 保真迁移 |
| `references/wps_limfinity_sync.rb` | **未迁** —— 团队包同名文件字节相同 | — |
| `regression_cases.md`（团队协作版） | **未迁** —— 团队包已有团队版 | — |

> 迁入原则：**只补团队包缺失的知识**。命中检测（2026-09-15）：`smartbook`/`smartsheet`/`HiFlow`/`wps_list_rds2`
> 在团队包中命中均为 **0**，故判定为真独有；其余条目团队包已有，不重复搬运。

### 遗留注册状态（未处理）

`~/.workbuddy/plugins/installed_plugins.json` 中仍有 `wps-limfinity-integration@my-experts`
（installPath 指向 `plugins/cache/my-experts/wps-limfinity-integration/1.0.0`，即 **1.0.0 旧快照**，
落后于归档时的 1.1.0）。该文件与 `cache/` 由客户端维护，本次**未手工改动**。
如要彻底停用，需在 WorkBuddy 专家管理界面卸载该专家（或删除该条目与 cache 目录）。

### 恢复方式

1. 把本目录移回 `plugins/`；
2. 在 `.codebuddy-plugin/marketplace.json` 的 `plugins` 数组补回条目：

```json
{
  "name": "wps-limfinity-integration",
  "source": "./plugins/wps-limfinity-integration",
  "description": "Expert for integrating WPS dbsheets with Limfinity LIMS: user-level OAuth/KSO-1 auth, field mapping, and incremental sync scripts."
}
```

3. 运行 `register_expert.py <dir>` 重新注册。

> ⚠️ 恢复前请确认：知识已并入团队包，两包并存会再次引入「改一处、另一处静默落后」。
