---
name: docx-report
user-invocable: true
description: 以既有 Word（.docx）模板为骨架、结合工作区调研内容生成正式中文调研报告；完整还原模板样式，产出无自动编号、带可点击上标引用角标与详尽参考文献的 .docx。
---

# Docx Report - 模板化调研报告生成

## 触发方式

`/docx-report <模板.docx 路径> [输出目录]`

例：`/docx-report /root/Working/Macao/Output_Report/Report_Template/xxx.docx /root/Working/Macao/Output_Report`

## 适用场景

- 用户给出一份 **.docx 提纲/模板**，要求"结合 space 中的所有调研内容"生成一份**正式报告**。
- 需要交付 **Word 成品**（而非 Markdown），且对版式、引用、参考文献有明确要求。
- 工作区里已有大量一手/二手调研资料（`Interview_Research/`、`company-dossier/`、`*.md`、`*.csv`、PDF、截图），需要被系统性地"用起来"而不是重新调研。

不适用：纯 Markdown 报告、无模板的自由写作、单纯的资料汇总。

## DSH 工具映射

| 用途 | 工具 |
|---|---|
| 读模板 / 源文件 | `bash`（unzip 解析 docx）+ `read` |
| 盘点工作区 | `glob` / `grep` / `read` |
| 缺口补研 | `skill(research)` 模式 B，或直接 `subagent` + `web_search` |
| 并行专题底稿 | `subagent`（后台，每专题 1 个） |
| 落盘 | `write` / `edit` |
| 生成 docx | `bash` + `python3 assets/md2docx.py` |
| 交付 | `present` |

---

## 一、硬性要求（用户验收标准，必须逐条满足）

> 以下 R1–R7 来自用户的明确反馈，是本 skill 的**验收口径**，不是建议。

### R1 模板保真
先用 `unzip` 解开模板 `.docx`，从 `word/document.xml`、`word/styles.xml` 提取**样式基线**，逐项还原：

- `w:docDefaults`：默认字体、字号（`w:sz` 为半磅，22 = 11pt）、行距（`w:line` 288 = 1.2 倍）；
- 各级标题：字体（如 `等线`/`Arial`）、字号（章 32=16pt、节 24=12pt）、是否加粗、`outlineLvl`、段前段后间距；
- 页面：`w:pgSz`（A4 = 11905×16840 twips）、`w:pgMar` 页边距；
- 章节结构：**逐节对应模板提纲**，不得缺章、不得擅自改章序。

详见 `TEMPLATE_SPEC.md`。

### R2 禁止 Word 自动编号（最高优先级）
**绝对不要对列表使用 `List Number` / `List Bullet` 样式或写入 `<w:numPr>`。**
Word 会把全文档所有引用同一编号定义的段落视为**同一个序列**，导致打开后出现"整篇文档跨标题连续编号"的严重版式错误。

正确做法：列表一律渲染为**普通段落 + 字面量标记**：
- 有序：`1.` `2.` `3.` 作为文本写入，**每个列表独立从 1 重新计数**；
- 无序：`•` 作为文本写入；
- 用 `left_indent` + 负 `first_line_indent` 制造悬挂缩进。

### R3 引用角标必须可点击跳转
- 正文引用以上标形式呈现：`vertAlign=superscript`、正文字号的 ~0.8 倍、深蓝色（如 `#1F497D`）；
- 每个角标是 **内部超链接**（`<w:hyperlink w:anchor="_RefN">`），点击跳转到《参考文献》对应条目；
- **多编号引用必须逐个成链**：`[[1,2,5,20,42]]` 要渲染成 `[` + 链接1 + `,` + 链接2 + … + `]`，
  **每个数字各自是一条超链接**（分别指向 `_Ref1`、`_Ref2`、`_Ref5`…），**不得把整串做成一个指向首编号的链接**；
- 参考文献条目段落必须有对应书签 `<w:bookmarkStart w:name="_RefN">`，书签 id 全文档唯一；
- 交付前必须校验**所有 anchor 均有同名书签**（零失效链接），且**链接总数 ≈ 各引用编号个数之和**（而非角标段落数）。

### R4 参考文献必须详尽
每条参考文献至少包含：**机构/作者 + 文件名/标题 + 文号或日期 +（如有）URL 或工作区落盘路径**。
- 按主题分组编号（国家战略 / 地方政策 / 法律法规 / 统计基础设施 / 企业与行业 / 本次调研既有成果 / 补充调研专题…）；
- **分组标签必须是标题（`#### 【一】…`），不是加粗正文**——否则不会出现在 Word 导航窗格的标题树里；
- 条目在 Markdown 中写作 `Rn. <内容>`，由转换器自动生成书签并渲染为 `[n] <内容>`；
- 附录末尾附一句"原始网页/PDF 与逐字摘录落盘位置"，保证可回溯。

