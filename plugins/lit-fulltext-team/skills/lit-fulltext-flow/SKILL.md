---
name: 文献全文获取流程
description: |
  面向 `ncu2fy_literature` 工程的中英文文献全文获取总流程：从缺口池盘点、题录清洗、来源路由，到按通道（万方/知网/中华医学期刊/英文出版社/OA）分片下载与四分类结算。内含单会话串行闸门、垫片端口陷阱、去重统计闸门、分片模板与不可得台账治理。
  **以下情况请主动触发本技能**：用户说"把这批文献的 PDF 下载下来"、"按来源分派到万方/知网/PMC"、"盘点缺口池给我下载计划"、"检查各通道成功率"、"续跑知网/万方分片"、"接着上次继续跑"、"开工前先过一遍交接清单"、"结算一下这轮真实净增多少"、"放开到全库"——即使用户没说技能名，只要意图是**批量获取文献全文并按来源分通道执行**，就用本技能。
  不适用于：单篇文献的检索与阅读、参考文献格式整理（用 `bib-formatter`）、纯元数据补全而不涉及全文下载。
agent_created: true
---

# 文献全文获取流程

一句话：**先判来源，再走通道；一次只开一个浏览器会话；报数只认库内数字变化。**

## 适用范围

| 项 | 值 |
|---|---|
| 工程根 | `E:\TRAE\英文文章\ncu2fy_literature` |
| 中文库 | `cn.db`（⚠ 工程根；`tools/cn.db` 是 **0 字节空壳**，用它会得到 0 条） |
| 英文库 | `ncu2fy.db` |
| 解释器 | 解析/Flask 类脚本用 `envs/default/Scripts/python.exe`；纯 SQLite 用系统 python 亦可 |
| 通道登记表 | `tools/flow_channels.py`（**唯一出处**，新增通道改这里） |

## ⛔ 五条硬约束（违反必出事故）

| # | 约束 | 后果 |
|---|---|---|
| 1 | **Chrome CDP `:9223` 唯一实例；WebVPN 单会话** ⇒ 所有浏览器通道**必须串行** | Edge 登 WebVPN 会**踢掉** Chrome 会话，两条通道同时跑＝互相踢 |
| 2 | **垫片端口**：`wf_pdf_batch.py` 默认 `WF_SHIM=3456`（→ Edge `:9222` 旧垫片），本工程实际用 **3457**（→ Chrome `:9223`） | 漏设＝白跑一整天，且日志看着像"全部失败" |
| 3 | **统计必带去重闸门** `COALESCE(dup_of,0)=0` | 漏掉则缺口虚高、增量虚高（实测曾虚高 140） |
| 4 | **先备份 → 再回填 → 后结算**，顺序不可颠倒 | 回填出错无法回滚 |
| 5 | **写库脚本禁用 `head` 截断管道** | SIGPIPE 杀死 Python，写库段静默不执行；**只认库内数字变化** |
| 6 | **知网日累计 ≥40 条即收手**（主动配额） | 被动熔断会留风控惩罚、次日首条就撞墙；主动停不留 |

## 四阶段主流程

```
Phase 1 发现      → 月度增量/缺口池盘点，统一口径快照
Phase 2 清洗+路由  → 题名清洗 → 按来源判定通道 → 切分派单
Phase 3 分片下载   → 逐通道串行，分片 + 节流 + 熔断
Phase 4 结算       → 四分类对账 + 账实相符核验 + 台账更新
```

### Phase 1 — 发现与口径
```bash
python tools/_cn_gap_snapshot.py     # 缺口池快照（后续探针读本地快照，必须先刷新）
python tools/_cn_gap_layers.py       # 分层：真缺口 vs 结构性难例
python tools/_cn_gap_sources.py      # 按来源通道拆分
```
> 缺口口径三层排序：① 中文题名优先 ② 学术期刊优先 ③ 同档 id 升序。
> ⛔ "顺序取数的前 N 条"**不是随机样本**，别用它估成功率。

### Phase 2 — 清洗与路由
清洗唯一实现：`tools/_cn_title_norm.py`（`CLEAN_VERSION=2`，自带 8 例断言自检）。
路由判据详见 `references/routing-and-cleanup.md`；一句话版本：

