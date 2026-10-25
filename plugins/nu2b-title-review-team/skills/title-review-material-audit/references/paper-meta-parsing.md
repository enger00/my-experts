# 论著元数据解析（作者 / 单位 / 刊名）与本院判定

主脚本 `_paper_meta.py`，结果落 `_papermeta.sqlite3`（`paper_meta` + `paper_meta_ov` 人工覆盖 + `pdf_p1` 首页带坐标行 + `doi_journal`）。

⚠ **绝不能全量重跑 `_paper_meta.py`**：`INSERT OR REPLACE` 会**删旧行插新行**，`_COLS` 之外的列（`cr_json`/`cr_hit`、`src`/`if_value`/`corr_author`/`first_unit`）被**整列清空**。
改走**只 UPDATE** 的幂等脚本（均自动备份）：`_recn_affil.py --lang cn|en`、`_upd_journal.py --apply`、`_fix_local.py --apply`。

## 一、业务规则

1. **排名第一 = 第一作者；排名最后 = 通讯作者**。中文论文常不标 `*`/`△`，须兜底。
   ⚠ 末位兜底**只对中文姓名**生效
2. **有角标 → 按角标对应单位；无角标 → 全体共用同一单位**（仅当单位块确实只有 1 个时才填，否则留空不猜）

## 二、姓名切分

- 分隔符优先，切不通才用姓氏表回溯
- 姓氏表取《百家姓》全文（**漏一个姓 = 整行判废并误抓摘要**）
- 中文姓名首字必须是姓氏，**但对申报人本人豁免**
- 学位词 `DEGREE_WORDS` 须从作者名剥离；⚠ **刻意不收 MA/BA**（会误伤"Ma（马）"）；取上标编号前先剥学位

## 三、单位块

**三条即停**：① 含句号且 >25 字；② 中文单位行后遇纯英文行；③ 遇摘要/关键词。

**续行合并**（两条都常有）：邮编折行；**英文单位折行**——`_CONT_TAIL` 命中即以 `of|and|the|for|in|on|at|to|with|from|by|de|la|del|und|et`、逗号/分号/冒号、或 `second|first|third|affiliated|medical|clinical|general|central|key|cancer` 结尾 → 并入上一行。
> 未做此处理时，续行自带 university/china 会被当成新单位行，又因无角标被丢弃：**75 条/19 行 → 13 条/4 行**。

**角标切分四要素**（缺一条整串粘成一坨、第一作者误判本院）：
1. 句点可能是**全角 `．`(U+FF0E)**
2. 整串常被括号包裹，`^` 后须容许 `[（(]`
3. 编号后可能无标点
4. **长度门槛必须在剥掉角标后再判**（"2．邵阳中心医院"仅 6 汉字）

⚠ 角标只认**独立成词**的编号 `[a-eA-E](?![a-z])`，否则 `Department` 的 D 被当角标（实测污染 27 行）。
⚠ 英文刊把多个单位挤在一行、编号后不留空格（`…China,2The Second…`）：只有下一段以**机构词**开头时才把逗号当条目分隔（lookahead 要容空格）。切分正则需加"句点 + 角标 + 机构词"分支。

**其它坑**：
- `AFF_KW` 须含 `保健院|卫生院|疾控|防治|血站|疗养院|诊所|检验所`
- 作者与单位同一行先剥括号；`_title_idx` 必须传过滤后的 lines
- **连字 ﬁ ﬂ ﬃ ﬀ ﬄ st（U+FB00–FB05）须 `.translate(_LIG)` 还原**——`Aﬃliated` 会让本院判定完全失效
- `_clean_aff_val`：截 `Page N of N` / `Xxx et al.` / `Co-first author` / `These authors contributed` / `Equal contribution` / `http`，折叠重复片段

**单位在脚注区（BMC/Springer）**：排在 **Abstract 之后**，"遇摘要即停"会整块错过 → `_fallback_affils()` 把脚注区拼成**一段按角标切**（不能按行切）。
⚠ 原 `if not blk: return {}` 让兜底永不执行；⚠ 原 `if len(fb) >= 4: break` 会把正主挤掉（董香丽的 a 排第 5 位）→ 已放宽到 **12**；主路径切不全时**只补不盖**（`setdefault`，`'0'` 键除外）。

