# Limfinity 7.0 `run_script` 外部触发实时同步模式

> 来源：2026-08-14 大华门禁刷脸记录 → Limfinity「门禁出入记录」实时推送（已跑通）。
> 本模式与「WPS/腾讯文档 OAuth 拉取同步」「7.0 仪表板渲染」是**三条不同路径**，不要混用。

## 一、什么时候用这套模式

- **数据源在 Limfinity 外部**的机器上（门禁机、采集服务器、本地 SQLite、第三方系统），需要把数据**主动推**进 Limfinity。
- 典型场景：门禁机记录在本地数据库，由一台"推送代理"常驻轮询、增量 POST 到 Limfinity。
- 区别于另两条路径：
  - **WPS/腾讯文档同步**：源在云端，Limfinity 侧脚本去**拉取**（OAuth token）。
  - **Limfinity 定时执行脚本**：脚本在 Limfinity **内部**、按时间触发。
  - **本模式**：由**外部进程主动触发** Limfinity 脚本（REST 调用），最灵活、可实时。

## 二、架构

```
[数据源机器 10.103.200.55]                      [Limfinity 10.103.200.46]
推送代理 (Python, nssm 服务, 轮询本地 SQLite)
   │  SELECT * FROM tb_access_record
   │    WHERE id > 水位
   │      AND access_time >= 截止时间(可选)
   │      AND event_code <> 'DoorStatus'
   │    ORDER BY id LIMIT 500
   │  enrich(): 解析 raw_json 派生字段, 滤掉无业务意义字段
   │  POST /api/run_script  {name, username, password, data:[...]}
   ▼
Limfinity Helper Script (dahua_access_sync, 须勾「通过API调用」)
   收 data → 逐条 create_subject → 回写 UID 同步结果 + 检查 success 才推进水位
```

## 三、铁律清单（每条都实测踩过）

1. **`/api/run_script` 是外部进程触发 Limfinity 的唯一代码通道**
   `POST http://{host}/api/run_script`，body `{name, username, password, data}`；脚本通过变量取 `data`。

2. **Limfinity 7.0 不会把 `data` 注入成脚本局部变量！**
   裸写 `data.each` 会报 `undefined local variable or method 'data' for #<ScriptRunner::Context>`。
   必须**兼容多路取数**（见下方 Ruby 骨架），最后全 nil 才抛带诊断线索的报错。

3. **Helper Script 必须勾「通过API调用」（脚本编辑器右上角勾选项）**
   不勾 → run_script 报 `Script 'xxx' is disabled`。它不是通用"启用"开关，是该脚本专用的"允许 API 调用"标志（极易漏，首次必卡）。

4. **run_script 永远返回 HTTP 200，即便脚本出错**
   出错时 body 是 `{"error":true,"success":false,"message":"..."}`。
   推送端**必须**判断 `resp.get('success') is True` 才推进水位；否则会：假成功 → 丢数据 / 或 `raise` 导致 success:False → 水位卡死 → 5 秒后重推 → 死循环刷日志。

5. **Subject Type 在 7.0 无代码建科目 API**
   必须后台 UI 手动建科目、字段、字典、UID 同步结果记录。REST `subject_types`/`userfields` 仅只读。

6. **`raise_message` 实测会抛异常**（不是单纯提示）
   把它当"完成提示"用，会把已成功的「同步结果回写」又包成"异常"外壳。正常完成就干净结束返回 `success:True`。

7. **`find_subjects` 全量拉取会 "too many subjects found"**
   门禁等持续增长科目，不带 limit 的全量查询超默认上限即报错。改用「信任水位 + 逐条 `create_subject`」，名称已存在 `rescue` 良性跳过。

8. **Dictionary 字段值不在字典内会静默丢弃（不报错）**
   `set_value('方向','进门')` 若字典无"进门"则列空、不报错。建科目时务必确认字段类型与字典选项与脚本发送值一致。

9. **`set_value` 字段名对不上会静默忽略**
   写库前逐项核对 Limfinity 实际显示名（中文系统）。字段名差一个字就进不去还不报错。

10. **服务账号「密码永不过期」**
    `api_sync` 这类服务账号建好后**必须勾**「密码永不过期」，否则 run_script 报 `密码已过期` 中断。

