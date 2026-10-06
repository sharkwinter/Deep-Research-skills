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
  3. **附录单倍行距**（R15）：自 `附錄A`／`附录A` 起，至文末，**正文一律单倍行距**
     （表格单元格、列表、引文块、参考文献条目同）；**标题（章/节/子标题）不改行距**。
     gov 档另需关闭这些段落的 `w:snapToGrid`——否则 `w:docGrid linePitch=360`
     会把单倍行距重新吸附回网格行高，"单倍行距"在 Word 里看不出变化。

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
        CARD_NUM_SZ=13.5, CARD_LABEL_SZ=9.5, CARD_TITLE_SZ=10, CARD_FOOT_SZ=8.5,
    ),
    "gov": dict(
        CN_FONT="標楷體", EN_FONT="Times New Roman",
        BODY_SZ=14, H1_SZ=14, H2_SZ=14, H3_SZ=14, TITLE_SZ=14, TOC_SZ=14,
        LINE=1.5, BEFORE=6, AFTER=0, JUSTIFY=True, FIRST_INDENT_PT=24,
        TABLE_SZ=11, TOC_INDENT={1: 0, 2: 24, 3: 48},
        TOC_TEXT_SZ={1: 14, 2: 14, 3: 14}, DOC_GRID=360, IMG_WIDTH_CM=15.5,
        # gov 档「全篇同字号」是硬约束（参照件 sz=28 唯一）：卡片数字**不放大**，
        # 靠加粗＋深蓝＋图标强调；标签沿用表格降级字号，不引入新字号类。
        CARD_NUM_SZ=14, CARD_LABEL_SZ=11, CARD_TITLE_SZ=11, CARD_FOOT_SZ=9,
    ),
}
PROFILE = "research"
# 附录区标记：主循环遇到 `附錄A`／`附录A` 起置 True，其后正文单倍行距（R15）
IN_APPENDIX = False


def apply_profile(name):
    """把选定版式档的取值写入模块级常量（其余函数直接读这些常量）。"""
    global PROFILE, CN_FONT, EN_FONT, BODY_SZ, H1_SZ, H2_SZ, H3_SZ, TITLE_SZ
    global LINE, BEFORE, AFTER, JUSTIFY, FIRST_INDENT_PT, TABLE_SZ
    global TOC_SZ, TOC_INDENT, TOC_TEXT_SZ, DOC_GRID, IMG_WIDTH_CM
    global CARD_NUM_SZ, CARD_LABEL_SZ, CARD_TITLE_SZ, CARD_FOOT_SZ
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
    CARD_NUM_SZ, CARD_LABEL_SZ = c["CARD_NUM_SZ"], c["CARD_LABEL_SZ"]
    CARD_TITLE_SZ, CARD_FOOT_SZ = c["CARD_TITLE_SZ"], c["CARD_FOOT_SZ"]


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


def set_snap_to_grid(p, on):
    """打开/关闭段落"与网格对齐"。

    gov 档页面带 `w:docGrid w:type="lines" w:linePitch="360"`；只要 snapToGrid 为默认的
    true，Word 会把每个文本行吸附到网格行高（360 twips），此时把行距设成单倍仍是 360，
    与 1.5 倍**视觉上无差别**。要让"单倍行距"真正生效，必须显式写 `w:snapToGrid w:val="0"`。
    """
    pPr = p._element.get_or_add_pPr()
    for old in pPr.findall(qn('w:snapToGrid')):
        pPr.remove(old)
    el = OxmlElement('w:snapToGrid')
    el.set(qn('w:val'), '1' if on else '0')
    # 必须插在 w:spacing 之前（OOXML pPr 子元素有固定次序，乱序会被 Word 判为非法）
    pPr.insert_element_before(
        el, 'w:spacing', 'w:ind', 'w:contextualSpacing', 'w:mirrorIndents',
        'w:suppressOverlap', 'w:jc', 'w:textDirection', 'w:textAlignment',
        'w:textboxTightWrap', 'w:outlineLvl', 'w:divId', 'w:cnfStyle',
        'w:rPr', 'w:sectPr', 'w:pPrChange')
    return p


