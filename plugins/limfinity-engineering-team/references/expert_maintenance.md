# 专家团「limfinity-engineering-team」维护约定

> **沿革**：本文件原为单体专家「limfinity-engineer」的维护约定（2026-08-29 确立），随包拆分一并继承。
> 2026-09-15 改写为**团队结构**版本——原版四处同步的指针（`agents/limfinity-engineer.md`）在团队包内并不存在，属继承性失效引用。
> **适用**：凡要新增/修改本专家团的能力、references、成员描述、quickPrompts、依赖技能，先读此文。
> **为什么成文**：本包由 `references/*.md` + `agents/*.md`（6 个）+ `README.md` + `.codebuddy-plugin/plugin.json` + 依赖技能清单多文件组成，改一处不联动其他处就会腐化；且 `agents/*.md` 的 frontmatter `description` 对 YAML 格式极敏感——曾因混入 **1 个裸 CR** 导致整个专家包 `yaml.safe_load` 失败、加载不出来。

---

## 1. 更新必须同步的位置（团队版，七处）

任何一次实质性更新，都要检查这七处，少一处即腐化：

| # | 文件 | 改什么 |
|---|---|---|
| ① | `references/<主题>.md` | 知识正文（新能力写新文件，已有能力追加章节） |
| ② | `agents/<成员>.md`（6 个） | frontmatter `description` / 核心能力 / 关键铁律 / **依赖技能列表** |
| ③ | `references/skill_dependencies.md` | 成员表（技能数 + 技能名）、总数、「知识分层」章节 |
| ④ | `references/skill_dependencies.json` + `references/dependency_baseline.json` | 机器可读镜像（**两个文件都要改**，不联动） |
| ⑤ | `.codebuddy-plugin/plugin.json` | `version` +1、`description`、`displayDescription`、`quickPrompts`、**`teamInfo`**、**`members[].displayName` / `.profession`** |
| ⑥ | `README.md` | 能力列表 / 目录结构 / 使用示例 |
| ⑦ | `references/domain_index.md` | **导航层**：新增/改名 references 文件时更新「知识域 → 文件定位速查表」与「接入即用资源」；新增科目时更新「40 个真实科目分组索引」 |

> ⑦ 是**索引**不是正文：更新它时**只写指针与一句话定位，不复制正文**——正文重复会形成第二知识源。

### 成员清单（当前 6 个，改动成员必同步 teamInfo 与 members）

| 角色 | agent 文件 | 花名 | 职责 |
|---|---|---|---|
| 调度主理人（leadAgent） | `limfinity-engineering-team-lead.md` | — | 调度、串并行编排、产出汇编 |
| 集成工程师 | `limfinity-integration-engineer.md` | 冼通源 | 外部数据源→Limfinity 同步、run_script、DSL 落库与水合取值 |
| 云后端工程师 | `limfinity-cloud-backend-engineer.md` | — | .56 Supabase 同步、frp 隧道、CloudBase |
| 小程序工程师 | `limfinity-miniprogram-engineer.md` | 景舒端 | Taro 小程序、多主题 UI、CLI 自动化 |
| 运维工程师 | `limfinity-infra-ops-engineer.md` | — | 虚拟机运维、基础设施 |
| 合规与交付工程师 | `limfinity-compliance-delivery.md` | 付规达 | 合规与交付文档 |

`plugin.json` 的 `teamInfo.leadAgent` 必须指向主理人，`teamInfo.memberAgents` 必须与上表 5 位成员完全一致；
`members[]` 中每位成员的 `id` 必须与 `agents/` 下的文件名（去 `.md`）一致。

**验证（改完必跑）**：

