# N1 公网隧道（独立 frp + 阿里云 Caddy）+ 微信云函数同步 Limfinity → CloudBase

> **来源**：2026-08-29 实战闭环。把内网 Limfinity（10.103.200.46:80）`/api` 经「独立新建 frp 实例 + 阿里云 Caddy 反代 + 已备案域名」公网合规暴露，再由微信云函数 `limfinityProxy` 把字段定义/主数据同步到 CloudBase（`module_schema` / `master_data`）。
> **结果**：全链路打通，云端测试 `limfinityProxy` 返回 `{"ok":true,"written":43,"use_helper":true}`（43 = Limfinity 全量 subject_types，与 `/api` 实测一致）。
> **用法**：凡涉及「把内网 Limfinity 经公网合规暴露并同步到小程序 CloudBase」直接读本文件，不要再重复踩 frp/Caddy/云函数的坑。

---

## 1. 目标与架构决策

- **目标**：小程序侧用 CloudBase 承载 Limfinity 字段定义（`module_schema`）与主数据（`master_data`）。Limfinity 在**内网**，需经隧道公网可达。
- **链路拓扑**：
  ```
  本机 frpc ──TLS──> 阿里云 frps:7000 ──> 阿里云 127.0.0.1:8088
        └─> Caddy(limfinity.nc2h-bio.cn:443) ──> 内网 Limfinity 10.103.200.46:80
  ```
- **双层认证**：① Caddy BasicAuth（用户名固定 `sync`）作**网关闸**；② Limfinity 自身用**表单** `username/password` 走 `gen_token` 取 token（应用层鉴权）。二者分离、互不冲突。
- **决策（易云拍板）**：**独立新建 `frpc_limfinity.toml`**，只指阿里云 frps、只代理 `limfinity-api`，**完全不动现有闲鱼 `frpc1.toml`**（避免影响 supabase 既有链路）。宿主可选本机或 `.55`（双通实测均可，本机随手改更便）。
- **合规**：域名 `limfinity.nc2h-bio.cn` 已备案（赣ICP备2026020362号），摆脱闲鱼明文 `49002`。

---

## 2. 阿里云 frps 部署（服务端）