def appendix_line(p, line):
    """附录（自 `附錄A` 起）内的正文段落返回单倍行距，并关闭网格吸附。

    **标题不调用本函数**——标题（章/节/子标题）保持版式档原行距，这是用户明确的例外。
    """
    if not IN_APPENDIX:
        return line
    set_snap_to_grid(p, False)
    return 1.0


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
    # rPr 子元素次序固定：rFonts → color → sz → vertAlign。
    # （曾把 vertAlign 排在 color 之前，全篇 2,790 处 OOXML 非法；Word 容忍但不应留下）
    c = OxmlElement('w:color'); c.set(qn('w:val'), '%02X%02X%02X' % (color[0], color[1], color[2]))
    rPr.append(c)
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), str(int(size * 2))); rPr.append(sz)
    if superscript:
        va = OxmlElement('w:vertAlign'); va.set(qn('w:val'), 'superscript'); rPr.append(va)
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
    set_paragraph_spacing(p, before=BEFORE, after=AFTER if after is None else after,
                          line=appendix_line(p, LINE))
    if JUSTIFY:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent:
        p.paragraph_format.first_line_indent = Pt(FIRST_INDENT_PT)
    add_inline(p, text, size=size)
    return p


def add_list_item(doc, marker, text, level=0, size=None, hang=13):
    """以字面量 marker（如 '1.' / '•'）渲染列表项，普通段落，无自动编号。"""
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=0, after=3, line=appendix_line(p, 1.25))
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
            set_paragraph_spacing(p, before=1, after=1, line=appendix_line(p, 1.05))
            txt = row[j] if j < len(row) else ''
            add_inline(p, txt.strip(), size=TABLE_SZ, base_bold=(i == 0),
                       allow_cite=True, cite_size=TABLE_SZ - 1.5)
            if i == 0:
                shade_cell(cell, "DCE6F1")
    sp = doc.add_paragraph()
    set_paragraph_spacing(sp, before=0, after=4, line=appendix_line(sp, 1.0))
    for r in sp.runs:
        r.font.size = Pt(2)
    return table


# --------------------------------------------------------------------------
# 章节头部「关键数字带」（R21）
#   一张原生表格 = 标题行（合并）+ N 张卡片（2 列）+ 口径脚注行（合并）。
#   · 数字必须是**真文本**，角标才能挂上并保持可点击（R3 / R10-1）；
#   · 图标是 Pillow 栅格化的透明 PNG，内联在卡片首行——不用 emoji 或字体符号，
#     因为 Word 的跨机字形回退不可控（同 R1.2「架构图必须出图」的理由）；
#   · 首行是标题行，因此 R10 校验器的 `rows[1:]`（跳过表头）语义刚好只跳过标题栏，
#     第一行卡片不会被漏检。
# --------------------------------------------------------------------------
CARD_FILL = "F4F7FB"           # 卡片底纹
CARD_TITLE_FILL = "DCE6F1"     # 标题行底纹（与其他表头一致）
CARD_BORDER = "BFBFBF"
CARD_ICON_CM = 0.42
CARD_COL_CM = 7.3              # 正文宽 14.65cm ÷ 2（列宽固定，避免 Word 自动分配）
CARD_NUM_COLOR = RGBColor(0x1F, 0x49, 0x7D)
CARD_LABEL_COLOR = RGBColor(0x40, 0x40, 0x40)
CARD_TITLE_COLOR = RGBColor(0x1F, 0x49, 0x7D)
# 数字色调（与图标语义词色一致）：deep=存量/规模，green=需求/模型，ochre=判断/对比
CARD_TONES = {
    'deep': RGBColor(0x1F, 0x49, 0x7D),
    'green': RGBColor(0x2E, 0x6B, 0x3E),
    'ochre': RGBColor(0x8A, 0x6A, 0x1F),
}
CARD_TONE_RGB = {
    'deep': (0x1F, 0x49, 0x7D),
    'green': (0x2E, 0x6B, 0x3E),
    'ochre': (0x8A, 0x6A, 0x1F),
}
# mini 图表：高度(cm) 与数字抬升量(半磅)。图形较高时把同一行的数字抬到视觉中线。
# 用 w:position 抬升而不是给图表单独占一段——段落一多，卡片带就占掉半页。
CARD_CHART = {
    'donut': dict(h=1.02, pos=14),   # 构成 / 占比
    'hbar':  dict(h=0.34, pos=0),    # 单一比例条
    'col':   dict(h=0.80, pos=9),    # 分布 / 对比柱
}
# 渲染器版本：**必须参与缓存键**。否则改了画法之后，同名 spec 仍会命中旧 PNG，
# 重建出来的文档里还是旧图——这是"图旧数新"的另一种形态。
CHART_VER = 'v3'


