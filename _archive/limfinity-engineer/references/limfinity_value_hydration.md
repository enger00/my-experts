# Limfinity Ruby DSL：取值与水合模型（2026-09-01 定稿，设备院区链路实证）

> **来源**：2026-08-31 ~ 09-01 打通「设备资产登记 → 放置地点(引用科室) → 所属院区」链路时踩出的全套坑。
> **为什么单独成文**：这是 Limfinity 内部 Ruby DSL 的**通用行为模型**，凡是「取到的值是 nil / 取到的值不对 / 关联对象读不到自定义字段」都落在这里，与具体业务（院区、科室、设备）无关。设备院区链路的完整落地见 `references/supabase_sync.md` §14。
> **一句话结论**：**两种水合行为完全相反，混用必炸** —— 批量枚举返回的是**未水合**对象（要补 `Subject.find`）；而 `get_value(引用字段)` 返回的**已经是水合好的**主体（再补 `Subject.find` 反而把它换回未加载实例）。

---

## 1. 三（四）种取值对象形态速查

| 来源 | 返回的是什么 | 自定义字段可读？ | 正确做法 |
|---|---|---|---|
| `subjects(...)` / `find_subjects(...)` / `try_subjects(...)` | **轻量对象**（Subject 的未完整加载实例，只带内置列） | ❌ `get_value` 返回 `nil`（不是报错，是静默空） | 先 `Subject.find(rid)` 拿到满载实例再取值 |
| `Subject.find(rid)` | **满载实例** | ✅ | 直接 `get_value` |
| `get_value(引用字段)`（如 `放置地点`、`科室`） | **已水合的关联主体** | ✅ **可直接 `get_value`** | ⛔ **禁止再 `Subject.find`** |
| `get_value(文件字段)` | `ScriptRunner::FileProxy`（不是字符串！） | —（`fp.filename` / `fp.file` / `fp.to_data_url`） | 见 `references/supabase_sync.md` §13.2 |

### 1.1 判断当前手上对象是哪一种（探针法）

拿不准时，把它塞进输出里回传，**一次即可定位**，别盲猜：

```ruby
probe = {
  klass:        obj.class.name,
  attrs:        (obj.attributes.keys rescue nil),
  name:         (obj.name.to_s rescue nil),
  rid:          (obj.id rescue nil),
  yaml_loaded:  (obj.instance_variable_get(:@fully_loaded) rescue 'n/a'),
  sample_value: (obj.get_value('所属院区').to_s rescue 'ERR')
}
```

判据：`attrs` 只有内置列（`id/name/uuid/barcode_tag/serial_number/description`）+ 自定义字段取值全 nil → **未水合**；`attrs` 仍只有内置列但自定义字段**取得到值** → 那是正常的（因为自定义字段本来就不是 DB 列，见 `supabase_sync.md` §10），说明已水合。

---

## 2. ⛔ 头号坑：引用字段返回的是「已水合」主体，禁止再 `Subject.find`

### 2.1 现象

```ruby
loc = eq.get_value('放置地点')      # 返回科室主体
loc2 = Subject.find(loc.id)         # ⛔ 画蛇添足
loc2.get_value('所属院区')          # => nil  ← 明明有值却取不到
```

实测后果：125 台设备中 `所属院区` 命中 **0/125**（原本 `放置地点` 有 123/125），整列全空。

### 2.2 根因

`get_value(引用字段)` 走的是 Limfinity 的关联水合路径，返回的是一个**已经把自定义字段值装载好的** Subject 实例。再调 `Subject.find(id)` 会**用一个新的、未完整加载的实例把它替换掉** —— 新实例只有内置列，自定义字段自然全 nil。

### 2.3 正确写法

```ruby
loc = eq.get_value('放置地点')
next if loc.nil?
yard = loc.get_value('所属院区')   # ✅ 直接读，不要 find
```

**对照**：`subjects(...)` / `try_subjects(...)` 返回的轻量对象**必须** `Subject.find` 水合（那是唯一正确的水合用途）。两者的区别：

- 轻量对象来自**批量枚举**（一次拉一批，不会逐个水合自定义字段）；
- 关联主体来自**单条引用解析**（逐个解析，顺带把值装好了）。

生产脚本 `scripts/limfinity_helper_script_v12_yard.rb` 中，`Subject.find` **只应出现在** `build_dept_subj_map`（把 `try_subjects('科室')` 的轻量对象水合）一处；`equipment_placement` 主路径**一处都不能有**。

---

## 3. ★ 判归属优先用 `name`，不要读字段

### 3.1 现象（最隐蔽的一个坑）

设备 `放置地点` 指向科室，想取科室所属院区。两种写法：

```ruby
# A. 读字段 —— 错
loc.get_value('所属院区')     # 对所有科室都返回「生物样本资源中心东湖院区」
loc.get_value('科室名称')     # 同上，也是东湖
```

交叉表实证（125 台设备）：

| 设备 `放置地点` 指向的科室 | `get_value('所属院区')` 得到 | 实际应为 |
|---|---|---|
| 生物样本资源中心红角洲院区 | 生物样本资源中心**东湖**院区 ❌ | 红角洲院区 |
| 生物样本资源中心东湖院区 | 生物样本资源中心东湖院区 ✅ | 东湖院区 |

**结果**：8 台红角洲设备被误判成东湖，前端筛选「红角洲院区」永远 0 命中，且**没有任何报错**。

### 3.2 根因

这些自定义字段在科室主体上的取值行为不可靠（疑似字段定义跨类型复用 / 字典回退到默认值），**返回的是同一个值**，与记录本身无关。

### 3.3 正解：用主体的 `name`

biobank 的**科室名本身就是院区串**（`生物样本资源中心红角洲院区` / `生物样本资源中心东湖院区`），所以：