- ⚠️ **下载用合集包名**：`frp_0.65.0_linux_amd64.tar.gz`（内含 frps+frpc 两个二进制）。**绝不加 `frps_` 前缀**（官方不发布单二进制包，加前缀 404）。
- 解压取 `frps` 装到 `/usr/local/bin`，`frps --version` 校验。
- ⚠️ **自签证书必须单行 + 带 SAN**（SSH 粘贴多行 `\` 续行会失效，报 `-keyout: command not found`）：
  ```bash
  openssl req -x509 -newkey rsa:4096 -nodes -keyout /etc/frp/frps.key -out /etc/frp/frps.crt -days 3650 -subj "/CN=frps.nc2h-bio.cn" -addext "subjectAltName=DNS:frps.nc2h-bio.cn,IP:47.122.105.172"
  ```
  frp 0.65 用的新版 Go crypto/x509 **强制 SAN**，CN-only 直接拒（`certificate relies on legacy Common Name field, use SANs instead`）。
- `frps.toml`：`bindPort=7000` + `auth.token=<自定>` + `transport.tls.force=true` + cert/key 路径。systemd 单元 `frps.service` + `enable --now` → `ss -ltnp|grep 7000` 确认 LISTEN。
- ⚠️ **阿里云安全组控制台入站放行 7000/tcp（必做，命令行改不了）**。
- 把 `/etc/frp/frps.crt` 经 `scp` 拉到本机 frpc 目录。

---

## 3. 本机 frpc（客户端）

```toml
serverAddr = "frps.nc2h-bio.cn"        # 用域名，TLS 主机名校验才过
serverPort = 7000
auth.token = "<与 frps 一致>"
transport.tls.enable = true
transport.tls.trustedCaFile = "frps.crt"
[[proxies]]
name = "limfinity-api"
type = "tcp"
localIP = "10.103.200.46"
localPort = 80
remotePort = 8088
```
- ⚠️ **Windows `hosts` 加** `47.122.105.172 frps.nc2h-bio.cn`（管理员），`serverAddr` 用域名 → 解决 TLS 主机名校验（证书 SAN 含 `DNS:frps.nc2h-bio.cn`）。若用 IP 连会 `session shutdown`（TCP 通但 TLS 主机名不符）。
- ⚠️ **绝不用 `start "frpc-limfinity" frpc.exe`**：PowerShell 的 `start` 启动带连字符/长参数进程会触发 Windows 凭据弹窗（把 `.toml` 误当目标用户名）。直接前台跑 `D:\frp_0.65.0_windows_amd64\frpc.exe -c D:\frp_0.65.0_windows_amd64\frpc_limfinity.toml`，日志完整可见。
- 成功标志：`login to server success` + `[limfinity-api] start proxy success`；frps 端 `journalctl -u frps -n 30` 看 `[limfinity-api] tcp proxy listen port [8088]`。

---

## 4. 阿里云 Caddy 站点（反代 + 鉴权）

- 追加（**幂等**：先 awk 剥离所有 limfinity 块再 append，避免重复报 `ambiguous site definition`）：
  ```
  limfinity.nc2h-bio.cn {
      encode gzip
      basicauth {
          sync <bcrypt 哈希>
      }
      reverse_proxy 127.0.0.1:8088
  }
  ```
- ⚠️ **BasicAuth 哈希必须非交互生成**：`caddy hash-password --plaintext "$PASS"`。裸 `caddy hash-password "$PASS"` 在新版会**改成交互式 `Enter password:`**，捕获的密码与 echo 明文错位 → 401。明文与哈希**必须同一次生成且 `curl -u` 实测 200** 才可信。
- 阿里云已是 Let's Encrypt 环境（supabase 站占 80 端口复用 ACME），`caddy reload` 后自动签发证书。
- ⚠️ **Caddyfile `ambiguous site definition` 坑**：重复站点块（手动加过 + `tee -a` 又叠）会报 ambiguous。先 `grep -n 'limfinity.nc2h-bio.cn' /etc/caddy/Caddyfile` 确认无重复，awk 剥离后 append 唯一块。

---

## 5. DNS A 记录

- 阿里云 DNS 控制台加 `limfinity` A → `47.122.105.172`（启用）。`nslookup limfinity.nc2h-bio.cn` 解析到该 IP 即生效（沙箱 + 本机双验证）。

---

## 6. 微信云函数 `limfinityProxy`（同步执行体）

- `cloudfunctions/limfinityProxy/index.js` 逻辑：`gen_token`（表单 `api_wx/yy@123456`）→ `run_script(mini_sync_schema, {include_master:true})`（轨道 B helper）→ 写 `module_schema` / `master_data`。
- **env 默认值已固化进代码**（与既有 `yy@123456` 兜底风格一致）：`LF_URL=https://limfinity.nc2h-bio.cn/api`、`LF_USER=api_wx`、`LF_PASS=yy@123456`、`LF_SCRIPT=mini_sync_schema`、`LF_BASIC_AUTH=qS3OZl6vGrNC62K75dpGIJ`、`USE_HELPER=true`。
- `basicAuthHeader()` 自动拼 `sync:<密码>` → 故 Caddy basicauth 用户名固定 `sync`，`LF_BASIC_AUTH` 只填**纯密码**（函数内部拼前缀）。
- **双层鉴权不冲突**：Limfinity 对 API 方法用**表单凭据**（`method=gen_token`），忽略 `sync` basicauth 头；只有裸 GET 才报 `User sync is not found`（应用层，预期）。函数走带 method 的 POST，正常。
- ⚠️ **坑① wx-server-sdk `set` 必须 `{data}` 包裹**：
  ```js
  // ✅ 正确
  await db.collection('module_schema').doc(String(t.id)).set({ data: { source_name: t.name, ... } })
  // ❌ 错误（报 parameter.data should be object instead of undefined）
  await db.collection('module_schema').doc(String(t.id)).set({ _id: ..., source_name: ... })
  ```
  `update` 同理 `{ data: {...} }`，与前端 `cUpdate` 的 `update({ data: patch })` 一致。**绝不可直接 `set({...})` 或 `set({_id,...})`**。