11. **水位(watermark) + 时间下限双保险**
    - 水位记"已推最大 id"到 `watermark.txt`；
    - `SINCE_HOURS=24` 防水位文件丢失时回炸全量历史（设为 0 = 纯水位模式）；
    - `BATCH=500` 分批，防单 POST 超 30s 超时卡死；
    - **「名称已存在」必须良性跳过**，否则 raise → success:False → 水位不推进 → 死循环。

12. **nssm 常驻服务注意**
    - 路径含空格须双引号：`"C:\Program Files\nssm-2.24\win64\nssm.exe" ...`；
    - 配 `AppStdout`/`AppStderr` 到 `.log` 便于看 `[OK]/[ERR]`；
    - 改脚本/配置须 `nssm restart` 才生效（正在跑的是旧内存）。

## 四、推送代理骨架（Python，跑在数据源机器）

```python
# -*- coding: utf-8 -*-
import sqlite3, time, os, json, requests
from datetime import datetime, timedelta

DB_PATH   = r'E:\dahua\access_log.db'            # 门禁机实际路径
LIM_URL   = 'http://10.103.200.46/api/run_script'
LIM_USER  = 'api_sync'                           # 通用集成账号，所有 run_script 同步共用
LIM_PWD   = '***'                                # 真密码（勿硬编码进分享包）
SCRIPT    = 'dahua_access_sync'
WM_FILE   = os.path.join(os.path.dirname(__file__), 'watermark.txt')
POLL_SEC  = 5
SINCE_HOURS = 24   # 时间下限；0 = 关闭（纯水位，水位丢失会重推全部）
BATCH     = 500    # 每轮最多条数，防超时

IP_NAME_MAP = {                                    # device_ip => 门禁中文名
  '192.168.1.10': '自动化存储实验室',
  '192.168.1.11': '生物样本库前门',
  '192.168.1.13': '生物样本库后门',
}

def load_wm():
    try: return int((open(WM_FILE).read().strip() or 0))
    except Exception: return 0

def save_wm(v):
    open(WM_FILE, 'w').write(str(v))

def enrich(rec):
    rec = dict(rec)
    rec.pop('raw_json', None)                      # 丢弃大字段
    rec['device_name'] = IP_NAME_MAP.get(rec.get('device_ip',''),'')
    for k in ('direction','device_sn','door_no'):  # 无业务意义字段不推送
        rec.pop(k, None)
    return rec

def poll():
    last = load_wm()
    cutoff_clause = ""; params = [last]
    if SINCE_HOURS and SINCE_HOURS > 0:
        cutoff = (datetime.now() - timedelta(hours=SINCE_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        cutoff_clause = " AND access_time >= ?"; params.append(cutoff)
    params.append(BATCH)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM tb_access_record WHERE id > ?{cutoff_clause} "
        "AND event_code <> 'DoorStatus' ORDER BY id LIMIT ?".format(cutoff_clause=cutoff_clause),
        tuple(params)).fetchall()
    conn.close()
    if not rows: return
    records = [enrich(dict(r)) for r in rows]
    payload = {'name': SCRIPT, 'username': LIM_USER, 'password': LIM_PWD, 'data': records}
    r = requests.post(LIM_URL, json=payload, timeout=30)
    resp = r.json() if r.text else {}
    if r.status_code == 200 and resp.get('success') is True:    # ⚠️ 必须以 success 为准
        save_wm(max(rec['id'] for rec in records))
        print(f"[OK] 推送 {len(records)} 条，水位={max(rec['id'] for rec in records)}", flush=True)
    else:
        print(f"[ERR] HTTP {r.status_code} resp={resp}", flush=True)

if __name__ == '__main__':
    print("push_agent started, watermark=", load_wm(), flush=True)
    while True:
        try: poll()
        except Exception as e: print("[ERR]", e, flush=True)
        time.sleep(POLL_SEC)
```

## 五、Limfinity 同步脚本骨架（Ruby Helper Script，须勾「通过API调用」）

