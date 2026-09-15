# quickPrompts 原文归档（15 条）

> 规范要求固定 3 条，其余 12 条于 2026-09-07 归档，仍可作为典型任务参考。

1. **zh**：帮我把 WPS 多维表对接到 Limfinity 来访人员登记表
   **en**：Sync a WPS dbsheet into the Limfinity visitor registry

2. **zh**：门禁刷脸记录怎么通过 run_script 实时推送到 Limfinity？
   **en**：Push face-access records into Limfinity in realtime via run_script

3. **zh**：怎么把 Limfinity 主数据同步到微信云开发并设置账号密码登录？
   **en**：Sync Limfinity master data into WeChat CloudBase and set up account/password login

4. **zh**：改完代码帮我构建小程序并生成真机预览二维码
   **en**：Build the miniprogram and generate a real-device preview QR code for me

5. **zh**：怎么把内网 Limfinity 经 N1 隧道同步到微信小程序 CloudBase？
   **en**：Deploy the N1 frp tunnel and sync Limfinity to the miniprogram CloudBase

6. **zh**：怎么把 Limfinity 字段定义/主数据同步到 .56 本地 Supabase（方案C 单库）？
   **en**：Sync Limfinity schema/master data into the local Supabase on .56 (Plan C)

7. **zh**：小程序真机读不到 .56 的 Supabase 主数据，怎么排查并打通 frp 反向隧道？
   **en**：The miniprogram cannot read .56 Supabase master data on a real device - diagnose and set up the frp reverse tunnel

8. **zh**：同步过来的数据只有内置字段，怎么把 Limfinity 自定义字段同步进 Supabase？
   **en**：Synced data only has built-in fields - how do I sync Limfinity custom fields (Property) into Supabase?

9. **zh**：.56 自托管 Supabase 排障：Studio 改密码、Envoy api-gw、compose 只用 service 名、Basic Auth 缓存
   **en**：Self-hosted Supabase on .56: Studio password change, Envoy api-gw, docker compose service names, Basic Auth cache

10. **zh**：怎么用 nssm 把 Node 轮询器 / frpc 隧道注册成 Windows 服务（开机自启、崩溃自愈），避开 PowerShell 静默坑？
   **en**：Register a Node poller / frpc tunnel as a Windows service with nssm (auto-start, crash self-heal), avoiding the PowerShell 2>$null NativeCommandError trap

11. **zh**：怎么把 Limfinity 的 21 个文件字段（设备验收报告/照片、人员岗位说明书）存进 Supabase Storage？
   **en**：Store Limfinity file attachments (21 file fields) into Supabase Storage via a decoupled upload worker

12. **zh**：Taro 构建后某个分包在 dist 里整目录消失、但 build 零报错，怎么排查修复？
   **en**：A Taro subpackage silently missing from dist with zero build errors - diagnose and fix

13. **zh**：一份 Limfinity 脚本怎么同时给定时任务和 run_script API 用？脚本为什么必须做成「自证型」？
   **en**：One Limfinity script for both a scheduled task and the run_script API - dual-entry setup and self-diagnosing script design

14. **zh**：Taro 构建被 safe-delete 守卫拦截/卡死，dist 应该怎么清才对？
   **en**：Taro build fails or hangs because of the safe-delete guard - how do I clean dist correctly?

15. **zh**：Limfinity 脚本怎么写：Helper 与 ScheduledScript 入口、顶层作用域规则、为什么「立即运行」不是 cron？
   **en**：How do I write a Limfinity script - Helper vs ScheduledScript, top-level scope rules, immediate-run is not cron

