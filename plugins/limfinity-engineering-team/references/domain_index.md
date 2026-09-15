# Limfinity 工程知识索引（导航层）

> **来源**：2026-09-15 由单体专家「limfinity-engineer」迁移而来（该包已归档，由本团队包取代），
> 并入其独有的索引层资产。
> **用途**：**导航** —— 快速定位「某个知识在哪个文件」。**正文一律以目标文件为准，本文不复制正文**，
> 避免形成第二个知识源（版本分叉）。

---

## 一、40 个真实科目分组索引

> 逐字段标注（`+新增` / `=已有` / `×跳过`）见 `limfinity_subject_fields.md`；此处仅为**分组导航**。
> 来源：易云老师提供的 43 张 Limfinity 科目截图（2026-08-15 逐张识别），覆盖本院 Limfinity（RURO LIMS）全部 40 个真实科目。
> ⚠️ 凡涉及**字段映射、小程序对接、科目同步、DSL 落库**，直接查 `limfinity_subject_fields.md` 取真实字段，
> **勿再要求用户提供科目导出 JSON 或截图**。

- **制度文件管理**：① 文件目录管理 ② 文件分发管理 ③ 文件废止管理 ④ 合规与审批文件 ⑤ 法规更新日志
- **人员能力建设**：⑥ 人员信息管理 ⑦ 来访人员登记表 ✅（已与 WPS 同步脚本完全印证）⑧ 人员能力评审记录 ⑨ 入职培训记录 ⑩ 人员年度培训计划
- **资源资产管理**：⑪ 设备资产登记 ⑫ 设备校准记录 ⑬ 实验物资出入库记录 ⑭ 设备维保日志
- **环境安全监控**：⑮ 环境巡查记录 ⑯ 环境消毒记录 ⑰ 不良事件登记 ⑱ 监控系统核查记录 ⑲ 危险化学品周统计表
- **质量体系运行**：⑳ 质控活动记录 ㉑ 质量控制计划 ㉒ 方法确认验证记录 ㉓ 风险识别与应对 ㉔ 投诉与处理记录 ㉕ 不符合项清单 ㉖ 库存样本核查记录 ㉗ 年度目标监测统计 ㉘ 战略规划记录
- **会议评审管理**：㉙ 文件评审会议记录 ㉚ 管理委员会会议记录 ㉛ 内部审核 ㉜ 管理评审
- **小程序缺失科目（待建）**：㉝ 实验化学品及耗材 ㉞ 科室 ㉟ 系统配置（跳过）㊱ 样本信息共享 ㊲ 实验预约信息 ㊳ 共享样本申请记录 ㊴ 温湿度记录 ㊵ 门禁出入记录

---

## 二、知识域 → 文件定位速查

| 要查的问题 | 去读 |
|---|---|
| Limfinity 脚本不执行 / `NameError` / 取值为空 / 跑不完 / 「立即运行」验证不了 | `limfinity_script_runtime.md` |
| 批量枚举 vs 引用字段取值为空 / 水合方向 / 院区判归属 / 前缀门禁 | `limfinity_value_hydration.md` |
| 科目字段精确清单 / 控件 → 小程序 FieldType 映射 / 与妙哒 33 类型对应 / 缺失科目 | `limfinity_subject_fields.md`（§〇 类型映射规则） |
| `run_script` 推送同步 / 双入口红线 / 自证型脚本调试法 | `run_script_push_sync.md`（§8） |
| `.56` Supabase 同步 / frp 反向隧道 / 自定义字段 / 自托管运维 / nssm 服务 / 文件附件 Storage | `supabase_sync.md`（§9 frp、§10 自定义字段、§11 运维、§12 nssm、§13 文件附件） |
| N1 公网隧道（独立 frp + 阿里云 Caddy）+ 微信云函数 `limfinityProxy` → CloudBase | `n1_frp_tunnel_cloud_fn_sync.md` |
| 虚拟机运维：Ubuntu 升级 / PG 大版本迁移 / netplan 静态 IP / VM Console / logrotate | `limfinity_vm_ops.md` |
| 小程序 Taro 构建 / UI 布局铁律 / CLI 自动化预览发布 / 自定义 tabBar 透明 | `miniprogram_dev_experience.md`（§10 布局、§10.9 CLI、§10.11 tabBar） |
| WPS 多维表 → Limfinity 增量同步（可直接运行的完整脚本） | `wps_limfinity_sync.rb` |
| WPS OAuth/KSO-1 鉴权硬约束 / 腾讯文档智能表 `smartbook/v2` / HiFlow 桥接 / Helper 脚本架构 `wps_list_rds2` | `wps_tencent_docs_sync.md` |
| **通用 DSL 方法签名**（`send_email` / `qb.compare` / `advance_workflow` / `params[:udf_config]` …） | **全局技能**，见 `skill_dependencies.md`「知识分层」 |
| 本包怎么维护（改哪几处、怎么校验） | `expert_maintenance.md` |
| 改完怎么回归验证 | `regression_cases.md` |

