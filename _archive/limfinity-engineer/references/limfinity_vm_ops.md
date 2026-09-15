# Limfinity 虚拟机基础设施运维（VM Ops）实战知识库

> **来源**：2026-08-17~18 易云老师的 Limfinity 测试机（Lim631）运维实战——Ubuntu 22.04 → 24.04.4 LTS 升级收尾、静态 IP 配置、Limfinity VM Console 调出与分辨率匹配、系统清理瘦身、logrotate 修复、升级后全面体检。
> **适用对象**：跑 Limfinity（RURO LIMS）的 Ubuntu 虚拟机（测试机/正式机），含 Rails 4.2 + puma + PostgreSQL + nginx + redis 栈。
> **用法**：凡涉及「系统升级、改 IP、调出/修虚拟机控制台、清垃圾、配日志轮转、升级后体检」直接读本文件，勿重复踩坑。

---

## 0. 远程操作通道（WorkBuddy 无原生 SSH 终端）

本机（Windows）用 Python 3.13.12 的 `paramiko` 连 VM：

- 测试机 `10.103.200.58`，正式机 `10.103.200.56`；账号 `root`，密码 `eq86l1o4`（测试机）。
- VM 内**没有 `curl`**（PATH 差异），HTTP 自检一律用 python：
  ```python
  python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/signin',timeout=10).status)"
  ```
- **避免多层转义**：要往 VM 写 SQL / 脚本时，用 SFTP 上传文件再执行，别在 Python 字符串里塞 `\p \d U&'\FF1A'`（会触发 SyntaxWarning / 转义错）。
- **中文文件名坑**：SFTP 上传前先 `shutil.copy` 到 ASCII 临时名（如 `/tmp/fix.sql`），再 `putfo`，规避编码问题。
- 写 systemd override / grub 等含 `%I` 的文件时，**务必单百分号 `%I`**；从 Python 字符串生成时若写成 `%%I`，systemd 不会展开 → agetty 去找 `/dev/%I` 报错。

---

## 1. 升级后全面体检清单（必做）

升级（尤其跨大版本 systemd 化）后逐项核对，任一项异常都先查再动：

| 检查项 | 命令 | 正常表现 |
|---|---|---|
| 系统版本 | `lsb_release -a` / `uname -a` | Noble 24.04.4，内核 6.8.x |
| 业务服务 | `for s in thin postgresql nginx redis-server; do systemctl is-active $s; done` | 全 `active` |
| 失败服务 | `systemctl --failed --no-legend` | 应为 0（RFID 设计性失败见 §6） |
| PG 集群 | `pg_lsclusters` | 仅业务库在线（如 14 @5432） |
| 业务库表数 | `sudo -u postgres psql -p 5432 -d limfinity -tA -c "select count(*) from information_schema.tables where table_schema='public'"` | 90（贵院实例） |
| Console 自启 | `ps aux \| grep syscon.rb \| grep -v grep` | 有进程（tty1 自动登录后启动） |
| HTTP | 见 §0 urllib 片段 | `8080/signin` 与 `80/` 均 200 |
| 磁盘 | `df -h / /data` | `/` 一般 <15% |

⚠️ **库名 vs 角色名**：业务库名是 **`limfinity`**，`limsowner` 是连库**角色（用户）**。写 `psql -d limsowner` 会报 "does not exist"——这是命令写错，不是库丢了。正确：`psql -d limfinity -U limsowner`。

---

## 2. 静态 IP / 网络配置（netplan，Ubuntu 24.04）

文件 `/etc/netplan/01-netcfg.yaml`（renderer 用 `networkd`）：

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 10.103.200.58/24
      routes:
        - to: default
          via: 10.103.200.254
      nameservers:
        addresses: [8.8.8.8, 114.114.114.114]
```

- 改完 `netplan apply` 生效（远程改 IP 有断连风险，先 `ping`/`arp` 确认目标 IP 没被占用！）。
- ⚠️ **24.04 权限告警**：netplan 文件权限须 `chmod 600`，否则 `netplan apply` 报 "permissions are too open" 安全告警。
- 静态 IP 改完，**VM Console 欢迎屏上写的访问 URL 仍是安装时写死的旧 IP**（如 `10.103.200.46`），不会自动更新——以实际新 IP 访问为准。

---

## 3. Limfinity VM Console 调出与分辨率匹配

### 3.1 调出 Console（核心坑：upstart → systemd 失效）

Console 是 VM 开机时 tty1 自动登录 `sysadmin` 后跑的 TUI：

```
tty1 自动登录 sysadmin
  → /home/sysadmin/run.sh (shell)
    → cd Limfinity && syscon/syscon.rb   ← 蓝灰色 Console 界面