| 线索 | 路由 |
|---|---|
| `source='cnki_export'` / 落地页含 `cnki.com.cn`·`kns.cnki.net` | 知网通道 |
| `wf_rid` 非空 / 落地页含 `wanfangdata` | 万方通道 |
| 刊名属中华医学会系列 / 域名 `yiigle.com` | 中华医学期刊通道 |
| 英文库迁入 / 题名无汉字 / DOI 前缀 `10.1007`·`10.1109`·`10.1016` | 英文出版社通道 |
| DOI 为 OA 刊 / PMID·PMCID 齐全 | OA 通道 |
| **无任何来源线索** | **题名搜索通道**（占 63%，是最大一块） |

### Phase 3 — 分片下载
> ⛔ **开跑前必须先过 `references/preflight-checklist.md`**（读交接 → 环境自检 → 配额闸门 → **抄参数卡**）。
> 这一步就是「不做无用功」：上次推导过、探测过、踩过的，直接抄结论。

统一模板 `tools/run_sd_chunk.sh`（8 步闭环：自检→下载→台账→PyMuPDF 核验→备份→回填→结算→备份滚动）。
知网分片总控 `tools/run_cnki_shards.sh`。

**为什么必须分片**：曾有一次 110 分钟长跑在第 89 分钟被宿主回收，**回填未执行** ⇒ 分片长度必须控制在"单次工具调用内可跑完"。

### Phase 4 — 结算
```bash
python tools/_audit_now.py                          # 四分类，A+B+C+D 必须平到总数
python tools/_cnki_pdf_qc.py                        # PDF 实体抽检
python tools/_cnki_unavailable_ledger.py --show 15  # 不可得台账
```
结算口径与 SQL 详见 `references/settlement.md`。

## 通道一览（资源轨判据与完整命令见 `references/channel-registry.md`）

| 通道 | 资源轨 | 载体 | 节奏要点 | 状态 |
|---|---|---|---|---|
| 万方 | VPN 轨 | 中文 | `--gap-min 12s`；<30s 触发 `0x05189` | 可用 |
| 知网 | VPN 轨 | 中文 | 单片 ≤25、片内 gap **≥75s**、片间冷却 ≥1800s、**日累计 ≤40 条** | 可用（有风控） |
| 中华医学期刊 | VPN 轨 | 中文 | 只吃 `pdf_status=3`，`--only-cma` | 可用 |
| 英文出版社 | VPN 轨 | 英文 | Springer 88.7% / IEEE 100% / SD 限流（冷却 ≥半天、gap ≥25s） | 可用 |
| **OA / PMC** | **自由轨** | 英文 | ⭐ **走 Edge `:9224`**：`start_edge_oa.py --daemon` + `CHROME_CDP_PORT=9224`；天花板仅 5.1% | 可用（**可并行**） |
| 受限出版社 | 未实现 | 英文 | Wiley/T&F/ACS/RSC 被 Cloudflare 锁死 ≈484 条 | **须机构加白名单** |

> ⛔ **资源轨是「能否并行」的唯一判据**（`tools/flow_channels.py::lane_of()`）：
> VPN 轨组内**必须串行**（共用 Chrome :9223 的单账号会话），
> 自由轨跑独立实例、免 WebVPN，**可与 VPN 轨并行**。
> ⇒ **先看轨，再看库**；别按「哪个数据库」拍并行方案。

## 常用命令速查

```bash
# 知网分片（起手参数：2 片 × 25 条、gap 75；真放开全库须 --journals ""）
bash tools/run_cnki_shards.sh --shards 2 --per-shard 25 --gap 75 --cool 1800 --carriers "学术期刊" --journals ""

# 万方批量（注意垫片端口 3457）
WF_SHIM=http://127.0.0.1:3457 python tools/wf_pdf_batch.py --status
python tools/wf_batch_supervisor.py --shim http://127.0.0.1:3457 --gap 15 --retry-errors

# OA
python tools/oa_browser_batch.py --all --conc 3

# 口径与结算
python tools/flow_channels.py        # 打印通道登记表
python tools/_audit_now.py
```

## 输出规范

面向用户的汇报固定四段：① **规模**（本轮处理/成功/跳过）；② **逐通道结果表**；③ **四分类 A/B/C/D**（须平）；④ **下一轮建议**（哪些通道值得继续投工时、是否需人工过验证）。

## References

- `references/preflight-checklist.md` — ⭐ **开工前交接清单**：读交接 / 环境自检 / 配额闸门 / **起手参数卡** / 反面清单
- `references/channel-registry.md` — 通道登记表：命令、节奏、准入、状态
- `references/routing-and-cleanup.md` — 路由判据决策树与题名清洗规则
- `references/settlement.md` — 四分类结算口径、SQL、账实相符核验、台账治理
