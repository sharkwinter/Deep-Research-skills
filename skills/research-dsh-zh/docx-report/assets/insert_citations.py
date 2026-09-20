#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
insert_citations.py — 为报告正文批量插入 [[n]] 引用角标标记。

设计原则
--------
- **章节默认引用集 + 关键词触发引用**两层叠加，保证"重要判断/结论必有引用"。
- 只在**可能含判断或数据**的段落上打标（含数字、判断词、或本身是列表项）。
- 跳过：标题、表格行、参考文献行（R#）、引用块（`>`）、附录区、已含 `[[` 的行。
- 不猜测事实归属：引用集必须由调用方在 config 中显式给定。

与 md2docx.py 的契约
--------------------
  * `[[n]]` / `[[n,m]]`  → 上标 + 内部超链接，跳转书签 `_Refn`
  * 参考文献条目写作 `Rn. <完整条目>` → 自动生成书签 `_Refn` 并渲染为 `[n] <条目>`

用法
----
  python3 insert_citations.py --config citations.json part1.md part2.md ...
  python3 insert_citations.py --strip part1.md part2.md ...     # 先清空重来

config（JSON，可省略以使用内置空默认）：
{
  "section_refs":   { "1.1": [1,2], "3.2.1": [47,48], "...": [] },
  "keyword_refs":   [ {"pattern": "第\\s*8/2005", "refs": [60]}, ... ],
  "judge_pattern":  "结论|判断|表明|显示|意味着|因此|综上|核心|关键|建议|缺口|瓶颈|痛点|定位|趋势|特征|由此|可见|说明",
  "max_refs":       5,
  "appendix_starts": ["## 七、", "### 附录"],
  "strip_top_until_first_h2": true
}
"""

import argparse
import json
import re
import sys

DEFAULT_JUDGE = ("结论|判断|表明|显示|意味着|因此|综上|核心|关键|建议|缺口|瓶颈|"
                 "痛点|定位|趋势|特征|由此|可见|说明")

CITE_RX = re.compile(r'\[\[[0-9,\s]+\]\]')
SEC_RX = re.compile(r'^#{2,4}\s+([0-9]+(?:\.[0-9]+)*)')
H_RX = re.compile(r'^#{1,7}\s')
REF_LINE_RX = re.compile(r'^R\d+\.')
ORDERED_RX = re.compile(r'^\s*\d+[.)]\s')
BULLET_RX = re.compile(r'^\s*[-*+]\s')


def refs_for(section, text, section_refs, kw_refs, max_refs):
    refs = list(section_refs.get(section, []))
    for rx, v in kw_refs:
        if rx.search(text):
            refs.extend(v)
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    out.sort()
    return out[:max_refs]


def strip_tokens(path):
    s = open(path, encoding='utf-8').read()
    n = len(CITE_RX.findall(s))
    open(path, 'w', encoding='utf-8').write(CITE_RX.sub('', s))
    return n


def process(path, cfg):
    section_refs = {k: list(v) for k, v in cfg.get('section_refs', {}).items()}
    kw_refs = [(re.compile(d['pattern']), d['refs']) for d in cfg.get('keyword_refs', [])]
    judge = re.compile(cfg.get('judge_pattern', DEFAULT_JUDGE))
    max_refs = int(cfg.get('max_refs', 5))
    appendix_starts = tuple(cfg.get('appendix_starts', []))
    skip_top = bool(cfg.get('strip_top_until_first_h2', True))

    lines = open(path, encoding='utf-8').read().split('\n')
    out, section, in_appendix, started = [], None, False, not skip_top
    for ln in lines:
        st = ln.strip()

        m = SEC_RX.match(st)
        if m:
            section = m.group(1)
            in_appendix = any(st.startswith(a) for a in appendix_starts)
            out.append(ln)
            continue
        if any(st.startswith(a) for a in appendix_starts):
            in_appendix = True
            out.append(ln)
            continue
        if H_RX.match(st):
            if st.startswith('## '):
                started = True
            out.append(ln)
            continue
        # 非标题、未进入正文、表格、参考文献、引用块 → 原样
        if (not st or st.startswith('|') or REF_LINE_RX.match(st)
                or st.startswith('>') or not started or in_appendix):
            out.append(ln)
            continue
        if '[[' in st or section is None:
            out.append(ln)
            continue

        qualifies = (bool(re.search(r'[0-9]', st)) or bool(judge.search(st))
                     or bool(ORDERED_RX.match(st)) or bool(BULLET_RX.match(st)))
        if not qualifies:
            out.append(ln)
            continue

        refs = refs_for(section, st, section_refs, kw_refs, max_refs)
        if not refs:
            out.append(ln)
            continue
        token = '[[' + ','.join(str(x) for x in refs) + ']]'
        body = ln.rstrip()
        if body.endswith('。'):
            i = body.rfind('。')
            out.append(body[:i] + token + body[i:])
        else:
            out.append(body + token)

    open(path, 'w', encoding='utf-8').write('\n'.join(out))
    n = len(CITE_RX.findall('\n'.join(out)))
    print('processed %s  (tokens now: %d)' % (path, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--config', default=None)
    ap.add_argument('--strip', action='store_true',
                    help='先移除已有 [[n]] 标记（重跑前使用）')
    args = ap.parse_args()

    if args.strip:
        for f in args.files:
            print('stripped %s (%d tokens)' % (f, strip_tokens(f)))
        return

    cfg = {}
    if args.config:
        with open(args.config, encoding='utf-8') as fh:
            cfg = json.load(fh)
    for f in args.files:
        process(f, cfg)


if __name__ == '__main__':
    main()