---

## 三、接入即用资源

### 3.1 本包 references（深度文档，正文在此）

| 文件 | 内容 |
|---|---|
| `limfinity_script_runtime.md` | Limfinity 脚本运行模型（Helper 库 / ScheduledScript 入口 / 顶层作用域铁律 / 立即运行≠cron） |
| `limfinity_subject_fields.md` | 字段精确对照表（基于 43 张真实截图，含类型映射规则） |
| `limfinity_value_hydration.md` | Ruby DSL 取值与水合模型（含 v8 字段内部名以数字「1」结尾的取值缺陷） |
| `run_script_push_sync.md` | `run_script` 外部触发实时同步完整模式（推送代理 + Helper Script + nssm） |
| `supabase_sync.md` | 方案C：内网 `.56` 直连同步 Limfinity → Supabase 完整实战（§9–§13） |
| `n1_frp_tunnel_cloud_fn_sync.md` | N1 公网隧道 + 微信云函数同步 |
| `limfinity_vm_ops.md` | 虚拟机基础设施运维实战知识库 |
| `miniprogram_dev_experience.md` | Taro 小程序开发与 Supabase 后端完整经验 |
| `wps_limfinity_sync.rb` | WPS ↔ Limfinity 同步脚本（⚠️ 已对 `APP_KEY` 脱敏） |
| `wps_tencent_docs_sync.md` | WPS 鉴权硬约束 + 腾讯文档智能表 `smartbook/v2` + Helper 脚本架构 + R1–R3 回归用例（2026-09-15 由 wps-limfinity-integration 迁入） |
| `expert_maintenance.md` | 本包维护约定 |
| `regression_cases.md` | 团队协作链路回归用例 |
| `domain_index.md` | 本文件（导航层） |
| `display_description_archive.md` | displayDescription 原文归档（规范压缩副产品，勿删） |
| `quick_prompts_archive.md` | quickPrompts 归档 12 条（规范压缩副产品，勿删） |

### 3.2 全局技能（按名调用，不复制副本）

- **DSL/API 参考层**（通用方法签名）：`limfinity-query-builder`、`limfinity-subject-crud`、`limfinity-value-ops`、`limfinity-udf-config`、`limfinity-workflow-ops`、`limfinity-messaging-errors`、`limfinity-communication`、`limfinity-file-ops`、`limfinity-reports-templates`、`limfinity-picker-ui`
- **UI 参考层**：`limfinity-miniapp-ui`
- **云后端**：`limfinity-cloudbase-sync`
- **合规交付**：`chinese-formal-report-docx`、`docx-official`、`pptx-official`、`sop-writer` 等（完整清单见 `skill_dependencies.md`）

> ⚠️ **取舍规则**：方法签名查全局技能；**行为语义以包内实测为准**（例：`raise_message` 全局技能称
> 「无 stack trace 的友好提示」，包内 `run_script_push_sync.md` 实测**会抛异常**）。

---

## 四、补：小程序首页个性化文件路径

`miniprogram_dev_experience.md` §9「关键文件速查」未收录首页个性化的三个路径，补记于此：

- `src/pages/home/index.tsx` —— 首页（`grid-cols-2` 模块网格 + 状态徽章）
- `src/db/homeConfig.ts` —— 常用区个性化配置
- `src/pages/module-prefs/` —— 模块偏好设置页

---

## 五、归档说明

`display_description_archive.md` 与 `quick_prompts_archive.md` 于 2026-09-15 由单体专家
「limfinity-engineer」迁入本包。二者是专家包规范压缩（`displayDescription` 限中文 40–50 字、
`quickPrompts` 固定 3 条）的副产品，**内容仍有参考价值，不得删除**。

单体专家包本体已归档至 `my-experts/_archive/limfinity-engineer/`（已从 `marketplace.json` 摘除注册），
仅作历史留档，不再维护。
