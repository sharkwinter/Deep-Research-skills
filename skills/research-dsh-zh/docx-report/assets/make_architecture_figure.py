#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把"分层架构"渲染成真正的图片（PNG），供 docx 内嵌。

为什么需要它
------------
Markdown 里用 ``` 围栏画 ASCII 框图（`┌─┐ │ └─┘`）在 Word 里**必然错位**：
中文字体不是等宽、东亚字符是双宽，右侧边框永远对不齐。
**架构图必须出图**，不能用字符拼。

做法
----
读一份 JSON 规格（`--spec`），用 Pillow 画"面板 + 箭头"式分层图：

    {"out":"figures/fig.png","width":2000,"panel_gap":26,
     "blocks":[
       {"kind":"panel","title":"第一層 …","subtitle":"…","color":"#1F497D",
        "items":["…","…"],"footer":"職能：…","wrap":26},
       {"kind":"arrow","label":"…"},
       {"kind":"note","label":"…"}
     ]}

* 中文字体默认取文泉驿正黑（`/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`），
  可用 `--font` 指定；**图内文字语体必须与文档一致**（繁體文档就用繁體）。
* 输出 PNG 尺寸按 A4 正文宽度（约 14.6cm）排版设计，插入时按 15.5cm 缩放即可。
* 依赖仅 Pillow（无需 matplotlib / graphviz）。

用法
----
    python3 make_architecture_figure.py --spec fig_6_1.json
    python3 make_architecture_figure.py --spec fig.json --out /tmp/x.png
"""
import argparse
import json
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit('缺少依赖：pip install Pillow')

DEFAULT_FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
WHITE = (255, 255, 255)
INK = (26, 32, 44)
GREY = (110, 118, 130)
LIGHT = (245, 247, 250)


def hx(s, default=(31, 73, 125)):
    s = (s or '').lstrip('#')
    if len(s) == 6:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    return default


def wrap(text, n):
    """按显示宽度折行：CJK 记 1，ASCII 记 0.5（近似等宽视觉宽度）。"""
    if n <= 0:
        return [text]
    lines, cur, w = [], '', 0.0
    for ch in text:
        cw = 1.0 if ord(ch) > 0x2000 else 0.55
        if w + cw > n and cur:
            lines.append(cur)
            cur, w = ch, cw
        else:
            cur += ch
            w += cw
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--font', default=DEFAULT_FONT)
    a = ap.parse_args()

    spec = json.load(open(a.spec, encoding='utf-8'))
    W = spec.get('width', 2000)
    pad = spec.get('pad', 34)
    gap = spec.get('panel_gap', 26)
    out = a.out or spec['out']

    f_title = ImageFont.truetype(a.font, spec.get('title_size', 42))
    f_sub = ImageFont.truetype(a.font, spec.get('sub_size', 30))
    f_item = ImageFont.truetype(a.font, spec.get('item_size', 31))
    f_foot = ImageFont.truetype(a.font, spec.get('foot_size', 29))
    f_arrow = ImageFont.truetype(a.font, spec.get('arrow_size', 32))

    blocks = spec['blocks']
    inner_w = W - 2 * pad
    # 逐块计算高度
    heights = []
    for b in blocks:
        k = b.get('kind', 'panel')
        if k == 'panel':
            # 高度按内容流"模拟"出来，避免固定留白导致页脚压住最后一条
            items = b.get('items', [])
            n = b.get('wrap', 30)
            need = 74 + 16
            if b.get('subtitle'):
                need += f_sub.size + 14
            need += sum(len(wrap(t, n)) * (f_item.size + 12) for t in items)
            if b.get('footer'):
                need += 16 + 2 + f_foot.size
            h = need + 22
        elif k == 'arrow':
            h = 76
        else:
            h = 60
        heights.append(h)
    H = 2 * pad + sum(heights) + gap * (len(blocks) - 1)

    img = Image.new('RGB', (W, H), WHITE)
    d = ImageDraw.Draw(img)
    y = pad

    def center_text(text, cy, font, fill):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, cy), text, font=font, fill=fill)

    for b, h in zip(blocks, heights):
        k = b.get('kind', 'panel')
        if k == 'arrow':
            lab = b.get('label', '')
            cy = y + 6
            center_text(lab, cy, f_arrow, hx(b.get('color'), INK))
            # 向下箭头
            ax = W / 2
            top = cy + f_arrow.size + 10
            d.line([(ax, top), (ax, y + h - 16)], fill=hx(b.get('color'), INK), width=5)
            d.polygon([(ax - 13, y + h - 20), (ax + 13, y + h - 20), (ax, y + h - 2)],
                      fill=hx(b.get('color'), INK))
            y += h + gap
            continue

        if k == 'note':
            center_text(b.get('label', ''), y + 12, f_foot, GREY)
            y += h + gap
            continue

        col = hx(b.get('color'))
        # 面板底
        d.rounded_rectangle([pad, y, W - pad, y + h], radius=14,
                            fill=LIGHT, outline=col, width=3)
        # 标题带
        d.rounded_rectangle([pad, y, W - pad, y + 74], radius=14, fill=col)
        d.rectangle([pad, y + 58, W - pad, y + 74], fill=col)
        tw = d.textlength(b.get('title', ''), font=f_title)
        d.text(((W - tw) / 2, y + 12), b.get('title', ''), font=f_title, fill=WHITE)
        cy = y + 74 + 16
        if b.get('subtitle'):
            center_text(b['subtitle'], cy, f_sub, col)
            cy += f_sub.size + 14
        # 条目：左侧色块 + 文本
        for t in b.get('items', []):
            for ln in wrap(t, b.get('wrap', 30)):
                d.rounded_rectangle([pad + 30, cy + 7, pad + 40, cy + 17], radius=3, fill=col)
                d.text((pad + 56, cy), ln, font=f_item, fill=INK)
                cy += f_item.size + 12
        if b.get('footer'):
            fy = y + h - (f_foot.size + 22)
            d.line([(pad + 30, fy - 10), (W - pad - 30, fy - 10)], fill=(215, 220, 228), width=2)
            center_text(b['footer'], fy, f_foot, col)
        # 侧标（如"主權邊界"）
        if b.get('side'):
            d.text((pad + 6, y + h - 30), b['side'], font=f_foot, fill=GREY)
        y += h + gap

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, 'PNG')
    print('已生成图片：%s  (%d×%d)' % (out, W, H))


if __name__ == '__main__':
    main()