**角标黏在学位后**（`MDa` / `BDb,c`）：学位大写尾字母会让 `(?<![A-Za-z])` 否掉角标 → `_DEG_SUP` 把 `MDa → MD a`；行内回填改为**逐位**（原"角标全空才回填"漏混合行，董香丽这种第二位有角标时第一位永远拿不到 a）。

## 四、刊名（用户口径：取首页页眉，不在正文）

- `_journal_kb.py` 从院文献库学出 3584 刊名 + 2773 ISSN + DOI 段 325 + 缩写 399；`_build_p1.py` 抽首页带坐标行入 `pdf_p1`
- 优先级：① DOI 精确反查（`doi_journal`）→ ② 页眉逐行 → ③ 正文刊头
- ⚠ DOI 必须证明是本文的（首页或文首 3000 字内），否则**参考文献 DOI 张冠李戴**
- ⚠ 同水平行先合并（`Journal`/`of`/`Oral`/`Science` 拆四行不合并会错配成《Science》）
- ⚠ 旧实现"前 14 行找全大写行"把栏目名当刊名（`RESEARCH` / `A R T I C L E I N F O`），182 篇为空；现按词典整词比对，**命中不到宁可留空**
- ⚠ 词典键必须**保留词间空格**（早期去空格归一导致所有多词刊名永远匹配不上）
- 现状 **269/307 有刊名**

## 五、英文专属

- `*` 含义因刊而异：Frontiers 是**通讯**，Aging/Cell 系是**共同第一**；出现 `equal contribution` 时撤销仅由 `*` 得来的通讯标记
- 通讯识别三级：上标 → `Correspondence to:` / `*CORRESPONDENCE` 就近人名 → 中文末位兜底
- `_not_person` 判非人名时**必须先放过中文**（否则 46 条中文作者归零）

## 六、本院判定口径（LOCAL_KW，审核敏感）

**本院 = 南昌大学第二附属医院。**

```python
LOCAL_KW = re.compile(r'(南昌大学第二附属|南昌大学附属第二医院|南昌大学第二临床医学院'
                      r'|南大二附院|二附院'
                      r'|second\s+affi?l?i?ated\s+hospital'
                      r'|2nd\s+affi?l?i?ated\s+hospital'
                      r'|second\s+hospital\s+of\s+nanchang'
                      r'|hosp\s*\.?\s*2\b|hospital\s*2\b)', re.I)
OTHER_KW = re.compile(r'(first\s+affiliated\s+hospital|1st\s+affiliated\s+hospital'
                      r'|南昌大学第一附属医院|江西省人民医院'
                      r'|南昌大学附属口腔医院|南昌大学江西医学院)', re.I)
```

- ⚠ 旧口径含裸 `nanchang university`，把**一附院 / 第一临床医学院 / 江西医学院 / 附属口腔医院全算本院**
- ⚠ `affi?l?i?ated` 两个变体都要吃：正确拼写 `affiliated`（aff**il**iated）与常见变体 `affliated` 字母顺序不同，只写 `affli?ated` 会让**全部真本院判成外院**（实测从 17 行变 131 行）
- ⚠ 缩写排版 `Hosp 2, Jiangxi Med Coll, Nanchang 330006` 也是本院
- **口径只有一份**：`_recn_affil.py`、`_serve_query.py` 的 `LOCAL_RE` 必须与 `_paper_meta.LOCAL_KW` 一致，且匹配前先 `_delig()` 还原连字
- ⚠ `_recn_affil.py` 的"不倒退"保护曾含 `not new_any and old_any`：口径收紧时它会把**所有误判旧值原样锁死**，修正永远不生效 → 已删，只保留"单位/作者信息变少"的回退
- 判不出的留空 / False，**宁可判空也不判错**；`is_other_local` 标记同城南昌大学系统待人工确认

**现状（307 条）**：中文 82（有刊名 64 / 78%、有作者 75、第一本院 51）｜英文 225（有刊名 205 / 91%、有作者 208、第一本院 109、任一本院 131）。

## 七、第一完成单位（一作署名单位）是否本院（用户口径 2026-10-19）

**政策**：评分论文须**本院为第一完成单位**。一作的完成单位压根不是本院，就不属于本院的完成单位，**不可作为本院业绩计分**。

