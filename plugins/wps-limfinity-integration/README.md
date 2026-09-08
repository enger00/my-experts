# WPS-Limfinity 对接专家

把 WPS 多维表、腾讯文档智能表等外部业务数据，增量同步进 Limfinity（RURO LIMS）的实战型对接专家。覆盖 WPS 用户级 OAuth + KSO-1 签名取数、Limfinity 内部 Ruby DSL 落库、字段映射与增量同步，并内置一份完整可运行参考代码。

## 类型

Agent 型（单个 AI 专家）

## 功能

- **WPS 多维表对接**：用户级 OAuth 授权码、KSO-1 签名、refresh_token 持久化、活动性 file_id/sheet_id、自动发现数据子表。
- **Limfinity 落库**：create_subject / find_subjects / set_value 正确写法，按业务唯一键增量同步（新增/更新/跳过）。
- **腾讯文档智能表（smartsheet）接入**：底层即 `smartbook/v2`，含消费者账号鉴权限制与企业应用自建表 / HiFlow 桥接替代方案。
- **可复用架构**：通用方法放入 limfinity Helper 脚本，主脚本 `require_script '脚本名'` 调用。

## 使用示例

- 帮我把 WPS 多维表对接到 Limfinity 来访人员登记表
- WPS 多维表 OAuth 授权码和 KSO-1 签名怎么配置？
- 腾讯文档智能表(smartsheet)怎么同步到 Limfinity？

## 目录结构

```
wps-limfinity-integration/
├── .codebuddy-plugin/plugin.json   # 专家元数据与展示字段
├── agents/wps-limfinity-integration.md  # 角色定义 / 核心能力 / 工作流程 / DSL 铁律
├── references/wps_limfinity_sync.rb     # 完整可运行参考代码（单文件，json/db 双模式）
├── avatars/expert.png
└── README.md
```

## 安全说明

`references/wps_limfinity_sync.rb` 中的 `WPS_APP_KEY` 已脱敏为占位符 `<WPS_APP_KEY>`；真实密钥保留在原项目文件 `E:\办公文件\信息化系统\limfinity\wps_limfinity_sync.rb`。**分享本专家包给他人前，请勿回填明文密钥。**

## 头像

头像已自动生成在 `avatars/` 目录下。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 安装

将专家包目录放到专家目录下：

```
C:\Users\Dell\.workbuddy\plugins\marketplaces\my-experts\plugins/wps-limfinity-integration/
```

然后运行注册命令使其可见：

```bash
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
python3 scripts/package_expert.py <expert-dir> <output-dir>
```
