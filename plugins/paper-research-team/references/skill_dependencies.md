# 论文写作与循证医学团 技能依赖清单

> 绑定方式：运行时按名调用全局技能（不复制副本，避免版本分叉）。总数 92 个。

## 立题远（选题与基金策划师）— 14 个

`aim-and-hypothesis-designer`、`basic-research-design`、`basic-research-design-extractor`、`scientific-problem-selection`、`scientific-brainstorming`、`grant-proposal-assistant`、`research-proposal-generator`、`nsfc-grant-writer`、`irb-application-assistant`、`prospero-registration-helper`、`methodology-extractor`、`protocol-standardization`、`inclusion-exclusion-criteria-builder`、`scientific-critical-thinking`

## 索文津（文献检索专员）— 26 个

`pubmed-search`、`pubmed-database`、`arxiv-search`、`biorxiv-database`、`openalex-database`、`literature-search`、`lit-synthesizer`、`literature-review`、`find-paper-references`、`reference-retrieval-skill`、`bear-support`、`bear-counter`、`bear-review`、`bear-propose`、`bear-map`、`bear-trace`、`nature-ref-verifier`、`retraction-watcher`、`citation-management`、`citation-formatter`、`bib-formatter`、`format-references-zotero`、`format-references-endnote`、`pyzotero`、`wanfang-webvpn-pdf`、`webvpn-pdf-downloader`

> **全文获取双链路**：英文走全局技能 `webvpn-pdf-downloader`（南昌大学 WebVPN 机构权限；Elsevier 走直连 `pdfft` 模式，**限速 ≥12 秒/篇**，落盘前校验 `%PDF-` 头 + 尾部 `%%EOF`，残缺文件用 `fix_bad_pdfs.py` 隔离重下）；**中文走全局技能 `wanfang-webvpn-pdf`**
> （万方期刊全文，含交易防火墙 `0x05189` 验证码解锁、GIF89a 动态验证码帧合成+时间中值识读、免渲染 fetch 下载，约 28 秒/篇）。

## 著华章（学术写作工程师）— 20 个

`academic-paper`、`academic-paper-reviewer`、`academic-pipeline`、`scientific-writing`、`manuscript-peer-review`、`discussion-section-architect`、`method-writing`、`cover-letter-generator`、`rebuttal-letter-strategist`、`response-letter`、`blind-review-sanitizer`、`text-format-organizer`、`content-proofreading`、`authorship-credit-gen`、`bioinfo_analysis_plan`、`hypothesis-generation`、`paper-analyzer`、`academic-norm-review`、`reproducibility-check`、`study-limitations-drafter`

## 证循真（循证合成分析师）— 17 个

`meta-analysis`、`meta-analysis-methods-generator`、`meta-protocol-writer`、`meta-manuscript-generator`、`meta-screening-fulltext`、`meta-abstract-screener`、`systematic-review`、`systematic-review-screener`、`meta-results-forest-plot-analyzer`、`meta-results-funnel-plot-generator`、`meta-results-risk-of-bias`、`meta-results-sensitivity-analysis`、`case-control-study-planner`、`Case-control-study-quality-assessment-nos`、`cohort-study-quality-assessment-nos`、`rct-bias-assessment-rob2`、`diagnostic-study-quality-assessment-quadas-2`

## 成章仪（排版与交付工程师）— 15 个

`docx`、`docx-official`、`pptx`、`pptx-official`、`pdf`、`pdf-processing-pro`、`chinese-formal-report-docx`、`markitdown`、`style-rewrite`、`table-1-generator`、`table-1-generator-advanced`、`result-figure-consistencycheck`、`word-read-write`、`xlsx-docx-chart-embed`、`scientific-slides`

