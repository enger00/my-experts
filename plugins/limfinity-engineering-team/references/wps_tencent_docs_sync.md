# WPS / 腾讯文档 → Limfinity 对接（鉴权 · 智能表 · Helper 架构）

> **来源**：2026-09-15 由独立专家包「wps-limfinity-integration」（WPS-Limfinity 对接专家）迁入，
> 该包随后归档至 `my-experts/_archive/wps-limfinity-integration/`。
> **迁入原则**：仅保留团队包中**缺失**的知识（`smartbook`/`smartsheet` 接口、`HiFlow` 桥接、
> `wps_list_rds2` Helper 架构、WPS 鉴权硬约束）。**通用 DSL 铁律、字段映射清单、`.rb` 源码不复制**，
> 一律以既有文档为准（见 §六）。

---

## 一、WPS 多维表：用户级 OAuth 硬约束

> 实测来源：2026-08-07 跑通「WPS 多维表 → Limfinity 来访人员登记表」增量同步。

| # | 约束 | 后果 / 说明 |
|---|---|---|
| 1 | **必须用用户级 token** | `client_credentials` 模式恒返回 **403**，不可用 |
| 2 | `scope` 须在 WPS 开放平台后台**预开通** | 未开通时授权页不报错，取数阶段才 403 |
| 3 | `redirect_uri` 须在后台**预登记** | 与登记值不一致直接拒绝授权 |
| 4 | **企业账号 OAuth 仅允许企业账号授权** | 个人账号无法授权企业表 |
| 5 | `fields` 是**单行紧凑 JSON 字符串** | 不是对象；须 `JSON.parse` 后再取值 |
| 6 | `refresh_token` 必须**持久化** | 否则每次都要人工重新走授权 |

签名算法：**KSO-1**（头字段与排序规则见 `wps_limfinity_sync.rb` 实现）。

---

## 二、腾讯文档智能表（smartsheet）接入

### 2.1 接口本质

腾讯文档「智能表」底层即多维表格 **`smartbook`**，走 **v2** 接口：

```
POST /openapi/smartbook/v2/files/{fileID}/sheets/{sheetID}
```

### 2.2 鉴权死路与替代方案

| 方案 | 可行性 | 说明 |
|---|---|---|
| 消费者**个人账号** token | ❌ 死路 | 个人账号无法授权企业级智能表 |
| **企业应用自建表** | ✅ 推荐 | 用企业自建应用建表，走应用级 token |
| **HiFlow 微信授权 webhook 桥接** | ✅ 备用 | 借 HiFlow 流程接收授权事件，再回写 Limfinity |

> ⚠️ 智能表与 WPS 多维表**接口不同**：WPS 走 KSO-1 签名 + `fields` 紧凑 JSON；
> 腾讯文档走应用级 token + `smartbook/v2` 路径。**字段取值与分页方式不可互相套用。**

---

## 三、可复用 Helper 脚本架构

把**通用取数方法**放进 Limfinity Helper 脚本，主脚本按名引用——**换表只改参数，方法体不动**。

```
Helper 脚本：wps_list_rds2            # 通用：拉取源表记录
主脚本：    require_script 'wps_list_rds2'
            传参 file_id / field_map / subject_type / biz_key_fields
落库：      sync_to_database          # 增量比对：无则新增、有变化则更新、完全相同跳过
```

- **参数化四件套**：`file_id`、`field_map`、`subject_type`、`biz_key_fields`（业务唯一键）。
- 调试用 `raise_message "内容"` 看中间结果（`puts` 在 limfinity 脚本环境**不回显**）。
- Helper 库机制与顶层作用域铁律详见 `limfinity_script_runtime.md`。

---

## 四、字段映射与增量策略（⑦ 来访人员登记表）

- 源字段名 → Limfinity **中文系统字段名**，一一对应；字段精确清单见
  `limfinity_subject_fields.md`（⑦ 来访人员登记表，已与本同步链路完全印证）。
- 增量唯一键：按**业务唯一键**比对，**无则新增 / 有变化则更新 / 完全相同跳过**。
- ⚠️ 不得臆造表结构；新表接入前先确认目标科目必填字段是否已被映射全覆盖。

---

## 五、回归用例

> 迁自原包 `references/regression_cases.md`。WPS 开放平台 / 腾讯文档接口、签名算法、
> 授权流程变更后执行。

### R1 · WPS 多维表 → Limfinity 来访人员登记表

- **触发输入**：帮我把 WPS 多维表对接到 Limfinity 来访人员登记表
- **执行要求**：字段映射与增量唯一键明确，不得臆造表结构
- **预期产出**：对接脚本 + 字段映射表 + 同步结果核对
- **验收标准**：① 目标表必填字段全覆盖 ② 增量唯一键说明清晰 ③ 失败重试与日志完整

### R2 · OAuth 授权码与 KSO-1 签名配置

- **触发输入**：WPS 多维表 OAuth 授权码和 KSO-1 签名怎么配置？
- **执行要求**：给出可复现的配置步骤与签名构造过程
- **预期产出**：配置清单 + 签名构造示例 + 常见报错对照
- **验收标准**：① 授权码换 `access_token` 流程完整 ② KSO-1 签名头字段与排序规则准确 ③ 令牌持久化与过期续期方案明确

### R3 · 腾讯文档智能表同步至 Limfinity

- **触发输入**：腾讯文档智能表（smartsheet）怎么同步到 Limfinity？
- **执行要求**：区分 smartsheet 与 WPS 多维表的接口差异
- **预期产出**：同步脚本 + 接口差异说明
- **验收标准**：① 接口调用与字段取值正确 ② 与 Limfinity 落库衔接完整 ③ 分页与限流处理明确

---

## 六、与既有文档的关系（防重复）

| 内容 | 权威位置 |
|---|---|
| 完整可运行同步脚本（`json`/`db` 双模式，含增量同步） | `wps_limfinity_sync.rb` |
| KSO-1 / `refresh_token` 实现细节 | `wps_limfinity_sync.rb`（代码层） |
| 科目字段精确清单（⑦ 来访人员登记表） | `limfinity_subject_fields.md` |
| DSL 运行模型 / Helper 库机制 / 顶层作用域 | `limfinity_script_runtime.md` |
| DSL 取值与水合方向 | `limfinity_value_hydration.md` |
| DSL 铁律（冒号无空格 / 多选 Dictionary 传数组 / 无 `private` / `puts` 不回显 / 空值跳过） | `limfinity_script_runtime.md` + `limfinity_value_hydration.md` + `agents/limfinity-integration-engineer.md` |
| **本文件** | WPS 鉴权硬约束 + 腾讯文档 `smartbook/v2` + Helper 脚本架构 + 回归用例 |