```bash
cd <专家包根>
# ① JSON/plugin.json 合法
node -e "require('./.codebuddy-plugin/plugin.json')"
# ② 成员 id ↔ agents/ 文件名 一致性
python - <<'PY'
import json, glob, os
d = json.load(open('.codebuddy-plugin/plugin.json', encoding='utf-8'))
disk = {os.path.basename(p)[:-3] for p in glob.glob('agents/*.md')}
decl = {m['id'] for m in d['members']}
print('仅声明未落地:', decl - disk, '｜仅落地未声明:', disk - decl)
ti = d['teamInfo']
print('lead 存在:', ti['leadAgent'] in disk, '｜memberAgents 一致:',
      set(ti['memberAgents']) == (disk - {ti['leadAgent']}))
PY
# ③ 依赖技能三处一致 + 技能名可解析
python - <<'PY'
import json, os
d = json.load(open('references/skill_dependencies.json', encoding='utf-8'))
b = json.load(open('references/dependency_baseline.json', encoding='utf-8'))
allsk = [s for v in d['members'].values() for s in v['skills']]
assert d['total_skills'] == len(allsk) == len(set(allsk)) == b['total'] == len(b['skill_ids'])
assert sorted(set(allsk)) == sorted(b['skill_ids'])
root = os.path.expanduser('~/.workbuddy/skills')
print('无法解析:', [s for s in b['skill_ids'] if not os.path.isfile(os.path.join(root, s, 'SKILL.md'))])
PY
```

---

## 2. frontmatter `description` 铁律（YAML plain scalar）

`agents/*.md` 的 `description` 是 YAML **plain scalar**（跨多行续行），值内禁两类字符，否则 YAML 解析崩：

- ⛔ **禁 ASCII `: `（冒号 + 空格）**：YAML 把它当 `key: value` 分隔符。要用中文全角「：」。
- ⛔ **禁 ` #`（空格 + 井号）**：YAML 把它当行内注释起点。

> 违反任一条都会让专家包加载失败（`could not find expected ':'` 或字段被截断）。写 description 时中文叙述用全角标点最安全。
> 团队包的 6 个 agent 是**多行数组式** `skills:` / 多行 `description`——用正则扫 frontmatter 极易漏判，**判定必须直接读文件**。

---

## 3. ★ 裸 CR 坑排查法（二进制模式，必看）

### 3.1 现象

`agents/*.md` 的 `description` 若混进**裸 `\r`**（非 CRLF 的孤立回车），PyYAML 报 `could not find expected ':'`，整个专家包加载不出来。

### 3.2 ⚠️ 文本模式会掩盖问题

Python **文本模式** `open(p).read()` 走 universal newlines，把裸 `\r` 自动转成 `\n`，于是你本地 `yaml.safe_load` 居然通过、一上线（二进制环境）却崩。**排查必须用二进制模式**。

### 3.3 排查命令（二进制，遍历全部 agent）

```python
import re, glob, yaml
for p in sorted(glob.glob('agents/*.md')):
    b = open(p, 'rb').read()
    bare_cr = len(re.findall(rb'\r(?!\n)', b))   # 裸 CR（问题所在）
    crlf    = b.count(b'\r\n')
    bare_lf = len(re.findall(rb'(?<!\r)\n', b))
    try:
        yaml.safe_load(b.decode('utf-8').split('---', 2)[1]); ok = 'OK'
    except Exception as e:
        ok = 'FAIL ' + str(e)[:40]
    print(f'{p:48s} 裸CR={bare_cr:3d} CRLF={crlf:4d} 裸LF={bare_lf:4d}  {ok}')
```

### 3.4 修复（只删裸 CR，保留既有换行风格）

```python
b2, n = re.subn(rb'\r(?!\n)', b'', b)
open(p, 'wb').write(b2)
print('removed', n)
```

> 当前健康基线（2026-09-15 实测）：**6 个 agent 裸 CR 均为 0，frontmatter 全部 `yaml.safe_load` 通过**。
> 每次大改后务必复测 `裸CR == 0`。

---

## 4. 换行符约定（本项目实测真值，编辑前必看）

本包换行风格**按文件类型分层，不统一**，编辑时**必须沿用目标文件既有风格**，不可全局统一（会造成整文件重写的巨型 diff）：

| 路径 | 风格 | 实测依据（2026-09-15） |
|---|---|---|
| `agents/*.md`（6 个） | **LF** | 36 ~ 125 行，CRLF 均为 0 |
| `references/*.md`（深度文档 9 个） | **LF** | 72 ~ 820 行，CRLF 均为 0 |
| `references/*.rb` | **LF** | `wps_limfinity_sync.rb` 387 行 |
| `references/*.json`（3 个） | **CRLF** | 37 / 65 / 155 行 |
| `references/skill_dependencies.md` | **CRLF** | 35 行（**唯一的 .md 例外**） |
| `references/display_description_archive.md`<br>`references/quick_prompts_archive.md` | **CRLF** | 11 / 49 行（迁移自单体包，**沿原风格未转换**） |
| `README.md` | **CRLF** | 44 行 |
| `.codebuddy-plugin/plugin.json` | **CRLF** | 155 行 |