```

- **老系统（upstart）**：`/etc/init/tty1.conf` 里 `exec /sbin/mingetty --autologin sysadmin tty1` 让它自动登录。
- **升级到 systemd 后该配置被完全忽略**，tty1 只跑标准 agetty → 显示黑底 `limfinity login: _`，Console 不出现。
- **修复（systemd drop-in）**，建 `/etc/systemd/system/getty@tty1.service.d/autologin.conf`：
  ```
  [Service]
  ExecStart=
  ExecStart=/sbin/agetty --autologin sysadmin --noclear %I $TERM
  ```
  然后 `systemctl daemon-reload && systemctl restart getty@tty1`。
- ⚠️ **`%I` 必须单百分号**（systemd 展开成 `tty1`）。写成 `%%I` → agetty 找 `/dev/%I` 报 `cannot open as standard input`。
- 验证：`journalctl -u getty@tty1` 见 `session opened for user sysadmin` + `run.sh`/`syscon.rb` 进程起来。

### 3.2 分辨率匹配正式机

Console 是固定大小文本 TUI（约 80×25 字符），想让它撑满 VMware 窗口、蓝边最小，要降帧缓冲分辨率（不是升）：

- 升级默认 `1280x800` 会显太大、蓝边多；正式机更密说明它跑在更低分辨率。
- **vmwgfx 驱动无视 `GRUB_GFXPAYLOAD_LINUX`**，只认内核 `video=` 参数。有效做法——编辑 `/etc/default/grub`：
  ```
  GRUB_GFXMODE=800x600
  GRUB_GFXPAYLOAD_LINUX=800x600
  GRUB_CMDLINE_LINUX_DEFAULT="quiet video=800x600"
  ```
  （`video=800x600` 是关键；`GRUB_GFXMODE` 只影响 GRUB 菜单本身）
- `update-grub` 后 `reboot`。重启后 `cat /sys/class/graphics/fb0/virtual_size` 应为 `800,600`。
- ⚠️ `echo 800x600 > /sys/class/drm/card0-Virtual-1/mode`（DRM 接口）需 DRM master 权限，SSH 下 root 也不够，不推荐；直接用 `video=` 内核参数最稳。
- 档位：VMware 虚拟显卡支持 640x480 / 800x600 / 1024x768 / 1280x1024 / 1920x1080 等，改一行重启即生效。

---

## 4. 系统清理瘦身（零风险优先）

磁盘轻松时（如 `/` 才 13%）也要定期减负担。按风险分级：

**零风险（直接做）**：
```bash
apt-get clean                     # 清 .deb 下载缓存（archives）
apt-get autoclean                 # 清过期缓存
journalctl --vacuum-size=50M      # systemd 日志裁剪（省 ~110M）
rm -rf /var/log/installer         # 安装残留（老系统年久）
rm -f /var/log/*.[0-9].gz /var/log/*.[0-9]   # 旧轮转日志
rm -rf /tmp/systemd-private-*     # 陈旧私有 tmp
```

**低风险（旧内核，标准操作）**：
```bash
# 先确认当前跑的版本：uname -a （如 6.8.0-138）
apt-get remove --purge linux-image-5.15.0-187 linux-headers-5.15.0-187-generic
update-grub                      # 重生成，确认 grub.cfg 里无旧条目
```
仅留一个在跑内核，启动无碍。

**需确认（数据库集群残留）**：
```bash
pg_lsclusters                   # 确认业务在 14（5432），16（5433）是空壳
pg_dropcluster 16 main          # 删升级残留空集群（业务在 14，无影响）
```
⚠️ 删前必须 `pg_lsclusters` 确认 5433 无业务数据；删后 `ss -ltn | grep 5433` 应无监听。

**明确保留（不是垃圾，勿动）**：
- `/data/lims_data/attachments`（样本附件业务数据）
- Ruby gems 目录（`/usr/local/lib/ruby/gems`，limfinity 运行依赖）
- limfinity 业务日志（52M）——**用 logrotate 轮转而非删**，见 §5

实测效果：上述清理后 `/` 从 6.0G → 5.1G（省 ~900M），业务零影响。

---

## 5. logrotate 修复（真实踩坑）

### 5.1 症状

limfinity 日志（`/data/lims_data/log/production.log` 等）持续上涨、从不压缩——旧配置 `/etc/logrotate.d/lims`（2016）有两个硬伤：

1. **路径过时**：指向升级前的 `/home/sysadmin/Limfinity/log/*`，实际日志在 `/data/lims_data/log`（软链 `/soft/Limfinity/log`）。
2. **缺 `su` + 目录 775（组可写）**：logrotate 判定 "insecure permissions" 把**所有文件跳过** → 轮转从来没跑过。

### 5.2 修复配置（已备份旧版为 `lims.bak.日期`）

```
/data/lims_data/log/*.log {
    su sysadmin sysadmin
    weekly
    rotate 12
    compress
    delaycompress
    dateext
    copytruncate
    missingok
    notifempty
}
/data/lims_data/log/puma*.log /data/lims_data/log/thin*.log /data/lims_data/log/rfid*.log {
    su sysadmin sysadmin
    monthly
    rotate 6
    compress
    dateext
    copytruncate
    missingok
    notifempty
}
```

- `su sysadmin sysadmin`：以日志属主身份轮转，绕过 775 权限检查（关键）。
- `copytruncate`：轮转后**截断原文件**、puma 无需重启即可继续写（关键，避免断业务）。
- `delaycompress`：本轮轮出的副本延后一轮再压缩（所以刚轮出的 `*-20260818` 暂未压，下轮自动压，属预期）。

### 5.3 验证

```bash
logrotate -d /etc/logrotate.d/lims     # dry-run，确认不再报 insecure
logrotate -fv /etc/logrotate.d/lims    # 强制跑一次
ls -lh /data/lims_data/log/            # production.log 归零、出 .gz 归档
ps aux | grep -E "puma|syscon"          # 进程仍在，应用没断
```
实测：日志目录 52M → 11M，puma 4 进程照常。后续由系统每日 cron 自动轮转。

---

## 6. 升级后常见"假故障"（设计行为，勿误修）

- **`ruro-rfid-controller.service` failed**：RFID 未启用时 init 脚本在标记文件 `/data/lims_data/config_data/start_rfid_controller` 不存在即 `exit 1`，属**设计行为**。测试机不接 RFID，无害。想静音可加 `ConditionPathExists=` 让无标记时跳过而非失败。`systemctl reset-failed` 只是清状态，重启会再现。
- **`before_login_script` 全角冒号 bug**：`subjtask_scripts` 表 id=4 脚本用了全角冒号 `：`(U+FF1A) 而非 `:`，每次访问 /signin 报 `undefined local variable or method '：login_extra_text'`。修复（数据库级，非文件）：
  ```sql
  UPDATE subjtask_scripts SET code = replace(code, U&'\FF1A', ':'), updated_at = now() WHERE id = 4;
  ```
  备份原值到 `/tmp/before_login_script_backup.txt`，重启 puma 后报错归零、登录页 "This is a test instance" 文本正常显示。此为升级前既有笔误。
- **RMagick 链接**：Ubuntu 24.04 升级后 ImageMagick 库从 `libMagickCore-6.Q16.so.6` 变 `so.7`，须重链 `libMagickCore-6.Q16.so.7`，否则图像相关功能报错。
- **`pam_lastlog.so: cannot open shared object file`**：Console 自动登录时的 PAM 警告，不影响功能（仅少"上次登录时间"显示），装 `libpam-modules` 可消，不急。

---

## 7. 关键文件/路径速查

| 项 | 路径 |
|---|---|
| netplan 静态 IP | `/etc/netplan/01-netcfg.yaml`（权限 600） |
| tty1 自动登录 drop-in | `/etc/systemd/system/getty@tty1.service.d/autologin.conf` |
| sysadmin 启动脚本 | `/home/sysadmin/run.sh` → `Limfinity/syscon/syscon.rb` |
| GRUB 分辨率/视频参数 | `/etc/default/grub`（`GRUB_GFXMODE` / `GRUB_CMDLINE_LINUX_DEFAULT="...video=800x600"`） |
| limfinity 日志目录 | `/data/lims_data/log/`（真实）；软链 `/soft/Limfinity/log` |
| logrotate 配置 | `/etc/logrotate.d/lims`（旧版备份 `lims.bak.日期`） |
| 业务库 | PostgreSQL 14 @5432，库名 `limfinity`，角色 `limsowner` |
| 登录前脚本 bug | `subjtask_scripts` 表 id=4 |
| RFID 启用标记 | `/data/lims_data/config_data/start_rfid_controller`（不存在=不启用） |

---

## 8. 标准收尾顺序（推荐）

1. 升级/改 IP/重启后先跑 §1 体检清单。
2. 要 Console 自动出现 → §3.1；要大小匹配正式机 → §3.2（一次到位，改一行重启）。
3. 清理 → §4（零风险先做，DB 残留确认后再删）。
4. 日志轮转 → §5（修旧配置 + 验证，避免涨回去）。
5. 区分 §6 设计性"假故障"，不误修。
6. 全程用 paramiko 远程（§0），改完 reboot 验证持久化（静态 IP/自启/RMagick/分辨率都是文件级，重启必验）。