- ⚠️ **坑② 超时 3s 太短**：微信云函数默认 `timeout=3s`，本同步需 2 次跨公网隧道 HTTPS + 冷启动 + 写库循环，3s 必超时（`Invoking task timed out after 3 seconds` / statusCode 433）。**修复**：
  ① 控制台「云函数 → limfinityProxy → 版本与配置」手动把超时改 **60s**（**最稳**）；
  ② 本目录 `config.json` 加 `{"timeout":60,"memorySize":256}` 重新部署**可能不生效**（当前工具/项目版本不读该字段），兜底永远控制台手动改。
  改完云端测试运行时间 ~3.5s，返回 `{ok:true,written:43}`。
- ⚠️ **`SOURCE_NAME_TO_MINI` 映射不全**：目前只配 人员/设备/科室 三类有 `mini_type`；其余 40 类型 `mini_type=null` 且 `master_data` 不写（代码 `if (t.master && mini)` 双条件）。补全跑 `scripts/check_schema_drift.py` 拿全 43 类型中文名再映射。

---

## 7. 联调验证清单

- **Caddy 鉴权配平**：`curl -sI -u 'sync:<明文>' https://limfinity.nc2h-bio.cn/api`
  - `200` → 鉴权配平 + 隧道通（响应体 `User sync is not found` 是 Limfinity 应用层，预期，因裸 GET 没带 Limfinity 登录）
  - `401` → 哈希/明文不配对，重 `caddy hash-password --plaintext` 并 curl 实测
  - `502` → 鉴权通但隧道断，回本机确认 `frpc.exe -c frpc_limfinity.toml` 前台进程在
- **云函数同步**：云端测试 `limfinityProxy`（参数留空）→ `{"ok":true,"written":43,"use_helper":true}`；云库 `module_schema` 43 条。
- **错误码速查**：`errorCode:-1 / statusCode 430`（set 写法）、`433`（超时）、`FUNCTION_NOT_FOUND`（未部署/未装依赖，须「上传并部署：云端安装依赖」）。

---

## 8. 铁律速查（十条，每条都实测踩过）

1. frp 下载用合集包名 `frp_0.65.0_linux_amd64.tar.gz`，加 `frps_` 前缀 404。
2. 自签证书必须带 SAN（`-addext "subjectAltName=DNS:...,IP:..."`），frp 0.65 拒 CN-only；SSH 粘贴多行 `\` 续行失效，务必单行。
3. frpc `serverAddr` 用域名 + Windows hosts 绑 IP，否则 TLS 主机名校验失败 `session shutdown`。
4. PowerShell 不用 `start "名字" frpc.exe`，触发 Windows 凭据弹窗；直接前台跑。
5. Caddy basicauth 哈希必须 `caddy hash-password --plaintext "$PASS"` 非交互生成；明文与哈希同源同次 + curl 实测 200 才可信。
6. Caddyfile 站点块勿重复（手动加 + `tee -a` 易叠成两份报 `ambiguous site definition`）；awk 剥离后 append 唯一块。
7. 云函数 `set`/`update` 必须 `{ data: {...} }` 包裹，绝不可 `set({_id,...})`。
8. 云函数默认超时 3s 必超时，控制台「版本与配置」手动改 60s 最稳；`config.json` 的 `timeout` 字段当前不生效，不依赖。
9. 双层鉴权互不冲突：Caddy 闸 `sync:<密码>`、Limfinity 表单 `api_wx/yy@123456`；裸 GET 报 `User sync is not found` 是应用层预期。
10. `SOURCE_NAME_TO_MINI` 映射不全（仅人员/设备/科室），其余 40 类型 `mini_type=null`；补全跑 `scripts/check_schema_drift.py`。