```ruby
SUBJECT_TYPE = '门禁出入记录'

# db 列名 => Limfinity 字段显示名（逐项核对真实显示名，差字即静默忽略）
FIELD_MAP = {
  'id'          => '门禁记录ID',
  'user_name'   => '姓名',
  'user_no'     => '工号',
  'verify_type' => '验证方式',
  'access_time' => '刷脸时间',
  'device_ip'   => '设备IP',
  'device_name' => '门禁名称',
  'result'      => '通行结果',
  'snap_url'    => '抓拍图路径',
  'create_at'   => '入库时间',
}

added = 0; skipped = 0; first_err = nil; field_warn = nil

# ⚠️ 兼容 Limfinity 各版本 data 注入方式（7.0 不注入局部变量 data）
__payload = nil
begin; __payload = data          if defined?(data);     rescue; end
begin; __payload = @data         if defined?(@data);    rescue; end
begin; __payload = context.data  if defined?(context) && context.respond_to?(:data); rescue; end
begin; __payload = params['data'] if defined?(params) && params.respond_to?(:[]);    rescue; end
begin; __payload = $data         if defined?($data);    rescue; end
begin; __payload = JSON.parse(__payload) if __payload.is_a?(String); rescue; end
raise "未取到 run_script 的 data" if __payload.nil?
data = __payload

data.each do |rec|
  biz_id = rec['id'].to_s
  next if biz_id.empty?
  if rec['user_name'].to_s.empty? && rec['user_no'].to_s.empty?   # 无身份事件跳过
    skipped += 1; next
  end
  name = "DA#{biz_id}"                       # 记录名科目内唯一
  begin
    create_subject(SUBJECT_TYPE, name: name) do |s|
      FIELD_MAP.each do |db_col, lf_field|
        v = rec[db_col]
        next if v.nil? || v.to_s.empty?       # ⚠️ 空值跳过，set_value(nil) 会清空字段
        val = (v.is_a?(Integer) || v.is_a?(Float)) ? v.to_s : v
        begin
          s.set_value(lf_field, val)
        rescue Exception => fe
          field_warn ||= "字段[#{lf_field}]值[#{val}]写入失败：#{fe.message}"  # 非致命
        end
      end
    end
    added += 1
  rescue Exception => e
    if e.message =~ /already exists/i        # ⚠️ 已存在=良性跳过，不卡死水位
      skipped += 1
    else
      first_err ||= e.message; skipped += 1  # 仅真实错误记录
    end
  end
end

# —— 同步结果回写（字段名固定「同步结果」，UID 区分各脚本，门禁=3433）——
ts = Time.now.strftime('%Y-%m-%d %H:%M:%S')
summary = "门禁同步 #{ts}：新增#{added} 跳过#{skipped}" +
          (first_err ? " ｜ 首条失败：#{first_err}" : "") +
          (field_warn ? " ｜ 字段警告：#{field_warn}" : "")
begin
  sync = find_subject(uid: 3433)
  if sync.nil?
    summary += " ｜ 未找到 UID=3433 的同步结果记录"
  else
    sync.set_value('同步结果', summary); sync.save
    summary += " ｜ 同步结果已回写(UID=3433)"
  end
rescue Exception => e
  summary += " ｜ 回写异常：#{e.message}"
end
raise summary if first_err     # 仅真实错误才失败（success:False → 推送端不推进水位）
```

## 六、常见失败 → 原因 → 修法 速查表

| 推送端日志 | 根因 | 修法 |
|---|---|---|
| `密码已过期` | 服务账号密码过期标记未清 / 未设永不过期 | Limfinity 账号勾「密码永不过期」 |
| `Script 'xxx' is disabled` | Helper Script 未勾「通过API调用」 | 编辑器右上角勾上该选项 |
| `undefined local variable or method 'data'` | 7.0 不注入局部变量 data | 改用兼容多路取数（见骨架） |
| `There are too many subjects found` | 开头全量 find_subjects | 改水位 + 逐条 create_subject |
| `...already exists: DA4363` + 水位不推进 | 「已存在」被当致命错误 raise | 改为良性跳过（rescue 不 raise） |
| 字段整列空（如方向）但其他字段有值 | Dictionary 选项不匹配 / 字段名不对 | 核对字典选项与真实显示名 |
| 日志刷同一条 `[ERR]` 死循环 | raise → success:False → 水位不推进 | 同「已存在」处理 |
| HTTP 200 但 `success:False` | 脚本内部错误 | 看 message 字段定位 |

## 七、nssm 部署速查（Windows 服务常驻）

