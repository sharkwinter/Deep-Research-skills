#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2docx.py — 将结构化的中文 Markdown 调研报告转换为与模板
《澳门AI发展现状与算力需求调研报告20260915(优化版).docx》风格一致的 Word 文档。

模板风格（自模板 document.xml / styles.xml 提取）：
  - 正文默认：等线 / Arial，sz 22（11pt），行距 288（1.2 倍），段后 160 twips
  - 标题（书名）：Arial/等线，bold，sz 44（22pt），段前后 480
  - 章标题（一、）：bold，sz 32（16pt），段前 320/段后 120，outlineLvl 1
  - 节标题（2.1）：sz 24（12pt），段前 300/段后 120，outlineLvl 2
  - 页面：A4 (11905 x 16840 twips)，页边距 上下 1440、左右 1800 twips

关键设计（v2）：
  1. **不使用 Word 自动编号**：有序/无序列表一律以「字面量编号 + 普通段落」呈现，
     从根本上避免 Word 打开后「全文档连续编号、跨标题续号」的问题。
  2. **引用角标**：正文中的 `[[n]]` 或 `[[n,m]]` 会渲染为**上标**，并作为**内部超链接**
     跳转到参考文献条目的书签 `_Refn`；参考文献条目以 `R1. ` 开头，自动生成书签。

用法：
  python3 md2docx.py <input.md> <output.docx> [--title "报告标题"] [--toc]