def resolve_img(path, md_path):
    """把底稿里的相对图片路径解析为真实路径（md 同目录 → 上一级 → 绝对）。"""
    if os.path.isabs(path):
        return path
    base = os.path.dirname(os.path.abspath(md_path))
    for cand in (os.path.join(base, path),
                 os.path.join(base, '..', path),
                 os.path.abspath(path)):
        if os.path.exists(cand):
            return cand
    return path


def set_cell_borders(cell, color=CARD_BORDER, sz=4):
    """给单元格加细边框（tcBorders 必须排在 w:shd 之前，否则 OOXML 非法）。"""
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:tcBorders')):
        tcPr.remove(old)
    b = OxmlElement('w:tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        e = OxmlElement('w:%s' % side)
        e.set(qn('w:val'), 'single')
        e.set(qn('w:sz'), str(sz))
        e.set(qn('w:space'), '0')
        e.set(qn('w:color'), color)
        b.append(e)
    tcPr.insert_element_before(b, 'w:shd', 'w:noWrap', 'w:tcMar',
                               'w:textDirection', 'w:tcFitText', 'w:vAlign',
                               'w:hideMark')


def set_cell_valign(cell, val='center'):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:vAlign')):
        tcPr.remove(old)
    e = OxmlElement('w:vAlign')
    e.set(qn('w:val'), val)
    tcPr.append(e)


def set_run_position(run, half_points):
    """把 run 抬升/下沉若干半磅（w:position）。rPr 子元素次序固定，必须插在 w:sz 之前。"""
    rPr = run._r.get_or_add_rPr()
    for old in rPr.findall(qn('w:position')):
        rPr.remove(old)
    el = OxmlElement('w:position')
    el.set(qn('w:val'), str(int(half_points)))
    rPr.insert_element_before(
        el, 'w:sz', 'w:szCs', 'w:highlight', 'w:u', 'w:effect', 'w:bdr', 'w:shd',
        'w:fitText', 'w:vertAlign', 'w:rtl', 'w:cs', 'w:em', 'w:lang',
        'w:eastAsianLayout', 'w:specVanish', 'w:oMath')
    return run


def _tint(rgb, f):
    return tuple(int(round(255 - (255 - c) * f)) for c in rgb)


def _chart_path(spec, tone):
    """渲染 mini 图表 PNG（按 spec+tone 缓存）。

    spec 形如 `donut:47/25/17/11`、`hbar:22.5/77.5`、`col:389596,209518,137034`。
    **数据写在底稿里**：问卷口径一变（R20），图会随数字一起重算，不会出现"图旧数新"。
    """
    import hashlib
    import tempfile
    from PIL import Image, ImageDraw

    tag = hashlib.md5(('%s|%s|%s' % (CHART_VER, spec, tone)).encode('utf-8')).hexdigest()[:12]
    cache = os.path.join(tempfile.gettempdir(), 'md2docx_charts_%s' % CHART_VER)
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, 'c_%s.png' % tag)
    if os.path.exists(out):
        return out

    kind, _, raw = spec.partition(':')
    vals = [float(x) for x in re.split(r'[/,]', raw) if x.strip()] or [1.0]
    base = CARD_TONE_RGB.get(tone, CARD_TONE_RGB['deep'])
    SS = 4
    W, H = {'hbar': (512, 80), 'col': (320, 220)}.get(kind, (256, 256))
    img = Image.new('RGBA', (W * SS, H * SS), (255, 255, 255, 0))
    dr = ImageDraw.Draw(img)

    if kind == 'hbar':
        # 多段比例条：第 1 段用语义主色（需要读者注意的那一段），其余段用中性色，
        # 这样「训练 117 P ／ 其余 404 P」读起来是两段构成，而不是「某比例填了多长」。
        # 先铺满中性轨道再叠各段，避免圆角在段间接缝处露白。
        tot = sum(vals) or 1.0
        r = int(H * SS * 0.34)
        NEUTRAL = [(0xB9, 0xC6, 0xD4), (0xD9, 0xD9, 0xD9), (0xC9, 0xC9, 0xC9)]
        dr.rounded_rectangle([0, 0, W * SS - 1, H * SS - 1], radius=r,
                             fill=NEUTRAL[0])
        x = 0
        for i, v in enumerate(vals):
            w = int(round(W * SS * v / tot)) if tot else 0
            if v > 0:
                w = max(w, int(H * SS * 0.9))
            col = base if i == 0 else NEUTRAL[(i - 1) % len(NEUTRAL)]
            if w:
                dr.rounded_rectangle([x, 0, min(x + w, W * SS - 1), H * SS - 1],
                                     radius=r, fill=col)
            x += w
    elif kind == 'col':
        mx = max(vals) or 1.0
        n = len(vals)
        gap = W * SS * 0.07
        bw = (W * SS - gap * (n + 1)) / n
        for i, v in enumerate(vals):
            hh = (H * SS - 8) * (v / mx)
            x0 = gap + i * (bw + gap)
            f = 1.0 if i == 0 else max(0.30, 0.74 - 0.13 * i)
            dr.rounded_rectangle([x0, H * SS - hh, x0 + bw, H * SS - 2],
                                 radius=int(bw * 0.20), fill=_tint(base, f))
    else:                                   # donut
        tot = sum(vals) or 1.0
        pad = 0.04
        box = [W * SS * pad, H * SS * pad, W * SS * (1 - pad), H * SS * (1 - pad)]
        ang = -90.0
        for i, v in enumerate(vals):
            ext = 360.0 * v / tot
            f = 1.0 if i == 0 else max(0.26, 0.68 - 0.15 * i)
            dr.pieslice(box, ang, ang + ext, fill=_tint(base, f))
            ang += ext
        m = 0.32                            # 挖空中心 → 环
        dr.ellipse([W * SS * m, H * SS * m, W * SS * (1 - m), H * SS * (1 - m)],
                   fill=(255, 255, 255, 0))

    img = img.resize((W, H), Image.LANCZOS)
    img.save(out)
    return out


