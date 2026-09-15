# Limfinity 脚本运行模型（Helper 库 / ScheduledScript 入口 / 顶层作用域铁律，2026-08-31 实测定稿）

> **来源**：多次在 Limfinity 后台写 Ruby 脚本时踩「立即运行」≠ cron、顶层常量在 `def` 内不可见、顶层局部变量跨语句不保留、作用域 NameError 的坑。
> **适用**：凡在 Limfinity 后台写 Ruby 脚本（Helper Script / ScheduledScript / 被 run_script 触发的脚本）**都先读此文**，再读 `limfinity_value_hydration.md`（取值水合）与 `supabase_sync.md`（同步落地）。
> **一句话结论**：Limfinity 有两种执行入口——**Helper = 代码库**、**ScheduledScript = 唯一定时入口**；作用域规则反直觉（顶层常量/变量在 `def` 内不可见、跨语句不保留）；「立即运行」按钮不是 cron，权威验证只能等 cron。

---

## 1. 两种入口模型（先分清你在写哪一种）

| 入口 | 是什么 | 怎么跑 | 你写的代码长什么样 |
|---|---|---|---|
| **Helper Script** | **代码库**（只定义 `def`，不挂 cron，不会自动执行） | 被别的脚本 `require_script` 调用，或被 ScheduledScript 引用 | 顶层只放 `def`，不写主流程 |
| **ScheduledScript** | **唯一定时入口** | cron 到点执行其**顶层代码** | 先 `require_script '<库名>'`，再在**顶层**（不在 `def` 里）写主流程 |

⚠️ **Limfinity 没有「第三种」执行方式**：REST `/api/run_script` 触发的脚本，本质也是执行一份已注册 Helper/ScheduledScript 的**顶层代码**（只是入口从 cron 变成 API）；详见 `run_script_push_sync.md`。

---

## 2. 作用域铁律（最反直觉，每条都踩过）

### 2.1 顶层常量在 `def` 内不可见 → 配置/映射一律用「方法暴露」

```ruby
# ❌ 错误：顶层常量 CONFIG 在 def 里读不到
CONFIG = { 'a' => 1 }
def work
  CONFIG['a']   # NameError: undefined local variable or method `CONFIG'
end

# ✅ 正确：把配置/映射包成方法
def config_map
  { 'a' => 1 }
end
def work
  config_map['a']
end
```

### 2.2 顶层局部变量跨语句不保留 → 参数读取包成 `def`

```ruby
# ❌ 错误：顶层 data 下一句可能已丢，def 内更读不到
data = JSON.parse(context.data.to_s)
def work
  data   # NameError
end

# ✅ 正确：读取包成 def，显式传参
def read_data
  JSON.parse(context.data.to_s)
end
def work
  d = read_data
  # ...
end
```

### 2.3 顶层代码引用 def → 必须 `require_script` 先把库加载到顶层

ScheduledScript 顶层 `require_script '<库>'` 后，库里的 `def` 都在顶层作用域，主流程顶层代码可直接调用；但若主流程把一切塞进一个 `def main` 再 `main()`，而 `main` 里用到的「常量」没按 §2.1 方法暴露，仍会 NameError。

---

## 3. ⛔「立即运行」≠ cron（头号误导，曾害误判 worker 没生效）

- 后台「**立即运行**」按钮是**受限的逐语句求值**环境：前向引用必 `NameError`，且不加载完整的 cron 上下文。
- 它**过 `.46` 的 nginx `proxy_read_timeout`（120s 硬限）**——遍历记录的脚本在这 120s 内必被掐断（见 `run_script_push_sync.md` §8 红线）。
- **切勿用「立即运行」验证 worker 是否生效**。权威验证 = **等 cron 跑一轮**，看「同步结果」报告里的 `worker_version` / `MODE` 探针（见 `supabase_sync.md` §14.5 四步部署验证循环）。

---

## 4. 取值 & 水合模型（指针，不展开）

完整版见 `references/limfinity_value_hydration.md`（2026-09-01 定稿）。速记：

- **批量枚举** `subjects()` / `try_subjects()` 返回**未水合**轻量对象 → 自定义字段恒 `nil` → 必须先 `Subject.find(rid)`。
- **`get_value(引用字段)`**（如 `放置地点`）返回**已是水合好的**关联主体 → ⛔ **禁止再 `Subject.find`**（再 find 会把满载实例换成未加载实例，自定义字段全 nil，实测 125 台设备 `所属院区` 0/125）。
- **判归属优先用主体 `name`**，不要读字段（`get_value('所属院区'/'科室名称')` 对所有科室返回同一值，会误判院区）。

---

## 5. 取文件值 & Storage 耐久坑（指针，不展开）

完整版见 `references/supabase_sync.md` §13。速记：

- 文件实体在 `.46`，须 `Subject.find` 满载再取；`get_value(文件字段)` 返回 `ScriptRunner::FileProxy`（**非字符串**）。
- Storage object key 必须**纯 ASCII**（拒中文/`%`）→ 用 `rid/pid.ext` 不透明 key。
- 大文件过 `.56` Kong（19.6MB）易 504 → 显式 `Content-Length` + 重试；根治调 `.56` Kong `proxy_read_timeout`。

---

## 6. 铁律速查（每条都是实测踩过的）

1. ⚠️ **Helper = 库、ScheduledScript = 入口**：Helper 只写 `def` 不写主流程；ScheduledScript 先 `require_script` 再在顶层写主流程。
2. ⚠️ **顶层常量在 def 内不可见** → 配置/映射用「方法暴露」，别用顶层常量。
3. ⚠️ **顶层局部变量跨语句不保留** → 参数读取包成 `def`，显式传参，别依赖顶层变量。
4. ⚠️ **「立即运行」不是 cron**：受限逐语句求值、前向引用 NameError、过 120s nginx 限；验证靠 cron 看 `worker_version`。
5. ⚠️ **API 只能执行已注册脚本、不能新建/排程**：每改一行都要人工到 `.46` 后台重粘贴注册（迭代以天计）→ 脚本必须「自证型」（失败按原因归类计数 + 记返回值 `class` + 结尾 `puts` 结构化 JSON），详见 `run_script_push_sync.md` §8。
6. ⚠️ **双入口有红线**：需遍历大量 Subject 记录的脚本**只能**走 ScheduledScript 内部执行；经 `/api/run_script` 触发必 504（耗时在启动阶段 ~120s，与参数无关）。详见 `run_script_push_sync.md` §8 红线。

---

## 7. 生产脚本与本地代表

| 角色 | 本地代表 | 部署为 |
|---|---|---|
| `.56` 同步脚本（Python） | `.workbuddy/tmp/sync_limfinity_remote.py` | `~/limfinity_sync/sync_limfinity.py` |
| Limfinity helper（含院区/文件逻辑） | `scripts/limfinity_helper_script_v12_yard.rb` | `.46` 后台 `mini_sync_schema` |

助手要按照本文件模型排查 Limfinity 脚本「不执行 / NameError / 取值为空 / 跑不完」类问题；凡涉及取值水合跳 `limfinity_value_hydration.md`、涉及同步落地跳 `supabase_sync.md`。
