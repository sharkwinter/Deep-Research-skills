#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「章节头部关键数字带」用的卡片小图标（透明底 PNG）。

为什么不用 emoji 或字体符号：Word 不保证跨机字形覆盖，缺字会渲染成方框或彩色
emoji，与正式报告的排版不一致。用 Pillow 图元直接画并栅格化，任何机器上看到的
都是同一张位图（同 R1.2「架构图必须出图」的理由）。

用法：
    python3 .tools/make_card_icons.py [输出目录]     # 默认 figures/icons

产出 8 个图标：
    gauge  柱条   规模 / 需求合计
    layers 分层   口径拆分
    list   名册   样本基数
    target 靶心   集中度 / 头部占比
    chip   芯片   算力 / 训练负载
    arrows 双向   澳琴分配 / 跨境
    rack   机柜   装机 / 上架率
    bars2  双柱   对比（>90% vs <30%）
"""
import os
import sys

from PIL import Image, ImageDraw

SS = 4              # 超采样倍数
OUT = 200           # 最终边长（px）
PAD = 36            # 画布内边距（SS 坐标系）

# 语义词色（与正文角标蓝同族，印刷友好）
DEEP = (0x1F, 0x49, 0x7D)      # 存量 / 规模
GREEN = (0x2E, 0x6B, 0x3E)     # 需求 / 模型
OCHRE = (0x8A, 0x6A, 0x1F)     # 判断 / 对比


def _canvas():
    n = OUT * SS
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), n


def _r(v):
    """归一化坐标 → 像素坐标（含内边距）。"""
    n = OUT * SS
    span = n - 2 * PAD
    return PAD + v * span


def _rect(d, x0, y0, x1, y1, color, radius=0):
    box = [_r(x0), _r(y0), _r(x1), _r(y1)]
    if radius:
        d.rounded_rectangle(box, radius=int(radius * (OUT * SS - 2 * PAD)),
                            fill=color)
    else:
        d.rectangle(box, fill=color)


def gauge(d, c):
    """三根递升柱条。"""
    for i, h in enumerate((0.34, 0.52, 0.70)):
        x = 0.14 + i * 0.26
        _rect(d, x, 0.84 - h, x + 0.16, 0.84, c, radius=0.035)


def layers(d, c):
    """三片层叠。"""
    for i, y in enumerate((0.18, 0.42, 0.66)):
        x0 = 0.14 + i * 0.04
        _rect(d, x0, y, 0.86 - i * 0.04, y + 0.16, c, radius=0.04)


def list_(d, c):
    """三行「点 + 横线」的名册。"""
    r = 0.055
    for y in (0.22, 0.5, 0.78):
        d.ellipse([_r(0.14), _r(y - r), _r(0.14 + 2 * r), _r(y + r)], fill=c)
        _rect(d, 0.34, y - 0.045, 0.86, y + 0.045, c, radius=0.04)


def target(d, c):
    """同心圆靶心。"""
    for rad, w in ((0.36, 0.075), (0.22, 0.075)):
        d.ellipse([_r(0.5 - rad), _r(0.5 - rad), _r(0.5 + rad), _r(0.5 + rad)],
                  outline=c, width=int(w * (OUT * SS - 2 * PAD)))
    d.ellipse([_r(0.40), _r(0.40), _r(0.60), _r(0.60)], fill=c)


def chip(d, c):
    """芯片：外框 + 核心方块 + 四边引脚。"""
    w = int(0.075 * (OUT * SS - 2 * PAD))
    d.rounded_rectangle([_r(0.26), _r(0.26), _r(0.74), _r(0.74)],
                        radius=int(0.07 * (OUT * SS - 2 * PAD)), outline=c, width=w)
    _rect(d, 0.42, 0.42, 0.58, 0.58, c, radius=0.03)
    for i in range(3):
        t = 0.30 + i * 0.20
        _rect(d, t - 0.026, 0.13, t + 0.026, 0.28, c, radius=0.02)   # 上
        _rect(d, t - 0.026, 0.72, t + 0.026, 0.87, c, radius=0.02)   # 下
        _rect(d, 0.13, t - 0.026, 0.28, t + 0.026, c, radius=0.02)   # 左
        _rect(d, 0.72, t - 0.026, 0.87, t + 0.026, c, radius=0.02)   # 右


def arrows(d, c):
    """双向箭头。"""
    for y, direction in ((0.34, 1), (0.66, -1)):
        x_from, x_to = (0.12, 0.88) if direction > 0 else (0.88, 0.12)
        _rect(d, min(x_from, x_to), y - 0.05, max(x_from, x_to), y + 0.05, c)
        tip = x_to
        back = x_to - direction * 0.16
        d.polygon([(_r(tip), _r(y)), (_r(back), _r(y - 0.14)),
                   (_r(back), _r(y + 0.14))], fill=c)


def rack(d, c):
    """机柜：外框 + 槽位分隔 + 指示灯。"""
    w = int(0.065 * (OUT * SS - 2 * PAD))
    d.rounded_rectangle([_r(0.24), _r(0.10), _r(0.76), _r(0.90)],
                        radius=int(0.05 * (OUT * SS - 2 * PAD)), outline=c, width=w)
    for i in range(1, 4):
        y = 0.10 + i * 0.20
        _rect(d, 0.24, y - 0.014, 0.76, y + 0.014, c)
    for i in range(4):
        y = 0.20 + i * 0.20
        d.ellipse([_r(0.34), _r(y - 0.042), _r(0.43), _r(y + 0.042)], fill=c)
        _rect(d, 0.52, y - 0.022, 0.68, y + 0.022, c, radius=0.02)


def bars2(d, c):
    """一高一低双柱（对比）。"""
    _rect(d, 0.20, 0.14, 0.44, 0.84, c, radius=0.04)
    _rect(d, 0.56, 0.54, 0.80, 0.84, c, radius=0.04)


ICONS = {
    'gauge': (gauge, DEEP),
    'layers': (layers, DEEP),
    'list': (list_, DEEP),
    'target': (target, GREEN),
    'chip': (chip, GREEN),
    'arrows': (arrows, OCHRE),
    'rack': (rack, DEEP),
    'bars2': (bars2, OCHRE),
}


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else 'figures/icons'
    os.makedirs(outdir, exist_ok=True)
    for name, (fn, color) in ICONS.items():
        img, d, n = _canvas()
        fn(d, color)
        img = img.resize((OUT, OUT), Image.LANCZOS)
        path = os.path.join(outdir, '%s.png' % name)
        img.save(path)
        print('%-8s %-42s %5d B' % (name, path, os.path.getsize(path)))


if __name__ == '__main__':
    main()