"""

import sys
import os
import re
import argparse

from docx import Document
from docx.shared import Pt, Twips, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CITE_COLOR = RGBColor(0x1F, 0x49, 0x7D)

# --------------------------------------------------------------------------
# 版式档（profile）：同一份 Markdown 可输出两种版式
#   research = 研究版：简体 / 等线 11pt / 1.25 倍行距 / 段后 6pt / 左对齐
#   gov      = 政府呈报版：繁體 / 標楷體 14pt / 1.5 倍行距 / 段前 6pt /
#              两端对齐 / 首行缩进 24pt / 全篇同字号（标题仅加粗）
#              对齐依据：《澳琴聯動推進算力建設初步分析報告》（科技廳 2026-08-25）
#              实测该文：eastAsia=標楷體(740/740)、ascii=Times New Roman、
#              sz=28 全篇唯一、spacing before=120 line=360 auto、jc=both、
#              ind firstLine=480、docGrid linePitch=360
# --------------------------------------------------------------------------
PROFILES = {
    "research": dict(
        CN_FONT="等线", EN_FONT="Arial",
        BODY_SZ=11, H1_SZ=16, H2_SZ=12.5, H3_SZ=11.5, TITLE_SZ=22, TOC_SZ=16,
        LINE=1.25, BEFORE=0, AFTER=6, JUSTIFY=False, FIRST_INDENT_PT=22,
        TABLE_SZ=9.5, TOC_INDENT={1: 0, 2: 18, 3: 36},
        TOC_TEXT_SZ={1: 11, 2: 10, 3: 9.5}, DOC_GRID=None, IMG_WIDTH_CM=15.5,
    ),
    "gov": dict(
        CN_FONT="標楷體", EN_FONT="Times New Roman",
        BODY_SZ=14, H1_SZ=14, H2_SZ=14, H3_SZ=14, TITLE_SZ=14, TOC_SZ=14,
        LINE=1.5, BEFORE=6, AFTER=0, JUSTIFY=True, FIRST_INDENT_PT=24,
        TABLE_SZ=11, TOC_INDENT={1: 0, 2: 24, 3: 48},
        TOC_TEXT_SZ={1: 14, 2: 14, 3: 14}, DOC_GRID=360, IMG_WIDTH_CM=15.5,
    ),
}
PROFILE = "research"


def apply_profile(name):
    """把选定版式档的取值写入模块级常量（其余函数直接读这些常量）。"""
    global PROFILE, CN_FONT, EN_FONT, BODY_SZ, H1_SZ, H2_SZ, H3_SZ, TITLE_SZ
    global LINE, BEFORE, AFTER, JUSTIFY, FIRST_INDENT_PT, TABLE_SZ
    global TOC_SZ, TOC_INDENT, TOC_TEXT_SZ, DOC_GRID, IMG_WIDTH_CM
    assert name in PROFILES, "未知版式档：%s（可选 %s）" % (name, list(PROFILES))
    PROFILE = name
    c = PROFILES[name]
    CN_FONT, EN_FONT = c["CN_FONT"], c["EN_FONT"]
    BODY_SZ, H1_SZ, H2_SZ, H3_SZ, TITLE_SZ, TOC_SZ = (
        c["BODY_SZ"], c["H1_SZ"], c["H2_SZ"], c["H3_SZ"], c["TITLE_SZ"], c["TOC_SZ"])
    LINE, BEFORE, AFTER = c["LINE"], c["BEFORE"], c["AFTER"]
    JUSTIFY, FIRST_INDENT_PT, TABLE_SZ = c["JUSTIFY"], c["FIRST_INDENT_PT"], c["TABLE_SZ"]
    TOC_INDENT, TOC_TEXT_SZ = c["TOC_INDENT"], c["TOC_TEXT_SZ"]
    IMG_WIDTH_CM = c.get("IMG_WIDTH_CM", 15.5)
    DOC_GRID = c["DOC_GRID"]


apply_profile("research")
CLASSIFICATION = None
IMG_WIDTH_CM = 15.5
AUTHOR = "澳门AI产业与算力需求联合调研组"


# --------------------------------------------------------------------------
# low level helpers
# --------------------------------------------------------------------------
def set_run_font(run, size=None, bold=None, color=None):
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), EN_FONT)
    rFonts.set(qn('w:hAnsi'), EN_FONT)
    rFonts.set(qn('w:eastAsia'), CN_FONT)
    rFonts.set(qn('w:cs'), EN_FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def set_paragraph_spacing(p, before=None, after=None, line=1.2):
    pf = p.paragraph_format
    if before is not None:
        pf.space_before = Pt(before)
    if after is not None:
        pf.space_after = Pt(after)
    if line is not None:
        pf.line_spacing = line


def set_outline_level(p, level):
    pPr = p._element.get_or_add_pPr()
    ol = OxmlElement('w:outlineLvl')
    ol.set(qn('w:val'), str(level))
    pPr.append(ol)


def shade_cell(cell, fill="DCE6F1"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    tcPr.append(shd)


def shade_run(run, fill="EDEDED"):
    """给文字（run）加浅底纹，用于高亮【推算】【冲突】等证据标记。"""
    rPr = run._element.get_or_add_rPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    rPr.append(shd)


def add_bookmark(paragraph, name, bid):
    start = OxmlElement('w:bookmarkStart')
    start.set(qn('w:id'), str(bid))
    start.set(qn('w:name'), name)
    end = OxmlElement('w:bookmarkEnd')
    end.set(qn('w:id'), str(bid))
    paragraph._element.insert(0, start)
    paragraph._element.append(end)


def add_internal_link(paragraph, anchor, text, size=None, superscript=True, color=CITE_COLOR):
    """插入指向书签 anchor 的内部超链接。"""
    size = BODY_SZ if size is None else size
    hl = OxmlElement('w:hyperlink')
    hl.set(qn('w:anchor'), anchor)
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), EN_FONT)
    rFonts.set(qn('w:hAnsi'), EN_FONT)
    rFonts.set(qn('w:eastAsia'), CN_FONT)
    rPr.append(rFonts)
    if superscript:
        va = OxmlElement('w:vertAlign'); va.set(qn('w:val'), 'superscript'); rPr.append(va)
    c = OxmlElement('w:color'); c.set(qn('w:val'), '%02X%02X%02X' % (color[0], color[1], color[2]))
    rPr.append(c)
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), str(int(size * 2))); rPr.append(sz)
    r.append(rPr)
    t = OxmlElement('w:t'); t.set(qn('xml:space'), 'preserve'); t.text = text
    r.append(t)
    hl.append(r)
    paragraph._element.append(hl)


def add_superscript(paragraph, text, size=None, color=CITE_COLOR):
    """插入普通（非链接）上标文本，用于引用的括号与逗号。"""
    size = BODY_SZ if size is None else size
    r = paragraph.add_run(text)
    set_run_font(r, size=size)
    r.font.superscript = True
    if color is not None:
        r.font.color.rgb = color
    return r


def add_citation(paragraph, nums, size=None):
    """把 [[1,2,5]] 渲染为 [1,2,5]，其中**每个编号各自是可点击的内部超链接**。"""
    size = BODY_SZ if size is None else size
    add_superscript(paragraph, '[', size)
    for k, num in enumerate(nums):
        if k:
            add_superscript(paragraph, ',', size)
        add_internal_link(paragraph, '_Ref%s' % num, num, size=size)
    add_superscript(paragraph, ']', size)


# --------------------------------------------------------------------------
# inline parsing: **bold**, `code`, [[cite]]
# --------------------------------------------------------------------------
CITE_RE = re.compile(r'\[\[([0-9,\s]+)\]\]')
# 证据标记：由转换器加浅底纹高亮，便于读者与脚本同时定位（R6.1/R6.3）
FLAG_RE = re.compile(r'【(?:推算|估算|冲突|未取得|负面发现|口径冲突)】')
INLINE_RE = re.compile(r'(\*\*.+?\*\*|`[^`]+`|\[\[[0-9,\s]+\]\]|【(?:推算|估算|冲突|未取得|负面发现|口径冲突)】)')


def add_inline(paragraph, text, size=None, base_bold=False, allow_cite=True,
               cite_size=None):
    size = BODY_SZ if size is None else size
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith('[[') and part.endswith(']]'):
            if not allow_cite:
                continue
            nums = [x.strip() for x in part[2:-2].split(',') if x.strip()]
            if not nums:
                continue
            add_citation(paragraph, nums, size=size if cite_size is None else cite_size)
        elif FLAG_RE.fullmatch(part):
            r = paragraph.add_run(part)
            set_run_font(r, size=size, bold=True)
            shade_run(r)
        elif part.startswith('**') and part.endswith('**') and len(part) > 4:
            r = paragraph.add_run(part[2:-2])
            set_run_font(r, size=size, bold=True)
        elif part.startswith('`') and part.endswith('`') and len(part) > 2:
            r = paragraph.add_run(part[1:-1])
            set_run_font(r, size=size - 0.5, bold=base_bold)
        else:
            r = paragraph.add_run(part)
            set_run_font(r, size=size, bold=base_bold)


# --------------------------------------------------------------------------
# block builders (NO Word auto-numbering anywhere)
# --------------------------------------------------------------------------
def add_body(doc, text, indent=True, size=None, after=None):
    size = BODY_SZ if size is None else size
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=BEFORE, after=AFTER if after is None else after, line=LINE)
    if JUSTIFY:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent:
        p.paragraph_format.first_line_indent = Pt(FIRST_INDENT_PT)
    add_inline(p, text, size=size)
    return p


def add_list_item(doc, marker, text, level=0, size=None, hang=13):
    """以字面量 marker（如 '1.' / '•'）渲染列表项，普通段落，无自动编号。"""
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=0, after=3, line=1.25)
    p.paragraph_format.left_indent = Pt(18 + level * 18 + hang)
    p.paragraph_format.first_line_indent = Pt(-hang)
    r = p.add_run(marker + ' ')
    set_run_font(r, size=size)
    add_inline(p, text, size=size)
    return p


def add_heading(doc, text, level):
    p = doc.add_paragraph()
    sz = {1: H1_SZ, 2: H2_SZ}.get(level, H3_SZ)
    if PROFILE == "gov":            # 政府版式：全篇同字号，标题仅靠加粗区分
        set_paragraph_spacing(p, before=BEFORE, after=AFTER, line=LINE)
        if JUSTIFY:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    else:
        set_paragraph_spacing(p, before={1: 16, 2: 14}.get(level, 10),
                              after={1: 8, 2: 6}.get(level, 4), line=1.2)
    add_inline(p, text, size=sz, base_bold=True, allow_cite=False)
    set_outline_level(p, min(level, 3))
    return p


def add_table(doc, rows):
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(ncol):
            cell = table.cell(i, j)
            cell.text = ''
            p = cell.paragraphs[0]
            set_paragraph_spacing(p, before=1, after=1, line=1.05)
            txt = row[j] if j < len(row) else ''
            add_inline(p, txt.strip(), size=TABLE_SZ, base_bold=(i == 0),
                       allow_cite=True, cite_size=TABLE_SZ - 1.5)
            if i == 0:
                shade_cell(cell, "DCE6F1")
    sp = doc.add_paragraph()
    set_paragraph_spacing(sp, before=0, after=4, line=1.0)
    for r in sp.runs:
        r.font.size = Pt(2)
    return table


def add_quote(doc, text):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=4, after=6, line=1.25)
    p.paragraph_format.left_indent = Pt(16)
    add_inline(p, text, size=BODY_SZ - 0.5)
    for r in p.runs:
        r.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
    return p


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------
def parse_table(lines, i):
    rows = []
    while i < len(lines) and lines[i].strip().startswith('|'):
        raw = lines[i].strip()
        if re.match(r'^\|[\s:\-\|]+\|$', raw):
            i += 1
            continue
        cells = [c.strip() for c in raw.strip('|').split('|')]
        rows.append(cells)
        i += 1
    return rows, i


def add_toc(doc, lines):
    """静态目录：章（##）→ 节（###）→ 子节（####），三级缩进。"""
    entries = []
    for ln in lines:
        s = ln.strip()
        m = re.match(r'^(#{2,4})\s+(.*)$', s)
        if m:
            level = len(m.group(1)) - 1          # ## -> 1, ### -> 2, #### -> 3
            txt = m.group(2).strip().replace('**', '')
            entries.append((level, txt))
    if not entries:
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_spacing(p, before=12, after=8, line=1.2)
    add_inline(p, '目　錄' if PROFILE == 'gov' else '目　录', size=TOC_SZ,
               base_bold=True, allow_cite=False)
    _indent, _size = TOC_INDENT, TOC_TEXT_SZ
    for level, txt in entries:
        q = doc.add_paragraph()
        set_paragraph_spacing(q, before=0, after=1, line=1.15)
        q.paragraph_format.left_indent = Pt(_indent.get(level, 36))
        add_inline(q, txt, size=_size.get(level, 9.5),
                   base_bold=(level == 1), allow_cite=False)
    br = doc.add_paragraph()
    run = br.add_run()
    run.add_break(WD_BREAK.PAGE)