### R5 重要判断、结论与表格数据都必须有引用
- 覆盖范围：**核心结论摘要、定位判断、各章小结、方案对比结论、模式价值、所有含数字/金额/法规编号的段落**；
- **表格同样必须挂角标**：关键数据速览表、统计表、对标表、判给台账、预测表的每一行数据，只要能定位到源，都要在**该行最后一个单元格（通常是"口径与来源/说明/依据/备注"列）末尾**追加 `[[n]]`；同一格多源写作 `[[a,b]]`；
  - 转换器已支持表格内引用（`add_table(..., allow_cite=True, cite_size=8.0)`），角标按表内字号自动降级为 8pt；
  - 多行规则用脚本批量追加，不要手改（见 `assets/add_table_citations.py`）；
  - **推荐做法**：在"关键数据速览"表下加一句表注——"本表及各章表格中的上标数字为参考文献编号，点击可跳转至附录F对应条目"；
- **不允许存在"僵尸文献"**：参考文献表里的每一条都必须在正文或表格中被至少引用一次；交付前统计被引用编号集合，若 1..N 有缺口，要么补挂角标、要么删除该条目；
- 密度：达不到"每段都有"时，至少保证**所有结论性段落 100% 有角标**；
- 交付前用脚本统计"含结论/判断/建议/定位 等关键词的段落中有角标的比例"，必须为 **100%**。

### R6 证据纪律
- 分级：`official`（政府/公报/监管文件）＞ `company`（企业自述）＞ `media`（第三方媒体）＞ `inference`（推算）；
- **不编造**：拿不到就写"未取得/未公开（负面发现）"——负面发现与正面事实同等有价值；
- **口径矛盾并录**：两个官方口径不一致时并列呈现并注明差异，不得静默择一；
- 推算一律就地标注 `【推算】`，不与已核实事实混同。

### R7 语言与命名
- 正文统一**简体中文**；引用来源若为繁体，转写为简体；
- **公司/机构名保留其登记的原文用字**，避免识别歧义；
- 文件名建议 `<报告全名><YYYYMMDD>.docx`，与模板同目录或用户指定目录。

---

## 二、执行流程

### Step 0：解析模板
```bash
cd <模板目录> && python3 - <<'PY'
import zipfile, re
z = zipfile.ZipFile('<模板>.docx')
d = z.read('word/document.xml').decode('utf-8')
paras = re.findall(r'<w:p[ >].*?</w:p>', d, re.S)
for i, p in enumerate(paras):
    t = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S))
    style = re.search(r'w:pStyle w:val="([^"]+)"', p)
    print(i, style.group(1) if style else '', t)
PY
```
同时读取 `word/styles.xml` 的 `<w:docDefaults>` 与 `document.xml` 末尾的 `<w:sectPr>`，记录字体/字号/行距/页面。

**产出**：一份"模板章节清单 + 样式基线表"，作为后续写作与转换的对照基准。

### Step 1：盘点工作区
用 `glob`/`grep` 建立"来源清单"：
- 用户点名的参考资料（务必全部读完并提取要点）；
- 同目录/兄弟目录的既有调研报告、结构化结果（`results/*.json`）、落盘一手资料（`sources/`）、问卷 `*.csv`、截图 `*.png`；
- 关键词检索补漏（政策名、机构名、金额、指标）。
   
**产出**：`章节 → 可用来源` 的映射表，并标出**缺口**。

### Step 2：缺口补研（三选一，按优先级）
1. **先查其他 source 文件**——多数"缺失信息"其实已落盘在别的目录，只是没被读；
2. **启动 `/research`（模式 B 深度叙事）或直接 `subagent`** 做定向补充调研；新调研内容**必须落盘到**：
   `<workspace>/Interview_Research/Complementary_Research/<专题名>/深度调研报告.md` + `sources/`（逐字摘录 + `SOURCES.md` 清单）；
3. **如实标注"未取得"**，并说明已检索范围与建议的函询渠道。