> 规律速记：**代码/文档类（.md 除 skill_dependencies、.rb）走 LF；配置/数据类（.json）与 README 走 CRLF；
> 由单体包迁移来的归档文件保持其原风格。** 新建文件默认用 **LF**（与多数 .md 一致）。

> ⚠️ **不要用 `grep -c $'\r'` 判定**：在 Git Bash 下该写法会退化为匹配字母 `r`，对本包大量含
> `limfinity`/`engineer` 的行全部误命中，得出「全是 CRLF」的假象（2026-09-15 实际踩过）。
> **判定换行符必须用 Python 二进制模式**统计 `\r\n` / `(?<!\r)\n` / `\r(?!\n)` 三者。

---

## 5. version、quickPrompts 与团队字段纪律

- 每次实质更新 `version` **+1**（语义：小修 +0.0.1，能力级 +0.1.0，重大重构 +1.0.0；本包用 `x.y.0`）。
- `quickPrompts` 固定 **3 条**（规范上限；多余的归档，勿直接删——见 §7）。
- `displayDescription` 的 `zh` 与 `en` 都要随能力更新同步，避免市场里描述过时。
- **团队专属**：新增/调整成员时，`teamInfo.memberAgents`、`members[]`、`agents/` 目录、`README.md`
  四处必须一致；成员 `profession.zh` 与 `displayName.zh` 要与 agent frontmatter 中的 `profession` 对应。
- **团队专属**：`references/skill_dependencies.{md,json}` 与 `dependency_baseline.json` 是**依赖技能的唯一真源**，
  改动必须三处同步（`dependency_baseline.json` 不随 `skill_dependencies.json` 自动联动）。

---

## 6. 与单体专家「limfinity-engineer」的关系（已归档，2026-09-15）

本包由单体专家「limfinity-engineer」（v1.13.1，1 个 agent）拆分而来。该单体包已于 **2026-09-15 归档**：
从 `marketplace.json` 摘除注册、目录移至 `my-experts/_archive/limfinity-engineer/`（git 历史完整，可恢复）。
**本包自此为 Limfinity 工程域的唯一维护目标。**

归档前已完成独有资产迁移，**无知识丢失**：

| 原单体包资产 | 现状 |
|---|---|
| `display_description_archive.md`、`quick_prompts_archive.md` | 已迁入本包 `references/`（字节保真） |
| agent MD 的**索引层**（40 科目分组索引、接入即用资源） | 已重构为本包 `references/domain_index.md`（导航层，不复制正文） |
| 首页个性化 3 个文件路径 | 已补录于 `domain_index.md` §四 |
| 「控件 → FieldType 映射」表 | 未迁 —— 本包 `limfinity_subject_fields.md` §〇 版本更完整 |
| `regression_cases.md` 的单体版（「单点能力」回归，59 行） | 未迁 —— 与本包版**同名不同物**，随归档留存 |

⚠️ **遗留提示**：本包 11 个 references 中，10 个曾与单体包字节完全相同。归档后不再有「改一处、另一处静默落后」
的双写风险；但若将来从 `_archive/` 取回任何文档，须先比对本包当前版本，**不可直接覆盖**。

---

## 7. 变更说明纪律

每条变更按固定格式，便于回溯「哪天为什么加的、证据在哪」：

```
- YYYY-MM-DD 新增/修正「<能力名>」：<一句话做了什么>；引用 `references/<文件>.md` <章节>；实测证据 <如 61 条 / written:43 / 0 裸 CR>。
```

例：`- 2026-09-15 修正「专家包维护约定」：原文件通篇为单体专家结构（指针指向不存在的 agents/limfinity-engineer.md），改写为团队七处同步版本；实测 6 agent 裸 CR=0、YAML 全通过。`

`quickPrompts` 归档位置：本包内新增 archive 型 reference 文件（参照单体专家的
`quick_prompts_archive.md` 体例：`# ... 原文归档` + 一句「为什么归档」说明 + 逐条 zh/en 对照）。
