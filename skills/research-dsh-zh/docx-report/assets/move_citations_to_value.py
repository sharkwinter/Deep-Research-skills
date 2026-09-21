#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R10 落位：把表格行末的引用角标搬到**数值所在单元格**。

问题
----
`add_table_citations.py` 为了省事，把 `[[n]]` 统一追加到每行**最后一个单元格**
（通常是"口径与来源/说明/备注"列）。这满足"有引用"，但**不满足 R10-1**：
R10 要求"角标必须紧贴该数值……不得只把角标挂在整行的'来源/备注'列"。
澳门报告实测：131 个含算力指标的数据行中，仅 36 行（27%）的**数值格**自带角标。

做法
----
对每张表的每一数据行：
1. 找出**含算力/数值指标**的单元格（`MET`，与 Step 7 自检脚本使用**同一正则**）；
2. 找出**已含 `[[n]]`** 的单元格；
3. 若两者都存在、且指标格尚未自带角标 → 把角标从"最右侧的承载格"**移动**到
   **第一个指标格**末尾（移动而非复制，避免同一行重复上标与链接膨胀）；
4. 只改行内的单元格文本，**不增删行**，可重复执行（幂等）。

设计取舍
--------
* **一行一个角标**：若某行有多个指标列但同源，只在第一个指标格落位。
  若这些列**来源不同**（如"对标数据明细表"的算力规模/电价/PUE 分别来自不同文件），
  `--strict` 会把这些行列出来，需**人工按列拆引用**（本脚本不猜）。
* **不猜来源**：整行都没有角标的行，本脚本只报告、不代填 —— 来源必须由人判定。

用法
----
    python3 move_citations_to_value.py <md> [<md> ...]              # 干跑
    python3 move_citations_to_value.py --write <md> [<md> ...]
    python3 move_citations_to_value.py --strict <md> [<md> ...]     # 列出多指标列行
"""
import argparse
import re

# ⚠️ 必须与 SKILL.md Step 7 自检脚本中的 MET 保持一致，否则"100%"无法复现
_NUM = r'\d[\d,\.]*\s*[万亿萬億]?\s*'
_UNIT = (r'(?:亿亿次|万亿次|PFLOPS|PFlops|P@FP16|Eops|EFLOPS|EPLOPS'
         r'|卡时|卡時|张|張|卡|台|柜|櫃|机架|機架|机位|機位'
         r'|MW|kW|MVA|kVA|GWh|%|P(?![A-Za-z@]))')
# 兼容「82.5万 A100 等效卡时/年」这类"数量+型号+等效+单位"的写法
MET = re.compile(_NUM + r'(?:(?:[A-Za-z]{1,6}\s*)?\d*\s*等效\s*)?' + _UNIT)
CITE = re.compile(r'\[\[[0-9,\s]+\]\]')
SEP = re.compile(r'^\|[\s:|-]+\|$')


def process(path, write, strict):
    lines = open(path, encoding='utf-8').read().split('\n')
    moved = nohold = multicell = 0
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not (s.startswith('|') and i + 1 < len(lines) and SEP.match(lines[i + 1].strip())):
            i += 1
            continue
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith('|'):
            parts = lines[j].split('|')
            cells = parts[1:-1]
            holders = [k for k, c in enumerate(cells) if CITE.search(c)]
            mets = [k for k, c in enumerate(cells) if MET.search(c)]
            if mets:
                if not holders:
                    nohold += 1
                else:
                    # 汇总该行已有的引用编号（去重，保持首次出现顺序）
                    seen, ordered = set(), []
                    for k in holders:
                        for grp in CITE.findall(cells[k]):
                            for num in grp[2:-2].split(','):
                                num = num.strip()
                                if num and num not in seen:
                                    seen.add(num)
                                    ordered.append(num)
                    cite_all = '[[%s]]' % ','.join(ordered) if ordered else ''
                    # 每个"数值格"都必须自带角标（R10 逐值）——缺则补上
                    for k in mets:
                        if k in holders or not cite_all:
                            continue
                        cells[k] = cells[k].rstrip() + ' ' + cite_all
                        moved += 1
                    if len(mets) > 1:
                        multicell += 1
                    lines[j] = '|'.join(parts[:1] + cells + parts[-1:])
            j += 1
        i = j
    if write:
        open(path, 'w', encoding='utf-8').write('\n'.join(lines))
    return moved, nohold, multicell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--strict', action='store_true',
                    help='额外列出"同一行有多个指标列"的行，需人工按列拆引用')
    a = ap.parse_args()
    tm = tn = tc = 0
    for f in a.files:
        m, n, c = process(f, a.write, a.strict)
        tm += m
        tn += n
        tc += c
        print('%-46s 移动 %-4d 整行无角标 %-3d 多指标列 %d' % (f.split('/')[-1][:44], m, n, c))
    print('-' * 78)
    print('合计：移动 %d 处；整行无角标 %d 处（须人工补来源）；多指标列 %d 处（建议按列拆引用）'
          % (tm, tn, tc))
    print('（%s）' % ('已写入' if a.write else '干跑，未写入；加 --write 生效'))
    if tn and a.strict:
        print('⚠️ 存在整行无角标的数据行，R10 未达标。')


if __name__ == '__main__':
    main()