### Step 3：并行专题子代理
每专题 1 个后台 `subagent`，brief 必须**自包含**（子代理看不到主对话），并强制：
- 先穷尽工作区既有语料，再做增量检索；
- 每个采用的源落盘 + 建 `SOURCES.md`（本地文件名｜标题｜机构/年份｜URL｜一句话相关性｜LOCAL-EXISTING/NEW-WEB）；
- 每条事实带来源文件名；推算标 `【推算】`；矛盾标 `【冲突】`；未取得标 `【未取得】`；
- 返回**结构化要点**，不写最终报告（最终成文由主控负责，保证文风一致）。

> 经验：同时启动 3–5 个专题子代理效率最高；子代理容易超字数目标与堆砌细节，brief 里要写明"返回要点而非全文"。

### Step 4：主控叙事成文（Markdown）
按模板章节逐节写作，分文件管理便于增量编辑：
```
<输出目录>/.parts/
  part1.md   # 标题 + 第1–3章
  part2.md   # 第4章
  part3.md   # 第5–7章 + 附录（含参考文献 R# 条目）
```
写作纪律：结论先行、数据带单位与口径、每个重要判断预留引用位。

### Step 5：插入引用角标 + 生成参考文献
1. 先写好**附录《参考文献》**，条目形如 `R12. 机构《文件名》（文号/日期）。落盘：<路径>。`
2. 编写 `citations.json`：`section_refs`（章节号 → 引用编号）＋ `keyword_refs`（关键词正则 → 引用编号）。
3. 运行：
```bash
python3 assets/insert_citations.py --config citations.json part1.md part2.md part3.md
# 重跑前先清空： --strip
```
4. **人工补漏**：脚本会跳过引用块（`>`）与纯文字段落，需手工给"章末小结/引语/定位判断"等补上 `[[n]]`。
   ⚠️ 务必写**双中括号** `[[n]]`；写成单括号 `[n]` 只是普通文本，不会变成可点击角标。

### Step 6：Markdown → Word
```bash
cat <主md去掉首行标题> .parts/part2.md .parts/part3.md > .parts/full_draft.md
python3 assets/md2docx.py .parts/full_draft.md "<输出目录>/<报告名>.docx" \
        --title "<报告标题>" --toc
```
转换器已内置：模板样式基线、**字面量列表编号（无自动编号）**、`[[n]]` → 上标内部超链接、`Rn.` → 书签 + `[n]` 条目、目录、页脚页码、A4 页面。

### Step 7：验收自检（必须全绿）
```bash
python3 - <<'PY'
import re, zipfile
from docx import Document
from docx.oxml.ns import qn
f = "<报告>.docx"
d = Document(f); x = zipfile.ZipFile(f).read('word/document.xml').decode('utf-8')
print('styles:', set(p.style.name for p in d.paragraphs))          # 只应有 Normal
print('numPr:', len(re.findall(r'<w:numPr>', x)))                  # 必须 0
print('List styles:', len(re.findall(r'ListNumber|ListBullet', x)))# 必须 0
print('superscript:', len(re.findall(r'w:vertAlign w:val="superscript"', x)))
names = set(re.findall(r'<w:bookmarkStart [^>]*w:name="([^"]+)"', x))
anchors = set(re.findall(r'<w:hyperlink w:anchor="([^"]+)"', x))
print('unresolved anchors:', [a for a in anchors if a not in names])  # 必须 []

# ★ 多编号引用：必须逐编号成链
for p in d.paragraphs:
    m = re.search(r'\[(\d+(?:,\d+)+)\]', p.text)
    if m:
        exp = m.group(1).split(',')
        got = [h.get(qn('w:anchor')) for h in p._element.findall(qn('w:hyperlink'))]
        ok = got[:len(exp)] == ['_Ref%s' % n for n in exp]
        print('多编号样例', m.group(0), '->', got, 'OK' if ok else 'FAIL')
        break

# ★ 导航窗格标题树：统计 outlineLvl 分布（1=章 2=节 3=子节/附录分组）
lv = {}
for p in d.paragraphs:
    pPr = p._element.find(qn('w:pPr'))
    ol = pPr.find(qn('w:outlineLvl')) if pPr is not None else None
    if ol is not None:
        k = ol.get(qn('w:val')); lv[k] = lv.get(k, 0) + 1
print('outlineLvl:', lv)          # 附录分组应计入 3

# ★ 表格数据引用：统计含引用链接的单元格数与表格数
cells = sum(1 for t in d.tables for r in t.rows for c in r.cells
            if 'w:anchor="_Ref' in c._tc.xml)
print('tables:', len(d.tables), '| cells with citation:', cells)   # 重要表应逐行有

# ★ 僵尸文献：被引用编号集合必须覆盖 1..N 无缺口
nums = sorted({int(m.group(1)) for a in anchors if (m := re.match(r'_Ref(\d+)$', a))})
N = max(nums) if nums else 0
print('cited refs:', len(nums), '| 未被引用的条目:',
      [n for n in range(1, N + 1) if n not in nums])              # 必须 []

# 关键判断段落引用覆盖率
key = re.compile(r'结论|判断|建议|定位|总体架构')
tot = wit = 0
for p in d.paragraphs:
    t = p.text.strip()
    if len(t) < 25 or t.startswith('['): continue
    if key.search(t):
        tot += 1
        if p._element.findall(qn('w:hyperlink')): wit += 1
print('key paragraphs cited: %d/%d' % (wit, tot))                  # 目标 100%
PY
```
再打开 Word 抽查：列表编号是否每段独立、角标是否能点击跳转。

