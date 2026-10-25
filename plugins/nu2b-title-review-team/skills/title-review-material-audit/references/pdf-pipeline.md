# PDF / 文档流水线

适用：把磁盘上的原始材料与申报表里的"代表作/业绩"逐条对上，并能在线预览。

## 一、目录规范（2026-10-17 定）

- **权威材料根**：`原件材料/<类别>/<姓名>/<文件>`（类别：正高-医师 / 副高-医师 / 副高-护理 / 副高-药技 / 副高-副系列 / 副高-自然科学 / 正高-药技）
- **人名目录下不再有任何子目录**，文件一律平铺；对照清单 `原件材料/_清单.csv`（源路径→目标路径）
- 生成脚本 `_flat_materials.py`（**只读源 + 复制**，不改动 `2026职称材料_已解压`）
  - 同名加 `(工号)`、重名文件加 `_2/_3`、跳过 `__MACOSX` / `~$` / `._`
  - 已跑：3674 文件 / 归属 226 人 / 未归属 0
- **转码产物根**：`原件材料_已转码/<类别>/<姓名>/<原名>.pdf`（与 `原件材料` 同构）

⚠ **`pdf_doc` 表不是全量文件库**，而是"**代表作命中文件**"子集（`_index_pdfs.py` 只对接代表作）。
凡**门槛业绩类材料**（专题报告等）不可只查 `pdf_doc`，必须回落到磁盘/扁平目录，否则会误判"未提交"。

## 二、doc_id 与索引

- PDF **二进制不入 SQLite**；只存 `pdf_doc`（索引）+ `pdf_link`（槽位映射）+ 服务 Range 流式读取
- `doc_id = stable_id(abs_path)` = `int.from_bytes(sha1(...).digest()[:7], 'big')`
- 专题报告合成行用 `sr_doc_id()` = `hexdigest[:13]`（**52 bit，必须 < 2^53**，见下）
- 脚本 `_index_pdfs.py`（可重跑幂等，自检含孤儿链接 / 越界路径 / 禁用词）
- **权威源已切换**：2026-10-17 起 `pdf_doc.abs_path/rel_path/dedup_key` 统一指向 `原件材料`（366 条迁移、24 条"已转码"保留原路径、`doc_id` 不变）。迁移脚本 `_migrate_to_flat.py`（执行前自动备份库）

### ⚠ doc_id 大整数必须字符串化（血泪坑）

- **症状**：点"查看报告"跳 `/pdf/<doc_id>` 报 `未找到该文件记录`
- **真因**：合成 doc_id 原 60 bit ≈ 1e18，以 **JSON 数字**下发，浏览器 `JSON.parse` 按双精度舍入（该量级 ulp=128）→ **96.8% 错位**（`898019781966882573 → 898019781966882600`）
- **双重修复（两条都要留）**：
  1. 生成侧压到安全区：`hexdigest[:13]` = 52 bit
  2. 传输侧强制字符串：`person_detail` 合成行 `doc_id = str(did)`，与 `pdf_doc` 支的 `CAST(doc_id AS TEXT)` 口径统一
- **测试方法论**：Python `json.loads` 整数无损、直接拼 URL 也正确，**完全无法暴露此问题**。凡"Python 造 ID → 浏览器使用"的链路，必须用 **Node 做 `JSON.parse` 往返测试**（从原始 JSON 文本取字面量比对）

## 三、Word→PDF 转码规范

- ⚠ **本机 COM 自动化彻底不可用，不要再试**：WPS 为 32 位（`Program Files (x86)`），两个 Python 均 64 位 → 64 位进程看不到 WOW6432Node 注册；PowerShell 工具禁止 COM 实例化；`cscript` 被 LOLBin 策略拦截。ProgID 虽为 `KWPS.Application` 也救不回来。
- **唯一可行通道：LibreOffice headless**
  - 安装：`winget install --id TheDocumentFoundation.LibreOffice -e --accept-source-agreements --accept-package-agreements --disable-interactivity`
  - ⚠ **包 ID 不是 `LibreOffice.LibreOffice`**
  - 装完 `C:\Program Files\LibreOffice\program\soffice.exe`
  - 调用范式（**避开中文/特殊字符文件名**：先拷到临时目录换成 ASCII 名，再批量转，最后搬回）：

    ```bat
    soffice --headless --norestore --invisible ^
      -env:UserInstallation=file:///<独立profile目录> ^
      --convert-to pdf --outdir <输出目录> <file1> <file2> ...
    ```

    一次启动可转多份（20 份/批），188 份仅 279 s、0 失败
- 脚本：`_convert_sr_pdf.py`（按文件名批量）+ `_convert_selected.py`（按系统实际选中项补漏，能捞到"标题回落命中""抗疫专题报告"等不含关键字的文件）
- 现状：**专题报告 212/229 可直接预览、0 个仅文本**；17 人属真实缺件

### 转码件接入服务的三个必做动作（少一个就预览不了）

