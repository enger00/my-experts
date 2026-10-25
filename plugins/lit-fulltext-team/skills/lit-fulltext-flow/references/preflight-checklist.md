# 开工前交接清单（Pre-flight）

> **目的：下次开工 5 分钟内进入执行 —— 不重复推导、不重复探测、不重复踩坑。**
> 适用：任何一次「续跑 / 放量 / 换通道」任务。由主理人（`lit-fulltext-team-team-lead`）在 Phase 1 之前执行。
> ⛔ **不做这份清单就开始跑 = 大概率白跑一轮。**

## Step 0 · 读交接（~30 秒，禁止跳过）

| 读什么 | 取什么 | 位置 |
|---|---|---|
| 库状态快照 | 已下载数 / 各载体缺口 | `E:\办公文件\文献\.workbuddy\memory\REFERENCE.md` **§十四** |
| 上一次停机原因 | 真风控？熔断？跑满？ | 当日日志 `2026-MM-DD.md` **最后一条 09:xx 节** |
| 上次起手参数 | gap / shards / cool / journals | 同一节的「起手参数卡」 |

⛔ **判因只认该条 id 自己的 probe log**（`logs/probe/cnki_shot/pdfprobe_<id>_a0.log`，
含 `blocked` / `btn` / `sim` / `gate` 字段）。日志里的 `kept` 页汇总只是**浏览器残留标签页**，
据它判因会误判 —— 曾差点把知网拼图风控当成 ScienceDirect 限流。

## Step 1 · 环境自检（~60 秒）

```bash
export PATH="/c/Program Files/Git/usr/bin:/c/Program Files/Git/mingw64/bin:$PATH"   # ⛔ 否则 ls/grep 全 not found
cd "E:/TRAE/英文文章/ncu2fy_literature"

curl -s --max-time 5 http://127.0.0.1:9223/json/version                            # Chrome CDP 存活？
curl -s --max-time 5 http://127.0.0.1:9223/json/list | grep -c "wvpn.ncu.edu.cn"   # >0 ⇒ 会话页在
python tools/flow_channels.py                                                      # 通道登记表 + 资源轨分组
```

| 检查项 | 通过判据 | 不过怎么办 |
|---|---|---|
| Chrome `:9223` | 返回 `Browser: Chrome/...` | 请用户手动开（⛔ **绝不自动配开机自启**） |
| WebVPN 会话 | `/json/list` 里有 `wvpn.ncu.edu.cn` 且**非登录页** | 请用户手动登录 |
| **`:9224` 未被误开** | 无 OA 任务时 `curl :9224` 应**连不上** | 活着 ⇒ 可能是旧启动器，先关掉 |
| 资源轨分组 | VPN 轨 6 个 / 自由轨 1 个（oa） | 分组不对 ⇒ 登记表被改坏 |
| **会话真能取到出版社** | 探针**阳性对照 ≈200KB**（`_e_wvpn_probe_domains.py`） | 全体同字节数 ⇒ **假阴性，见下** |

### ⛔⛔ 会话有效性必须「**预热后再测**」（09-22 实测，差点误判）

刚重启 Chrome 后直接跑 `_e_wvpn_probe_domains.py`，会出现：
**12 个域名全部返回同一个 ~3.7KB 页面 —— 连阳性对照 Springer 也是**，脚本报 `⚠ 对照不符`。

> ⇒ **这不是会话失效。** 用浏览器自身 cookie 做一次**真实导航**即可验证：
> `page.goto("https://wvpn.ncu.edu.cn/_webvpn_*/https://link.springer.com/")`
> → `200` + `title='Home | Springer Nature Link'` + **~237KB** ⇒ 会话有效。

**正确动作**：先真实导航预热一次（打开任意一个 wvpn 包装的出版社首页），**再**跑探针 ⇒ 恢复正常。

⛔ **判据**：① 阳性对照必须 **≈200KB**；② **所有域名字节数完全相同 ⇒ 判为假阴性**。
⛔ **绝不要**据 3754B 这一批结果让用户重新登录 —— 会白折腾一轮。

## Step 2 · 配额闸门（**主动配额，防被动熔断**）

⛔ **被动熔断会留下惩罚，主动配额不会。** 续跑前先查当日已放条数：

```bash
grep -c "本片候选" logs/probe/run_cnki_shards*.log            # 当日已开片数
grep "本片结果" logs/probe/run_cnki_shards*.log | tail -5     # 累计已放条数
```

| 当日知网累计 | 动作 |
|---|---|
| < 25 条 | 可正常续跑 |
| 25–39 条 | **只跑 1 片**，`--gap 90` |
| **≥ 40 条** | **今日收手**，转其他通道或次日再来 |

## Step 3 · 起手参数卡（**直接抄，别再推导**）

**知网页（有风控，默认保守）**

```bash
bash tools/run_cnki_shards.sh --shards 2 --per-shard 25 --gap 75 --cool 1800 \
     --carriers "学术期刊" --journals ""
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--gap` | **75** | 放量默认 **75s**；`≥50s` 是**下限不是推荐值** |
| `--shards` / `--per-shard` | 2 / 25 | 单片 ≤25 条；整轮 ≤50 条（配合日配额 40 需保守） |
| `--cool` | 1800 | 片间冷却 ≥30 min |
| `--journals ""` | 空串 | ⛔ **要真放开全库必须传空串**；默认三刊只是交集 |

**万方 / 英文出版社 / OA** 见 `channel-registry.md`。

## Step 4 · 相位判断（该跑谁）

```
上次是真风控  ──→ 次日先跑「知网 1 片 × gap 90」试水；不过就全天转英文侧
上次是熔断    ──→ 先跑台账汇总再续跑（非风控，无需长冷却）
上次跑满      ──→ 直接续跑（自动跳过已归档）
无历史        ──→ 先探针 1 次，再跑 1 片试水
```

## Step 5 · ⛔ 反面清单（**这些事不要重复做**）

| 不要做 | 因为 |
|---|---|
| 重新推导 gap / shards / cool | 上面参数卡就是结论，重推＝白烧一轮对话 |
| 重新对统计口径 | 一律 `COALESCE(dup_of,0)=0` ＋ `carrier_type`，无例外 |
| 重新验 OA 能否免 VPN | 已实测：Europe PMC / PMC / Unpaywall 全文无 wvpn |
| 重新试纯 HTTP 打知网 | 三条已探明不可行（见 `REFERENCE.md §14.1`） |
| 重新试英文篇名检索 | 实测为语义翻译式宽松匹配，无法精确命中 |
| 靠「再买台机器并行」绕单账号 | 约束在**账号**不在机器数，换机照样踢 |
| 重跑已归档条目 | 续跑自动跳过；重跑只增风控风险 |