### Step 8：交付
`present` 主 `.docx`（＋ Markdown 源文件、补充调研专题报告），并在回复中说明：结构对应关系、引用体系、以及**未取得项/口径矛盾**。

---

## 三、资源文件

| 文件 | 用途 |
|---|---|
| `assets/md2docx.py` | Markdown → docx 转换器：模板样式、**无自动编号列表**、`[[n]]` 上标内部超链接、`Rn.` 书签、目录、页脚页码 |
| `assets/insert_citations.py` | 批量插入 `[[n]]` 角标（章节默认集 + 关键词触发；支持 `--strip` 重跑） |
| `assets/add_table_citations.py` | 按"(文件, 表头行号) → 各行引用"规则，批量为**表格数据行**追加 `[[n]]`（只改行尾，可重复执行） |
| `assets/citations.example.json` | 引用配置示例（真实项目规模：86 条参考文献、332 个角标） |
| `TEMPLATE_SPEC.md` | docx 模板解析与样式基线对照表 |
| `CHECKLIST.md` | 交付前逐项验收清单 |

---

## 四、常见失败模式（真实踩过的坑）

| 失败现象 | 根因 | 规避 |
|---|---|---|
| **Word 打开后全文档跨标题连续编号** | 用了 `List Number`/`List Bullet` 样式或 `<w:numPr>` | 见 R2：字面量编号 + 普通段落 |
| **`[1,2,5]` 点哪个数字都只跳到 [1]** | 整串被当成**一个** hyperlink | 用 `add_citation()`：逐编号建链，`,` `[` `]` 为普通上标 |
| **附录分组标签不在导航窗格标题树里** | 用 `**加粗正文**` 冒充分组标题 | 写成 `#### 【一】…`（→ outlineLvl 3），并让其父级为 `### 附录X` |
| 群组标题出现在正文但不在目录 | 目录只收录 `##`/`###` | 目录生成按 `#{2,4}` 收录三级；或在 SKILL 配置中调整 |
| 角标只是普通文本，点击无反应 | 写了单括号 `[n]` 或未建书签 | 写 `[[n]]`；条目用 `Rn.` 前缀 |
| 点击角标跳转失败/报错 | anchor 与书签不匹配，或书签 id 重复 | Step 7 校验 `unresolved anchors == []`，且链接数=编号个数之和 |
| 表格里的数据没有来源 | 转换器对表格 `allow_cite=False`，且底稿未在单元格内写 `[[n]]` | 转换器改用 `allow_cite=True, cite_size=8.0`；用 `assets/add_table_citations.py` 按"行→引用"规则批量追加 |
| 参考文献表里有从未被引用的条目（僵尸文献） | 只检查"段落是否有角标"，没检查"条目是否被引用" | Step 7 增加"被引用编号集合 vs 1..N"的差集校验，输出必须为空 |
| 结论段落漏引用 | 自动脚本跳过 `>` 引用块与无数字段落 | Step 5 第 4 条：人工补漏 + Step 7 覆盖率检查 |
| 参考文献被正文引用符号污染 | 参考文献行也参与打标 | 条目用 `Rn.` 前缀，脚本对附录区整体跳过 |
| 大文件反复用 `edit` 极慢且易错 | 逐处编辑 40k+ 字文档 | 用 Python 脚本批量替换/插入；分 part 文件增量维护 |
| 子代理产出与主报告文风割裂/超长 | 让子代理直接写"成稿" | 子代理只产**事实底稿 + 落盘源**，成稿由主控统一写 |
| 数字自相矛盾 | 不同来源口径不同却静默择一 | R6：并录两个口径并注明差异 |
| 简体/繁体、公司名混乱 | 直接沿用来源用字 | R7：正文转简体，专名保留登记原文 |
