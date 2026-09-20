# TEMPLATE_SPEC.md — docx 模板解析与样式基线

## 1. 单位换算（Word XML）

| 单位 | 说明 | 换算 |
|---|---|---|
| `w:sz` | 半磅（half-point） | 22 → 11pt，24 → 12pt，32 → 16pt，44 → 22pt |
| `w:line`（`lineRule=auto`） | 1/240 行 | 288 → 1.2 倍行距，240 → 单倍 |
| `w:spacing before/after` | twips（1/20 pt） | 480 → 24pt |
| `w:pgSz` | twips | A4 = 11905 × 16840 |
| `w:pgMar` | twips | 1440 → 1 英寸（2.54cm）；1800 → 3.17cm |
| `w:ind firstLine` | twips | 首行缩进 2 字符（11pt）≈ 440 |
| python-docx `Pt/Twips/Cm` | — | `Twips(11905)` 直接对应 `w:pgSz` |

## 2. 解析模板（三步）

```python
import zipfile, re
z = zipfile.ZipFile(TEMPLATE)
# (a) 正文段落 + 样式 + 段落属性
d = z.read('word/document.xml').decode('utf-8')
for i, p in enumerate(re.findall(r'<w:p[ >].*?</w:p>', d, re.S)):
    text = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S))
    pPr  = re.search(r'<w:pPr>.*?</w:pPr>', p, re.S)
    print(i, text, '|', pPr.group(0) if pPr else '')
# (b) 默认样式
s = z.read('word/styles.xml').decode('utf-8')
print(re.search(r'<w:docDefaults>.*?</w:docDefaults>', s, re.S).group(0))
# (c) 页面设置
print(re.search(r'<w:sectPr.*?</w:sectPr>', d, re.S).group(0))
```

要点：
- 段落可能由多个 run 拼成（换字体/加粗会拆 run），**文本必须拼接所有 `<w:t>`**；
- `w:bCs` 只作用于复杂文种，**不等于中文加粗**；中文加粗看 `<w:b/>`；
- 模板可能只用 `outlineLvl` 而不挂 `Heading` 样式——以 `outlineLvl` + 字号/加粗判断层级。

## 3. 样式基线对照（以《澳门AI…调研报告(优化版)》模板为例）

| 元素 | 字体 | 字号 | 加粗 | 间距（before/after） | 行距 | 其他 |
|---|---|---|---|---|---|---|
| 文档默认 | 等线 / Arial | 11pt（sz 22） | 否 | 0 / 160 twips | 1.2 | `w:docDefaults` |
| 书名标题 | Arial / 等线 | 22pt（sz 44） | 是 | 480 / 480 | 1.2 | — |
| 章标题（一、二、…） | Arial / 等线 | 16pt（sz 32） | 是 | 320 / 120 | 1.2 | `outlineLvl=1` |
| 节标题（2.1、3.4） | Arial / 等线 | 12pt（sz 24） | 模板未加粗 | 300 / 120 | 1.2 | `outlineLvl=2` |
| 子项（3.4.1…） | Arial / 等线 | 11pt（sz 22） | 否 | 120 / 120 | 1.2 | 左缩进 ~220 |
| 页面 | — | — | — | — | — | A4 11905×16840；页边距 上下 1440、左右 1800 |

> 转换器 `md2docx.py` 中的常量：`CN_FONT/EN_FONT`、`BODY_SZ=11`、`H1_SZ=16`、`H2_SZ=12.5`、`H3_SZ=11.5`、`TITLE_SZ=22`；页面在 `convert()` 内按上表设置。换模板时**只改这些常量**。

## 4. Markdown → 样式映射

| Markdown | 输出 | outlineLvl |
|---|---|---|
| `--title` 参数 | 书名标题（居中、22pt 粗体） | — |
| `## 一、…`（二级标题） | 章标题（16pt 粗体） | 1 |
| `### 2.1 …`（三级标题） | 节标题（12.5pt 粗体） | 2 |
| `#### 3.4.1 …`（四级及更深） | 子标题（11.5pt 粗体） | 3 |
| 普通段落 | 正文 11pt，首行缩进 2 字符 | — |
| `- ` / `* ` | `•` 字面量 + 悬挂缩进 | — |
| `1. ` / `1) ` | `1.` 字面量，**每列表重新计数** | — |
| `> ` | 灰字引用块（左缩进） | — |
| `\| a \| b \|` | `Table Grid` 表格，首行底纹 `#DCE6F1` | — |
| `[[12]]` / `[[3,7]]` | **上标 + 内部超链接**；多编号时**每个编号各成一条链接**合并入书签 `_Ref12` / `_Ref3`、`_Ref7` | — |
| `R12. …` | 参考文献条目：书签 `_Ref12` + 前缀 `[12]` | — |

**标题层级与导航窗格**：Word 导航窗格的标题树由 `outlineLvl` 驱动（不依赖 `Heading` 样式）。
`## 一、` → L1；`### 2.1` → L2；`#### 3.4.1` → L3。
**附录内的分组标签必须写成 `#### 【一】…`**（而不是 `**【一】…**` 加粗正文），否则不会出现在标题树里。
目录（静态 TOC）按 `#{2,4}` 收录三级，因此这些分组标签也会作为附录的子条目出现在目录中。

## 5. 与模板的一致性边界

- **必须还原**：页面尺寸/页边距、字体、各级字号、加粗、行距、章节结构。
- **允许增强**：目录、页脚页码、表格底纹、引用角标颜色——模板是提纲态，成品报告需要这些才可用。
- **不得引入**：Word 自动编号、自动多级列表、模板未定义的样式名。