**判定必须用"排名第一位作者的署名单位"，不能用 `paper_meta.first_unit` 字段**：
⚠ 实测 59 条 `first_unit` 与第一作者 `aff` 不一致——兰琼玉论文1 的第一作者是伊朗学者，`first_unit` 却写成本院二附院。该字段取的是"第一个命中的本单位"，不是第一位作者。

```
src = authors[0].aff  →  缺失才回落 first_unit 字段
```

**三档结论**（`unit_verdict()`）：
| 值 | 含义 | 展示 |
|----|------|------|
| `True` | 本院 | 绿 ✔ 本院为第一完成单位 |
| `False` | 明确外单位 | 红 ✘ + 结论横幅 + 列表红角标 |
| `None` | 无文本 / 无法判定 | 灰 ？ 未识别（**绝不判红**） |

**⚠ 最大陷阱：上游会把正文片段当单位。** 初版直接判，30 条"外院"里近一半是正文：
`于200 余例单中心队列 科室 神经内科`、`clinical manifestations and early diagnostic`、
`germinal center (GC) responses, critically r`、`International Publis`（出版社）。
**一律标红会误伤十几个人，后果比漏判严重得多** → 必须过 `_looks_like_aff()` 形态校验：

- 长度 6–200，含机构词（`医院|大学|学院|hospital|univ|institut|college|center|laborator`）
- 不含正文停用词（`患者|科室|知情同意|伦理委员会|本文|结果|方法|余例|出版|编辑部` / `patients|study|results|we|this|were|was|is|are|setting|using|publish`）
- 不以小写字母开头（正文句子特征）
- 不以"机构词 + 逗号"开头（`University, Nanchang 330006` = 折行截断的尾巴）
- 仅含"××重点实验室/中心"而无明确医院/大学专名 → 灰（如"江西省分子医学重点实验室"，其第二单位才是二附院）
- 只写到"南昌大学"层级（未细化到二附院）→ 灰

**效果**：初版 30 条 → 校准后 **9 条 / 8 人**，逐条人工核对均为真外院（兰琼玉·伊朗阿扎德大学、朱水山·浙大药学院、刘青·邢台三院+南通大学附院、魏美林·抚顺矿务局总医院、胡晨恺·江滨医院、李张云·江苏师大、龚晨辉·江西省妇幼保健院、刘峰·上海六院）；另有 **44 条** 属"仅写学校层级/实验室"归灰待人工。

**三层标识（缺一层审核人就会漏）**：
1. **元数据卡片横幅**（`/pdf/<doc_id>`）：红底+左侧 4px 红条 —— `✘ 非本院第一完成单位`，并直接给结论"该文不可作为本院业绩计分；通讯作者虽为本院，只能作合作/参与事实留档"
2. **业绩表红角标**：`.futag` 白字红底 `✘ 一作外院`，`title` 带一作姓名与单位
3. **顶部红色汇总条**：`✘ 有 N 条业绩的第一完成单位非本院 —— …`，列到条
- 三者共用 `first_unit_of()` 单一数据源；`person_detail` 按 `paper_meta.slot` 与 `three_q_detail.位次序号` 对齐回填 `fu_local / fu_text / fu_author`，并给 `b['非本院一作条数']`
- 回归脚本 `_check_fu_tag.py`（Node 真跑渲染，断言角标数与 API 中 `fu_local===false` 条数一致、横幅存在）；清单 `_scan_firstunit.py` → `_非本院第一完成单位清单.csv`

## 八、元数据卡片与人工修正

- 三路融合：PDF 正文 + 院文献库（最准）+ Crossref
- **判定条三态**：✔绿 / ✘红 / **？灰 = 未识别**。**无数据绝不能显示红色**
- 「修正元数据」→ `GET/POST /api/pmeta`，白名单 `PMETA_FIELDS`
- **署名校验 `_author_hit` 比标题校验更能抓错配**：三级 = 作者表拼音精确相等 → 原文搜姓名 → 未命中
  - 须 ① 拼音展开 ② **姓氏多音字表**（"仇"读 Qiu）③ 过滤机构名/刊名噪声 ④ 按来源分级
  - 未命中用**橙条"存疑"**，绝不用红条断言错误。现 307 行误报仅 2（刘青，真信号）