```bat
REM 路径带空格必须双引号
"C:\Program Files\nssm-2.24\win64\nssm.exe" set DahuaPushAgent AppStdout E:\dahua\push_agent.log
"C:\Program Files\nssm-2.24\win64\nssm.exe" set DahuaPushAgent AppStderr E:\dahua\push_agent.log
"C:\Program Files\nssm-2.24\win64\nssm.exe" set DahuaPushAgent AppParameters "-u E:\dahua\dahua_push_agent.py"
"C:\Program Files\nssm-2.24\win64\nssm.exe" restart DahuaPushAgent
"C:\Program Files\nssm-2.24\win64\nssm.exe" status DahuaPushAgent   REM 应返 SERVICE_RUNNING
```
> AppStdout 文件在 restart 后由 nssm 自动新建（目录须存在、服务账号有写权限）。

---

## 八、Helper Script 双入口：ScheduledScript + run_script（2026-08-31 实战）

### ⛔ 选型红线（先看这条，能省半天）

**"双入口"是有前提的 —— 不是任何脚本都能两个入口随便挑。**

若脚本需要**遍历大量 Subject 记录**（几十条以上），则 **只能走 .46 定时脚本内部执行**，
**`/api/run_script` 触发必定 504**，且**与参数无关**：

- 实测：某 worker 需遍历 137 条 Subject（equipment 125 + personnel 12）。
  - `{"max_uploads":6,...,"time_budget":100}` → **504**
  - 极简 `{"max_uploads":1,"upload_read_timeout":5,"time_budget":5}` → **仍是 504**
- 根因：**耗时不在业务逻辑段，而在启动阶段** —— 加载 subject 记录（Limfinity DSL/ORM）
  本身就要 ~120s，撞上 nginx `proxy_read_timeout`。而脚本内的 `time_budget` 之类预算
  **只管得住业务循环，管不住启动阶段**。
- 对照佐证：只遍历**字段定义**（subject_types）的 `mini_sync_schema` 秒回 `success:true`
  → 差异就在"要不要遍历记录"。
- 判据：**用极简参数（如 `time_budget:5`）试一次，若仍 504，即可确诊是启动阶段慢，
  不是业务逻辑慢** —— 这时调参毫无意义，必须换内部执行。

➡️ 结论：涉及"遍历记录逐个处理"的批处理脚本，一开始就该按 **ScheduledScript 内部执行**设计，
别在 API 触发上调参浪费时间。API 触发适合**轻量、不遍历记录**的脚本（如 schema 同步、单条写入）。

同一份 Helper Script 可**同时**被两种入口执行，无需注册两份。但「定时执行」的接法取决于 Limfinity 对脚本的分类：

| 入口 | 触发方式 | 是否过 nginx 120s 限 | 建议参数 |
|---|---|---|---|
| **ScheduledScript（.46 内部定时）** | 见下方两种接法 | ❌ 不过（内部执行） | 不传 data → 走宽松默认值 |
| **run_script API（外部/手动）** | `POST /api/run_script` 传 `data` | ✅ 过（120s 掐断） | 传 `data` 收敛各项上限 |

**★ 两种接法（2026-08-31 易云澄清，关键）**

- **接法 A（worker 自身可被定时选中）**：ScheduledScript 的"脚本"字段**直接选 worker 本体**，worker 顶层自执行。
- **接法 B（Helper / 定时分类严格分离 · 易云实际环境）**：worker 注册为 **Helper Script**（不挂 cron、不自动执行，只 `def` 定义方法），**另建一个 ScheduledScript 薄壳**，其正文用
  `require_script 'limfinity_file_upload_worker'` 加载 helper 的定义后调用入口方法（如 `run_file_upload_worker`）。
  这样可复用代码全在 helper，定时脚本保持极薄。**`require_script` 是进程内调用，不过 nginx，不触发 120s 限。**

> 判据：若后台「Helper Script」即"只被别的脚本 require、自己不跑"，则用接法 B；若 worker 能直接被定时任务选为脚本本体，则接法 A 更省事。两者都合法，**不要混用**。

三个要点：

1. **禁止的是 `Net::HTTP` 回环薄壳，不是 `require_script` 薄壳**
   后台定时任务**可以**是一个薄壳脚本，用 `require_script 'helper名'` 引helper后调用其方法（接法 B）——这是合法的 DRY 写法。
   ❌ **唯一禁止**的是薄壳里用 `Net::HTTP` 回环调 `http://127.0.0.1/api/run_script` 去触发——
   那样请求会**再次经过 .46 前 nginx 的 120s `proxy_read_timeout`**，
   等于把"内网定时不受 120s 限制"的优势全部作废。