```ruby
def yard_of(dept_name, subj)
  dn = dept_name.to_s.strip
  return dn if dn.start_with?('生物样本资源中心')   # 科室名即院区 → 直接用
  extract_yard(subj)                                # 否则才回退去读字段
end
```

调用：`yard = yard_of(loc.name, loc)`。

> **推广**：凡是「关联主体的某个属性」与「主体的 name」含义重叠时，**优先信 `name`**。`name` 是 Limfinity 的一等属性、写入路径唯一、不会跨类型串味；自定义字段则可能被复用/回退。

---

## 4. ★ 前缀门禁：杜绝把部门名写成院区

不同科室的 `科室名称` 字段值五花八门（分子医学实验室、南昌大学神经科学研究所、细胞遗传实验室……）。若 `extract_yard` 无脑 `|| vals.first` 兜底，就会把**部门名当成院区**写进 `所属院区`，前端胶囊里出现一堆根本不是院区的选项。

```ruby
# ❌ 错误示范（v13.1 曾这样写，导致 93/125 里混入部门名）
yard = vals.find { |x| !x.to_s.empty? } || vals.first

# ✅ 正确写法（v13.1.1 起）：只接受带前缀的真实院区串
YARD_PREFIX = '生物样本资源中心'
def extract_yard(subj)
  vals = ['所属院区', '所属院区1', '科室名称', '科室名称1'].map do |f|
    (subj.get_value(f).to_s.strip rescue '')
  end.reject(&:empty?)
  vals.find { |x| x.start_with?(YARD_PREFIX) }   # 取不到就返回 nil，绝不兜底到任意值
end
```

**原则**：归属类字段**取不到就留空**（前端显示为「未归属」），**绝不拿任意非空值兜底**。宁可空，不可错 —— 空值一眼可见，错值会静默污染筛选结果。

---

## 5. 字段内部名以数字「1」结尾的取值缺陷（v8 已知 bug）

Limfinity DSL 的 `get_value` **只按 display_name 匹配、不匹配 internal_name**。当某字段的内部名以数字 `1` 结尾（如 `放置地点1`、`验收人1`、`所属院区1`）时，若该内部名与 display_name 不同，取值会静默返回空。

**对策**：候选字段名列表里**同时带上带 `1` 和不带 `1` 的两个变体**（见 §4 的 `extract_yard`），并 `rescue` 掉不存在的字段。

---

## 6. 交叉表探针法（验证归属判定是否正确）

单看结果分布（如「东湖 85、红角洲 8」）**无法证明判定正确** —— 可能只是碰巧。必须出**交叉表**：

```
[放置地点指向的科室]  →  {判定出的院区: 台数}
  生物样本资源中心东湖院区   → {生物样本资源中心东湖院区: 85}
  生物样本资源中心红角洲院区 → {生物样本资源中心红角洲院区: 8}
  分子医学实验室            → {(无): 17}
```

**判据**：对角线（科室名 = 院区名）应当饱满；非 biobank 科室应落 `(无)`。若出现「红角洲科室 → 东湖院区」这种**跨行**，说明判定逻辑还在读字段（§3 的坑）。

参考实现：`.workbuddy/tmp/check_dept_remote.py`（查 department 主数据 + 设备 `放置地点科室` 分布 + 交叉表）。

---

## 7. 铁律速查（每条都是实测踩过的）

1. ⚠️ **批量枚举 → 必须 `Subject.find` 水合**：`subjects()` / `try_subjects()` 返回轻量对象，自定义字段恒 nil；nil 是静默的，不会报错。
2. ⚠️ **引用字段 → 禁止 `Subject.find`**：`get_value('放置地点')` 已返回水合主体，再 `find` 会把它换成未加载实例 → 自定义字段全 nil（实测 125 台设备 `所属院区` 全空即此坑）。
3. ⚠️ **判归属优先用 `name`**：科室主体上 `get_value('所属院区'/'科室名称')` 会对所有科室返回同一个值（东湖），导致红角洲 8 台设备误判；`loc.name` 才是对的。
4. ⚠️ **归属字段取不到就留空，绝不兜底任意非空值**：必须加 `start_with?('生物样本资源中心')` 前缀门禁，否则部门名会污染院区列。
5. ⚠️ **内部名以数字 `1` 结尾的字段取值有缺陷**：候选名同时带 `所属院区` 与 `所属院区1` 两个变体。
6. ⚠️ **验证靠交叉表，不靠结果分布**：分布对不代表判定对，「红角洲→东湖」这类跨行错误只有交叉表能暴露。
7. ⚠️ **拿不准对象形态就回传 introspection**（`class.name` / `attributes.keys` / 样例 `get_value` 结果），与 `supabase_sync.md` §10.6 同一方法论，一次定位。
8. ⚠️ **不要指望报错**：本文件涉及的三个坑（未水合、误 `find`、字段串味）**全部静默**——返回值是 nil 或错误的值，脚本照常 `success:true`。唯一可靠的正对照是交叉表。

---

## 8. 生产脚本与本地代表

| 角色 | 本地代表 | 部署为 |
|---|---|---|
| `.56` 同步脚本 | `.workbuddy/tmp/sync_limfinity_remote.py` | `~/limfinity_sync/sync_limfinity.py` |
| Limfinity helper（含院区逻辑） | `scripts/limfinity_helper_script_v12_yard.rb` | `.46` 后台 `mini_sync_schema` |

helper 里与本文相关的三个方法：`extract_yard`（§4）、`yard_of`（§3）、`equipment_placement`（主路径，调用前两者）。版本号体现在 `mode` 字段（当前 `v13.1.2_yard`），用于探针确认线上跑的是哪一版。
