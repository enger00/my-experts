# 专家包「limfinity-engineer」维护约定（2026-08-29 确立，沉淀为元知识）

> **为什么成文**：本专家包由 `references/*.md` + `agents/limfinity-engineer.md` + `README.md` + `.codebuddy-plugin/plugin.json` 多文件组成，改一处不联动其他处就会腐化；且 `agents/*.md` 的 frontmatter `description` 对 YAML 格式极敏感——曾因混入 **1 个裸 CR** 导致整个专家包 `yaml.safe_load` 失败、加载不出来。
> **适用**：凡要新增/修改本专家包能力、references、描述、quickPrompts，先读此文，严格按「四处同步 + 验证」操作。

---

## 1. 更新必须同步四处

任何一次实质性更新，都要动这四处，少一处即腐化：

| # | 文件 | 改什么 |
|---|---|---|
| ① | `references/<主题>.md` | 知识正文（新增能力写新文件，已有能力追加章节） |
| ② | `agents/limfinity-engineer.md` | frontmatter `description` / 核心能力列表 / 工作流 / 注意事项铁律 / 接入即用资源指针 |
| ③ | `README.md` | 能力列表 / 目录结构 / **变更说明**（按日期+能力+引用章节+实测证据记） |
| ④ | `.codebuddy-plugin/plugin.json` | `version` +1、`description`、`displayDescription`、`quickPrompts` |

**验证（改完必跑）**：

```bash
cd <专家包根>
node -e "require('./.codebuddy-plugin/plugin.json')"   # 必须无报错（JSON 合法）
```

---

## 2. frontmatter `description` 铁律（YAML plain scalar）

`agents/limfinity-engineer.md` 的 `description` 是 YAML **plain scalar**（跨多行续行），值内禁两类字符，否则 YAML 解析崩：

- ⛔ **禁 ASCII `: `（冒号 + 空格）**：YAML 把它当 `key: value` 分隔符。要用中文全角「：」。
- ⛔ **禁 ` #`（空格 + 井号）**：YAML 把它当行内注释起点。

> 违反任一条都会让专家包加载失败（`could not find expected ':'` 或字段被截断）。写 description 时中文叙述用全角标点最安全。

---

## 3. ★ 裸 CR 坑排查法（二进制模式，必看）

### 3.1 现象

`agents/*.md` 的 `description` 若混进**裸 `\r`**（非 CRLF 的孤立回车），PyYAML 报 `could not find expected ':'`，整个专家包加载不出来。

### 3.2 ⚠️ 文本模式会掩盖问题

Python **文本模式** `open(p).read()` 走 universal newlines，把裸 `\r` 自动转成 `\n`，于是你本地 `yaml.safe_load` 居然通过、一上线（二进制环境）却崩。**排查必须用二进制模式**。

### 3.3 排查命令（二进制）

```python
import re
p = 'agents/limfinity-engineer.md'
b = open(p, 'rb').read()
bare_cr = re.findall(rb'\r(?!\n)', b)   # 裸 CR（问题所在）
crlf    = b.count(b'\r\n')               # 正常换行（应保留）
print('bare_CR=', len(bare_cr), 'CRLF=', crlf)
```

### 3.4 修复（只删裸 CR，保留 CRLF）

```python
b2, n = re.subn(rb'\r(?!\n)', b'', b)
open(p, 'wb').write(b2)
print('removed', n)
# 复验 frontmatter 仍可解析
import yaml
fm = b2.decode('utf-8').split('---', 2)[1].split('---', 1)[0]
yaml.safe_load(fm)
```

> 当前健康基线：裸 CR = **0**、CRLF = **323**（2026-08-31 实测）。每次大改后务必复测 `bare_CR == 0`。

---

## 4. version 与 quickPrompts 纪律

- 每次实质更新 `version` **+1**（语义：小修 +0.0.1，能力级 +0.1.0，重大重构 +1.0.0，本包用 `x.y.0`）。
- `quickPrompts` 覆盖**高频入口场景**（一句话能直接触发对应工作流），中文 `zh` + 英文 `en` 成对。
- `displayDescription` 的 `zh` 与 `en` 都要随能力更新同步，避免市场里描述过时。

---

## 5. 变更说明纪律（README.md）

每条变更按固定格式，便于回溯「哪天为什么加的、证据在哪」：

```
- YYYY-MM-DD 新增/修正「<能力名>」：<一句话做了什么>；引用 `references/<文件>.md` <章节>；实测证据 <如 61 条 / written:43 / 0 裸 CR>。
```

例：`- 2026-08-31 修正「Taro 构建铁律」：`rm -rf dist` 被 safe-delete 守卫拦截，正解改 `mv dist dist_prev`；引用 `references/miniprogram_dev_experience.md` §构建必看；实测 `mv` 后沙箱 build 约 15s 成功。`