def _add_classification(text):
    """在页眉写入密级标识。政府文书惯例；是否启用由发文机关决定。"""
    global CLASSIFICATION
    CLASSIFICATION = text


def convert(md_path, out_path, title=None, toc=False):
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')

    doc = Document()

    normal = doc.styles['Normal']
    normal.font.name = EN_FONT
    normal.font.size = Pt(BODY_SZ)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), CN_FONT)
    normal.paragraph_format.space_after = Pt(AFTER)
    normal.paragraph_format.line_spacing = LINE

    for section in doc.sections:
        section.page_width = Twips(11906)
        section.page_height = Twips(16838)
        section.top_margin = Twips(1440)
        section.bottom_margin = Twips(1440)
        section.left_margin = Twips(1800)
        section.right_margin = Twips(1800)
        if DOC_GRID:                      # 字符网格：与政府文件一致
            sectPr = section._sectPr
            for g in sectPr.findall(qn('w:docGrid')):
                sectPr.remove(g)
            g = OxmlElement('w:docGrid')
            g.set(qn('w:type'), 'lines')
            g.set(qn('w:linePitch'), str(DOC_GRID))
            sectPr.append(g)

    if title:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(p, before=24, after=18, line=LINE)
        add_inline(p, title, size=TITLE_SZ, base_bold=True, allow_cite=False)
        try:
            doc.core_properties.title = title
            doc.core_properties.author = AUTHOR
            doc.core_properties.subject = "澳门AI发展现状与算力需求调研"
        except Exception:
            pass

    try:
        if CLASSIFICATION:
            hp = doc.sections[0].header.paragraphs[0]
            hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            hr = hp.add_run(CLASSIFICATION)
            set_run_font(hr, size=BODY_SZ)
            hr.bold = True
    except Exception:
        pass

    try:
        footer = doc.sections[0].footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = fp.add_run()
        set_run_font(run, size=9)
        fld1 = OxmlElement('w:fldChar'); fld1.set(qn('w:fldCharType'), 'begin')
        instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = ' PAGE '
        fld2 = OxmlElement('w:fldChar'); fld2.set(qn('w:fldCharType'), 'end')
        run._r.append(fld1); run._r.append(instr); run._r.append(fld2)
    except Exception:
        pass

    if toc:
        add_toc(doc, lines)

    bookmark_id = 100
    ordered_counter = 0
    prev_was_ordered = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            if not stripped:
                prev_was_ordered = False
            continue

        if re.match(r'^-{3,}$', stripped):
            i += 1
            continue

        # 图片：![alt](path) → 居中插入；路径相对 md 所在目录解析
        m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$', stripped)
        if m:
            ipath = m.group(2).strip()
            if not os.path.isabs(ipath):
                base = os.path.dirname(os.path.abspath(md_path))
                # 依次尝试：md 同目录 → 上一级（.parts/ 下的底稿引用 ../figures/）→ 当前目录
                for cand in (os.path.join(base, ipath),
                             os.path.join(base, '..', ipath),
                             os.path.abspath(ipath)):
                    if os.path.exists(cand):
                        ipath = cand
                        break
            if os.path.exists(ipath):
                doc.add_picture(ipath, width=Cm(IMG_WIDTH_CM))
                pic_p = doc.paragraphs[-1]
                pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_paragraph_spacing(pic_p, before=6, after=2, line=1.0)
            else:
                add_body(doc, '【缺图：%s】' % ipath, indent=False)
            i += 1
            continue

        # 题注：*…* 独占一行 → 居中、小一号、灰色
        m = re.match(r'^\*(?!\*)(.+?)\*$', stripped)
        if m:
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_paragraph_spacing(cp, before=0, after=10, line=1.15)
            add_inline(cp, m.group(1), size=BODY_SZ - 1.5)
            for r in cp.runs:
                r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
            i += 1
            continue

        if stripped.startswith('|'):
            rows, i = parse_table(lines, i)
            add_table(doc, rows)
            prev_was_ordered = False
            continue

        m = re.match(r'^(#{1,7})\s+(.*)$', stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level <= 2:
                add_heading(doc, text, 1)
            elif level == 3:
                add_heading(doc, text, 2)
            else:
                add_heading(doc, text, 3)
            prev_was_ordered = False
            i += 1
            continue

        # reference entry: R12. ...  -> bookmark _Ref12
        m = re.match(r'^R(\d+)\.\s+(.*)$', stripped)
        if m:
            num = m.group(1)
            p = doc.add_paragraph()
            set_paragraph_spacing(p, before=0, after=3, line=1.2)
            p.paragraph_format.left_indent = Pt(22)
            p.paragraph_format.first_line_indent = Pt(-22)
            add_bookmark(p, '_Ref%s' % num, bookmark_id)
            bookmark_id += 1
            r = p.add_run('[%s] ' % num)
            set_run_font(r, size=BODY_SZ - 0.5, bold=True)
            add_inline(p, m.group(2), size=BODY_SZ - 0.5, allow_cite=False)
            prev_was_ordered = False
            i += 1
            continue

        if stripped.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(lines[i].strip().lstrip('>').strip())
                i += 1
            add_quote(doc, ' '.join(x for x in buf if x))
            prev_was_ordered = False
            continue

        m = re.match(r'^(\s*)[-*+]\s+(.*)$', line)
        if m:
            indent = len(m.group(1))
            level = 1 if indent >= 2 else 0
            add_list_item(doc, '•', m.group(2).strip(), level=level)
            prev_was_ordered = False
            i += 1
            continue

        m = re.match(r'^(\s*)\d+[.)]\s+(.*)$', line)
        if m:
            indent = len(m.group(1))
            level = 1 if indent >= 2 else 0
            ordered_counter = ordered_counter + 1 if prev_was_ordered else 1
            add_list_item(doc, '%d.' % ordered_counter, m.group(2).strip(), level=level)
            prev_was_ordered = True
            i += 1
            continue

        add_body(doc, stripped)
        prev_was_ordered = False
        i += 1

    doc.save(out_path)
    print("saved:", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--title', default=None)
    ap.add_argument('--toc', action='store_true')
    ap.add_argument('--profile', default='research', choices=sorted(PROFILES),
                    help='版式档：research=研究版（简体/等线11pt）；'
                         'gov=政府呈报版（繁體/標楷體14pt/1.5倍行距/两端对齐）')
    ap.add_argument('--author', default=None)
    ap.add_argument('--classification', default=None,
                    help='页眉密级标识（如「秘密」）。留空则不加页眉——密级应由发文机关决定')
    args = ap.parse_args()
    apply_profile(args.profile)
    if args.author:
        globals()['AUTHOR'] = args.author
    if args.classification:
        _add_classification(args.classification)
    convert(args.input, args.output, args.title, args.toc)


if __name__ == '__main__':
    main()