def add_cards(doc, spec, md_path):
    """渲染 `:::cards` 区块。spec 见 parse_cards()。"""
    cards = spec['cards']
    ncol = 2
    nrow = max(1, (len(cards) + ncol - 1) // ncol)
    table = doc.add_table(rows=nrow + 2, cols=ncol)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # 固定栏宽：否则 Word 会按内容自动分配，两列宽度不相等、卡片错位
    table.autofit = False
    CW = CARD_COL_CM

    # ---- 标题行（跨列合并）：本节关键数字 + 口径/导出时点 ----
    head = table.cell(0, 0).merge(table.cell(0, ncol - 1))
    head.text = ''
    hp = head.paragraphs[0]
    set_paragraph_spacing(hp, before=3, after=3, line=1.0)
    set_snap_to_grid(hp, False)
    add_inline(hp, spec.get('title') or '本节关键数字', size=CARD_TITLE_SZ,
               base_bold=True, allow_cite=False)
    for r in hp.runs:
        r.font.color.rgb = CARD_TITLE_COLOR
    if spec.get('subtitle'):
        r = hp.add_run('　　' + spec['subtitle'])
        set_run_font(r, size=CARD_LABEL_SZ, color=CARD_LABEL_COLOR)
        r.font.bold = False
    shade_cell(head, CARD_TITLE_FILL)
    set_cell_borders(head, sz=4)
    head.width = Cm(CW * ncol)

    # ---- 卡片行 ----
    for k, (icon, num, label, cite, tone) in enumerate(cards):
        cell = table.cell(1 + k // ncol, k % ncol)
        cell.text = ''

        p1 = cell.paragraphs[0]
        set_paragraph_spacing(p1, before=4, after=1, line=1.0)
        set_snap_to_grid(p1, False)
        isz, pos = CARD_ICON_CM, 0
        ipath = None
        if ':' in icon and icon.split(':', 1)[0] in CARD_CHART:
            kind = icon.split(':', 1)[0]
            ipath = _chart_path(icon, tone or 'deep')       # mini 图表
            isz, pos = CARD_CHART[kind]['h'], CARD_CHART[kind]['pos']
        else:
            ipath = resolve_img('figures/icons/%s.png' % icon, md_path)
        if os.path.exists(ipath):
            run = p1.add_run()
            run.add_picture(ipath, height=Cm(isz))
            p1.add_run('　')
        else:
            p1.add_run('【缺图：%s】' % icon)
        head_n = len(p1.runs)                  # 图形之后的 run 才需要抬升
        add_inline(p1, num, size=CARD_NUM_SZ, base_bold=True, allow_cite=False)
        ncolor = CARD_TONES.get((tone or 'deep').lower(), CARD_NUM_COLOR)
        for r in p1.runs[head_n:]:             # 数字统一着色，较高的图把数字抬到中线
            r.font.color.rgb = ncolor
            if pos:
                set_run_position(r, pos)
        if cite:                               # 角标紧贴数值，落在数值所在格内（R10-1）
            add_citation(p1, cite, size=CARD_LABEL_SZ - 1)

        p2 = cell.add_paragraph()
        set_paragraph_spacing(p2, before=0, after=4, line=1.05)
        set_snap_to_grid(p2, False)
        add_inline(p2, label, size=CARD_LABEL_SZ, allow_cite=False)
        for r in p2.runs:
            r.font.color.rgb = CARD_LABEL_COLOR

        shade_cell(cell, CARD_FILL)
        set_cell_borders(cell)
        set_cell_valign(cell)
        cell.width = Cm(CW)

    # ---- 口径脚注行（跨列合并） ----
    foot = table.cell(nrow + 1, 0).merge(table.cell(nrow + 1, ncol - 1))
    foot.text = ''
    fp = foot.paragraphs[0]
    set_paragraph_spacing(fp, before=1, after=2, line=1.0)
    set_snap_to_grid(fp, False)
    add_inline(fp, spec.get('foot') or '', size=CARD_FOOT_SZ, allow_cite=True)
    for r in fp.runs:
        r.font.color.rgb = CARD_LABEL_COLOR
    set_cell_borders(foot, color="FFFFFF")
    foot.width = Cm(CW * ncol)

    sp = doc.add_paragraph()
    set_paragraph_spacing(sp, before=0, after=4, line=appendix_line(sp, 1.0))
    for r in sp.runs:
        r.font.size = Pt(2)
    return table


def parse_cards(lines, i):
    """解析 :::cards 围栏。

    首行  `:::cards 标题 | 副标题`
    卡片  `图标名|数字|标签|角标|色调`   （角标形如 [[74,77]]，可留空）
    脚注  `foot|口径说明…`
    结束  `:::`
    """
    spec = {'title': None, 'subtitle': None, 'cards': [], 'foot': None}
    first = lines[i].strip()[3:].strip()          # 去掉 ':::cards'
    if first.lower().startswith('cards'):
        first = first[5:].strip()
    if first:
        parts = [x.strip() for x in first.split('|', 1)]
        spec['title'] = parts[0] or None
        if len(parts) > 1:
            spec['subtitle'] = parts[1] or None
    i += 1
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith(':::'):
            i += 1
            break
        if not s:
            i += 1
            continue
        if s.startswith('foot|'):
            spec['foot'] = s[5:].strip()
            i += 1
            continue
        f = [x.strip() for x in s.split('|')]
        while len(f) < 5:
            f.append('')
        icon, num, label, cite, tone = f[:5]
        nums = re.findall(r'\d+', cite)
        spec['cards'].append((icon, num, label, nums, tone))
        i += 1
    return spec, i


def add_quote(doc, text):
    p = doc.add_paragraph()
    set_paragraph_spacing(p, before=4, after=6, line=appendix_line(p, 1.25))
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
    global IN_APPENDIX
    IN_APPENDIX = False
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
            ipath = resolve_img(m.group(2).strip(), md_path)
            if os.path.exists(ipath):
                doc.add_picture(ipath, width=Cm(IMG_WIDTH_CM))
                pic_p = doc.paragraphs[-1]
                pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_paragraph_spacing(pic_p, before=6, after=2,
                                      line=appendix_line(pic_p, 1.0))
            else:
                add_body(doc, '【缺图：%s】' % ipath, indent=False)
            i += 1
            continue

        # 题注：*…* 独占一行 → 居中、小一号、灰色
        m = re.match(r'^\*(?!\*)(.+?)\*$', stripped)
        if m:
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_paragraph_spacing(cp, before=0, after=10, line=appendix_line(cp, 1.15))
            add_inline(cp, m.group(1), size=BODY_SZ - 1.5)
            for r in cp.runs:
                r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
            i += 1
            continue

        # 章节头部「关键数字带」（R21）
        if re.match(r'^:::cards\b', stripped):
            spec, i = parse_cards(lines, i)
            add_cards(doc, spec, md_path)
            prev_was_ordered = False
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
            if re.match(r'^附\s*[錄录]\s*[A-Z]', text):
                IN_APPENDIX = True      # 自「附錄A」起：正文单倍行距（R15）
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
            set_paragraph_spacing(p, before=0, after=3, line=appendix_line(p, 1.2))
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