1. `file_index()` 多根扫描 `原件材料` + `原件材料_已转码`（`sr_by_name` 排序里 `ext != '.pdf'` 会让转码件自动胜出）
2. **`DOC_ROOTS` 追加 `CONV_ROOT`** —— 否则 `safe_abs()` 返回 None → 全部 404
3. `sr_by_title()` 并列比较须加 `(LCS, 是否PDF)` 二级键，否则同 stem 的 .doc 会压过 .pdf

⚠ 合成文档行 `_SR_DOC` **必须带 `person_key/姓名/科室`**：`pdf_page()` 直接取 `r['person_key']` 查同人导航，缺失即 `KeyError` → 预览页 500。

## 四、代表作 ↔ 原件对接

- **理由**：申报表填了论文 ≠ 交了原文；实测有人两篇代表作一篇都没上传
- **三级匹配**（`attach_paper_sources`）：
  1. `pdf_link` 槽位（**最权威**，专治 `代表作二.pdf` / `材料9.pdf` 这类无语义文件名）
  2. 标题 ↔ 文件名 4-gram（容忍英文截断）
  3. `论文N` / `代表作N` 序号推定（UI 打"推定"角标）
- ⚠ **`papers.是否代表作` 列不可信**：1129 条中空 487、是 391、否 247，并有**一人自填十几篇"是"**（规定仅三项）。**权威口径永远是 `pdf_link` 槽位**
- 前端三档展示：有槽位（蓝"是"+槽位，缺原件标红 `⚠未见原文`）／仅自填（橙"是"+`自填` 角标）／其余（否/—）。统计条另列"另有自填代表作 N 篇"——自填超标本身即审核点
- `_PAPER_EXCL` 必须排除：专题报告/申请表/业绩目录/查新报告/检索报告/专利/课题/证书类，否则误配
- 现状：论文 1129 条可查看 420（37.2%）；**正式代表作 322 条已对接 279（86.6%）**，缺 43 条/27 人

## 五、按 PDF 正文内容识别论文（最重要的一节）

- **为什么必须读正文**：① 上游 `pdf_link` 存在**两篇代表作共用同一 doc_id 的串档**（陈未平）；② 文件名乱七八糟且无标准（`neuroscience 2024.pdf`、`tmp_KEoaJi.pdf`、`材料9.pdf`）。光看文件名必然错配。
- **做法**：
  - `import pymupdf`（⚠ **不要用 `import fitz`**，已废弃会告警）。本机 PyMuPDF 1.28.2
  - 取 PDF **前两页正文** → 与论文标题做 4-gram 覆盖比对：`|标题gram ∩ 正文gram| / |标题gram|`
  - 阈值 **0.72**（中文 0.60）
  - 断点行/软连字符不影响：`_norm` 去标点 → `_grams` 去空格，序列仍连续
- **指纹缓存**：`_pdf_head.sqlite3`（`_build_pdf_head.py`，1923 PDF / 83 s）
- 380/1923 无文本层（扫描件），UI 须提示"人工打开"，不能断言缺件

## 六、院文献库对接（`E:\TRAE\英文文章\ncu2fy_literature`）

- `ncu2fy.db`（英文 12016 篇，`author_units` 106520 行提供**逐作者单位**）、`cn.db`（中文 12388 篇）；PDF 名只有数字 id
- 元数据**优于 Crossref**（按本院建）；391 条命中 295（75.4%），缺原文 71→38
- 落点复用"已拆分"链路（`split_doc` 加 `src`/`lit_key`），服务零改动即可出 `/sp/<id>`
- ⚠ **两库 id 编号空间完全独立**，绝不能跨库按数字 id 取文件
- ⚠ `cn.db` 的 `pdf_path` 是**相对路径**（可能 `'NO_OA'`），曾致 **17 条中文论文配成英文 PDF**。装载时补 LIT 前缀；复制后读正文校验兜底（有文本层 <0.30 不登记，扫描件不拦）
- 其它：doc_id 为 NULL 才算缺件；正则禁嵌套量词（曾灾难性回溯）；稀有 gram 倒排（RARE_N=14 / TOPK=60）；DOI 命中须 `sim>=0.45`；`paper_meta` INSERT 用**显式列名**
- 撤销错配补件时**只删 split_doc + 文件，保留 paper_meta**

## 七、合并件拆分

- 脚本 `_split_merged.py` / `_split_index.py`（PyMuPDF 按标题定位页码切分）
- 参数 `--person/--all/--dry/--pks/--keep-head/--json`
- 产出 `原件材料_已拆分/<工号>_<姓名>/`，登记进 `_split.sqlite3`（表 `split_doc`，按 [工号, 槽位]）
- 人员页业绩表优先直连 `/sp/<sp_id>`
- ⚠ **doc_id 冲突别一律废弃 `pdf_link`** —— 可能是合法合并件；第一版全废弃使匹配率 86.6%→81.1%

## 八、快捷入口

- `GET /api/open-folder/<工号>` → `material_dir()` 定位该人原件材料目录（**原件材料 优先、已转码次之**），`safe_abs()` 校验后 `os.startfile()` 在本机弹资源管理器
- 无材料人员返回 404 并在按钮旁红字提示、路径自动复制到剪贴板
