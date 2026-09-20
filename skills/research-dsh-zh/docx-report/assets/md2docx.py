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
import re
import argparse

from docx import Document
from docx.shared import Pt, Twips, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CN_FONT = "等线"
EN_FONT = "Arial"
BODY_SZ = 11
H1_SZ = 16
H2_SZ = 12.5
H3_SZ = 11.5
TITLE_SZ = 22
CITE_COLOR = RGBColor(0x1F, 0x49, 0x7D)


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


def add_bookmark(paragraph, name, bid):
    start = OxmlElement('w:bookmarkStart')
    start.set(qn('w:id'), str(bid))
    start.set(qn('w:name'), name)
    end = OxmlElement('w:bookmarkEnd')
    end.set(qn('w:id'), str(bid))
    paragraph._element.insert(0, start)
    paragraph._element.append(end)


def add_internal_link(paragraph, anchor, text, size=BODY_SZ, superscript=True, color=CITE_COLOR):
    """插入指向书签 anchor 的内部超链接。"""
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


def add_superscript(paragraph, text, size=BODY_SZ, color=CITE_COLOR):
    """插入普通（非链接）上标文本，用于引用的括号与逗号。"""
    r = paragraph.add_run(text)
    set_run_font(r, size=size)
    r.font.superscript = True
    if color is not None:
        r.font.color.rgb = color
    return r


def add_citation(paragraph, nums, size=BODY_SZ):
    """把 [[1,2,5]] 渲染为 [1,2,5]，其中**每个编号各自是可点击的内部超链接**。"""
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
INLINE_RE = re.compile(r'(\*\*.+?\*\*|`[^`]+`|\[\[[0-9,\s]+\]\])')


def add_inline(paragraph, text, size=BODY_SZ, base_bold=False, allow_cite=True,
               cite_size=None):
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
def add_body(doc, text, indent=True, size=BODY_SZ, after=6):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=0, after=after, line=1.25)
    if indent:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    add_inline(p, text, size=size)
    return p


def add_list_item(doc, marker, text, level=0, size=BODY_SZ, hang=13):
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
    if level == 1:
        set_paragraph_spacing(p, before=16, after=8, line=1.2)
        add_inline(p, text, size=H1_SZ, base_bold=True, allow_cite=False)
        set_outline_level(p, 1)
    elif level == 2:
        set_paragraph_spacing(p, before=14, after=6, line=1.2)
        add_inline(p, text, size=H2_SZ, base_bold=True, allow_cite=False)
        set_outline_level(p, 2)
    else:
        set_paragraph_spacing(p, before=10, after=4, line=1.2)
        add_inline(p, text, size=H3_SZ, base_bold=True, allow_cite=False)
        set_outline_level(p, 3)
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
            add_inline(p, txt.strip(), size=9.5, base_bold=(i == 0),
                       allow_cite=True, cite_size=8.0)
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
    add_inline(p, '目　录', size=16, base_bold=True, allow_cite=False)
    _indent = {1: 0, 2: 18, 3: 36}
    _size = {1: 11, 2: 10, 3: 9.5}
    for level, txt in entries:
        q = doc.add_paragraph()
        set_paragraph_spacing(q, before=0, after=1, line=1.15)
        q.paragraph_format.left_indent = Pt(_indent.get(level, 36))
        add_inline(q, txt, size=_size.get(level, 9.5),
                   base_bold=(level == 1), allow_cite=False)
    br = doc.add_paragraph()
    run = br.add_run()
    run.add_break(WD_BREAK.PAGE)


def convert(md_path, out_path, title=None, toc=False):
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')

    doc = Document()

    normal = doc.styles['Normal']
    normal.font.name = EN_FONT
    normal.font.size = Pt(BODY_SZ)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), CN_FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for section in doc.sections:
        section.page_width = Twips(11905)
        section.page_height = Twips(16840)
        section.top_margin = Twips(1440)
        section.bottom_margin = Twips(1440)
        section.left_margin = Twips(1800)
        section.right_margin = Twips(1800)

    if title:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(p, before=24, after=18, line=1.2)
        add_inline(p, title, size=TITLE_SZ, base_bold=True, allow_cite=False)
        try:
            doc.core_properties.title = title
            doc.core_properties.author = "澳门AI产业与算力需求联合调研组"
            doc.core_properties.subject = "澳门AI发展现状与算力需求调研"
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
    args = ap.parse_args()
    convert(args.input, args.output, args.title, args.toc)


if __name__ == '__main__':
    main()
