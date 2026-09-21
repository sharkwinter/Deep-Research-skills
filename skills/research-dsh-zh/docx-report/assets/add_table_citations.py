#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为报告中的表格批量追加 `[[n]]` 引用角标（追加到该行最后一个单元格末尾）。

为什么需要它
------------
正文角标可以靠"章节默认集 + 关键词触发"自动铺，但**表格每一行的数据源各不相同**
（同一张表里 A 行来自政府公报、B 行来自企业年报），必须逐表逐行判定。
本脚本把这种"判定结果"固化成规则表，一次判定、批量落盘、可重复执行。

用法
----
    python3 add_table_citations.py            # 干跑：只校验规则是否全部命中，不写文件
    python3 add_table_citations.py --write    # 实际写入

规则格式
--------
    RULES = {
        (文件路径, 表头所在行号): (表头校验子串, 各行引用),
    }
  * 表头行号基于**原始文件**（写入只在行尾 `|` 前插字符，不增删行，故行号稳定）；
  * 各行引用为 list（长度须等于数据行数），或单个字符串（该表所有数据行相同）；
  * 引用写 `[[12]]` / `[[7,20,42]]`（转换器会逐编号建内部超链接，逗号与方括号为普通上标）。

落点约定与工序（两步，缺一不可）
--------------------------------
**第一步（本脚本）**：把 `[[n]]` 挂到该行最后一个单元格（一般就是"口径与来源/说明/依据/备注"列），
先保证"有引用"。
**第二步（`move_citations_to_value.py`）**：把角标**搬到每个数值所在单元格内**——这是 R10-1 的硬要求，
"只挂在行末来源列"不算达标（澳门报告首次实测仅 34% 的数值格自带角标）。
按列分源的表（同一行不同列来自不同文件，如对标数据明细表的算力规模/电价/PUE），第二步之后还需
**人工按列拆引用**，脚本不猜来源。

幂等性
------
已含 `[[` 的行自动跳过，可安全重复执行；`--write` 前后行数不变。
"""
import re
import sys

# ---------------------------------------------------------------------------
# 规则表：项目实施时按实际文件填写
# ---------------------------------------------------------------------------
RULES = {
    # ('报告.md', 72): ('| 维度 | 关键指标 | 数值 | 口径与来源 |', [
    #     '[[75,83]]', '[[75]]', '[[74,76]]',
    # ]),
    # ('报告.md', 111): ('| 时点 | 关键指标 |', '[[1]]'),      # 单串=全表同源
}


def process(path, applied):
    try:
        text = open(path, encoding='utf-8').read()
    except FileNotFoundError:
        return None
    lines = text.split('\n')
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith('|') and i + 1 < len(lines) and \
                re.match(r'^\|[\s:|-]+\|$', lines[i + 1].strip()):
            out.append(line)
            out.append(lines[i + 1])
            j = i + 2
            rows = []
            while j < len(lines) and lines[j].strip().startswith('|'):
                rows.append(lines[j])
                j += 1
            key = (path, i + 1)
            if key in RULES:
                exp, refs = RULES[key]
                assert exp in s, '%s L%d 表头不匹配: %r' % (path, i + 1, s)
                if isinstance(refs, str):
                    refs = [refs] * len(rows)
                assert len(refs) == len(rows), \
                    '%s L%d 数据行数不符: 规则 %d 行 / 实际 %d 行' % (
                        path, i + 1, len(refs), len(rows))
                fixed = []
                for r, ref in zip(rows, refs):
                    if '[[' in r or not ref:
                        fixed.append(r)          # 幂等：已挂角标则跳过
                        continue
                    body = r.rstrip()
                    assert body.endswith('|'), r
                    fixed.append(body[:-1].rstrip() + ' ' + ref + ' |')
                rows = fixed
                applied.append((path, i + 1, len(rows)))
            i = j
            out.extend(rows)
            continue
        out.append(line)
        i += 1
    return '\n'.join(out)


def main():
    write = '--write' in sys.argv
    files = sorted({k[0] for k in RULES}) or []
    results, total = {}, 0
    for f in files:
        acc = []
        results[f] = (process(f, acc), acc)
        total += len(acc)
    print('=' * 72)
    for f, (_, acc) in results.items():
        print('%s: %d 张表已加引用' % (f, len(acc)))
    print('合计 %d 张表 / 规则 %d 条' % (total, len(RULES)))
    assert total == len(RULES), '有规则未命中——表头行号可能因编辑而位移，请先核对！'
    if write:
        for f, (res, _) in results.items():
            if res is not None:
                open(f, 'w', encoding='utf-8').write(res)
        print('已写入。')
    else:
        print('（干跑，未写入；加 --write 生效）')


if __name__ == '__main__':
    main()
