---
name: webvpn-pdf-downloader
description: 南昌大学 WebVPN 通道批量下载付费期刊 PDF。当需要为文献数据库补全 PDF、用户提到 WebVPN/校园网权限下载、或需要复用浏览器登录态批量获取机构授权全文时使用。
agent_created: true
---

# WebVPN PDF 批量下载（南昌大学）

已验证可用的完整链路（2026-09-13 实测）。

## 架构

> 脚本随本技能自带（`scripts/cdp_proxy_shim.mjs`、`scripts/vpn_download_v3.py`）；工作数据（数据库、PDF 目录、日志）在 `E:\TRAE\英文文章\ncu2fy_literature\`。

1. **专用 Edge 窗口**（CDP 调试端口 9222，独立 profile，不影响日常浏览器）
   - 启动：`"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --user-data-dir=E:\TRAE\英文文章\ncu2fy_literature\edge-profile --remote-debugging-port=9222 --no-first-run "https://wvpn.ncu.edu.cn/auth/login"`
   - 用户手动登录 WebVPN（助手绝不碰账号密码）
2. **CDP 代理垫片** `scripts/cdp_proxy_shim.mjs`（启动：`node <本技能>/scripts/cdp_proxy_shim.mjs`）
   - 兼容 web-access CDP proxy v2.5.3 契约（/targets /info /new /navigate /eval /click /scroll /close）
   - Node ≥22 原生 WebSocket，零依赖；`SHIM_PORT=3456`，`CHROME_CDP_PORT=9222`
   - **坑**：Edge 忽略 `/json/new?url=`（返回 about:blank），必须用浏览器级 WS `Target.createTarget`
3. **下载器** `scripts/vpn_download_v3.py`（启动：`python <本技能>/scripts/vpn_download_v3.py --limit N --prefixes ...`）
   - 流程：DOI 规范化 → doi.org 直连解析落地页 → WebVPN URL 重写 → 浏览器内 fetch（1MB 分块 base64 回传）→ %PDF 头校验 → 落库 articles.pdf_path + manifest.tsv
   - `--limit N --prefixes 10.1007,10.1186,... --sleep 3`；挑战页自动停批

## WebVPN 重写规则（核心）

`scheme://host[:port]/path` → `https://scheme-host-port.wvpn.ncu.edu.cn/path`
- 例：`https://link.springer.com/article/10.1007/x` → `https://https-link-springer-com-443.wvpn.ncu.edu.cn/article/10.1007/x`
- `wvpn.ncu.edu.cn/_webvpn_*/https://host/` 路径格式同样受白名单约束，不比子域名格式更宽松
- 页面内相对链接基于重写后地址解析即可；页面上下文 fetch 带 credentials:'include' 即带 WebVPN 会话

## 白名单实测（2026-09-13）

✅ 可用：link.springer.com、*.biomedcentral.com、www.sciencedirect.com、www.tandfonline.com、pubs.acs.org、ieeexplore.ieee.org
❌ 未启用（报"网站尚未启用"）：onlinelibrary.wiley.com(Cloudflare 挑战)、www.nature.com、academic.oup.com、journals.lww.com、www.bmj.com、www.frontiersin.org、www.mdpi.com、www.dovepress.com、karger.com、spandidos
⚠️ ScienceDirect 首页正常但**文章页被 robot check** 拦截（出口 IP 222.204.4.75）；linkinghub.elsevier.com 未启用，需映射到 `www.sciencedirect.com/science/article/pii/<PII>`

## 实测成功率与局限

- Springer/BMC/ACS 文章：~94%（PDF 直链 + citation_pdf_url meta 两种发现途径均有效）
- 每篇 10–15 秒（含导航等待与限速 sleep 3s）；大批量务必 run_in_background
- 遇 Cloudflare/人机验证页立即停批等用户；不绕验证码、不碰凭证

## OA 直连通道（`scripts/oa_download_v4.py`）

覆盖前缀：10.3389 Frontiers、10.1155 Hindawi、10.21037 AME、10.18632 Aging、10.2147 Dove Press（约 930 篇，无需 VPN，requests 直连，落地页 citation_pdf_url/.pdf 链接 + Frontiers `/full→/pdf`、AME `/html→/pdf` 规则）。
用法：`python scripts/oa_download_v4.py --limit N --sleep 2`；台账 `oa_download_manifest.tsv`。

## 运行前检查清单

1. Edge 专用窗口存活：`curl http://127.0.0.1:9222/json/version`
2. 垫片存活：`curl http://127.0.0.1:3456/targets`
3. 用户已登录 WebVPN（/targets 里应见 wvpn.ncu.edu.cn/site-nav/home）
4. 库文件 `E:\TRAE\英文文章\ncu2fy_literature\ncu2fy.db`（busy_timeout=60000，勿全局重建）

## 相关数据事实

- 库内 NO_PDF 记录用 `pdf_path='NO_PDF'` 标记（非 NULL）；doi 字段 7,877 条是 URL 格式需规范化提取
- 缺口 8,446 条有 DOI；WebVPN 白名单现覆盖 ~1,202 篇（10.1007/10.1186/10.1080/10.1021）
- OA 大户（Frontiers/Hindawi/AME/Aging ~750 篇）无需 VPN 可直抓，属另一条免费通道