2. **用 `data[...]` 区分两套行为，一套代码两处用**
   超时/批量这类参数必须可配，因为两种入口的约束完全不同：
   ```ruby
   MAX_UPLOADS_PER_RUN = (_cfg['max_uploads'].is_a?(Integer) && _cfg['max_uploads'] > 0) ? _cfg['max_uploads'] : 20
   UPLOAD_READ_TIMEOUT = (_cfg['upload_read_timeout'].is_a?(Integer) && _cfg['upload_read_timeout'] > 0) ? _cfg['upload_read_timeout'] : 30
   TIME_BUDGET_SEC     = (_cfg['time_budget'].is_a?(Integer) && _cfg['time_budget'] > 0) ? _cfg['time_budget'] : 240
   ```
   - 定时跑（不传参）：`20 / 30s / 240s` 全速；
   - API 触发（传参）：`{"max_uploads":6,"upload_read_timeout":12,"time_budget":100}` → 6×12=72s < 120s 总限。
   - `read_data` 必须对无 data 场景兜底返回 `{}`（定时脚本不传参也安全）。

3. **总时长预算（TIME_BUDGET）是定时脚本的必需品**
   单文件超时调大后，最坏总耗时会随批量线性放大；若超过 cron 间隔就会**前后两轮重叠**。
   务必加"到点即停"的总预算（已改的字段仍照常落盘），并让 `budget_stopped=true` 视为正常而非错误。

### ★ 自证型调试法（本模式最重要的工程教训）

**背景约束**：Limfinity 的 API **只能执行已注册脚本，不能新建/排程脚本**（已实测：10 个 method 探测 + `GET /api/scripts` → 404）。
因此**每改一行脚本，都要人工在 .46 后台重新粘贴注册一次** —— 迭代周期以"天"计，绝不是改完就能试。

➡️ **推论：脚本必须"自证型"——一次跑完就把根因暴露出来，而不是靠反复试错。**

具体做法（三条）：

1. **失败要按原因归类计数，不要只记总数**
   ```ruby
   stats[:no_file_samples] = {}    # 取不到值的原因 → 次数
   def bump(h, k); h[k] = (h[k] || 0) + 1; end
   # 关键：记录返回值的【类型】，这是区分"可重试"与"永远修不好"的分水岭
   _k = fp.nil? ? 'nil' : "class=#{fp.class.name} val=#{safe_str(fp.to_s)[0,60]}"
   bump(stats[:no_file_samples], "#{fn}: #{_k}")
   ```
   例如文件同步场景：若采样大量出现 `class=String`，说明 `get_value` 返回的是**文件名字符串**
   而非 `ScriptRunner::FileProxy` → 这不是超时问题，**重试一万次也修不好**，必须改取值方式。
   反之若 `class=ScriptRunner::FileProxy` 却读不出字节，才是可修的路径/流问题。

2. **参数全部可经 `data` 覆盖**：超时、批量、预算都留口子，改行为不必改代码、不必重新注册。

3. **返回结构化 JSON 报告**（`puts JSON.generate(...)`），含各项计数 + 采样 + 是否触发预算，
   外部触发时直接就能读到，不必登服务器翻日志。

### 对照实验：判断"脚本没注册"还是"我调错了"

`run_script` 对「未注册」和「调用姿势错」的报错不同，但都容易误判。用**已知已注册的脚本做正对照**一秒分辨：

```python
# 正对照选一个确定已注册、且执行无副作用的脚本（如 mini_sync_schema 只同步 schema）
for name in ["mini_sync_schema", "目标脚本名"]:
    print(name, run_script(token, name, {"probe": 1}))
```

- 正对照 `success:true`、目标 `Script 'xxx' is not found` → **脚本确实没注册**，调用姿势没问题，只能去后台注册；
- 正对照也报错 → 是**鉴权/通道/参数**问题（token、账号、勾选项），不是注册问题。

> 别忘了同时排查「Helper Script 未勾『通过API调用』」→ 报 `Script 'xxx' is disabled`（见铁律 3）。
> 双入口都用的脚本，**这个勾选项是必勾的**（它只影响 API 调用，不影响定时执行）。
