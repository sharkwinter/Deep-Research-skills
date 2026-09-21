#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简体 → 繁體（政府呈报版）转换器。

用途
----
同一份 Markdown 底稿要出两种版式：
  * 研究版  —— 简体 / 等线 11pt（`md2docx.py --profile research`）
  * 政府呈报版 —— 繁體 / 標楷體 14pt（`md2docx.py --profile gov`）
本脚本负责把底稿转成繁體，并用词与政府侧文件对齐。

为什么不用单纯的 s2t / s2twp
------------------------------
* `s2twp` 会把术语改成**台湾用法**：軟件→軟體、網絡→網路、數據→資料、芯片→晶片、
  視頻→影片 —— 与澳门/香港公文不符，**不可用**。
* `s2t` 会把「平台」转成「平臺」、「后台」转成「後臺」，与政府文件用字不符。
* 实测《澳琴聯動推進算力建設初步分析報告》（科技廳 2026-08-25）用字：
  平台 13 / 平臺 0、網絡 1 / 網路 0、數據 21 / 資料 2、支持 4 / 支援 0、
  人工智能 7 / 人工智慧 0、智能 10 / 智慧 0。
  因此基线取 **s2hk**（保留 軟件/網絡/數據/芯片/視頻/平台/後台），再叠加
  下方 OVERRIDES 与政府用字对齐。

必须保护的内容（否则破坏可追溯性）
----------------------------------
* URL、行内 `` `code` ``、围栏代码块 —— 全部原样保留；
* **文件路径**：路径里可能含简体中文（如 `企业算力需求汇编.md`），一旦被转成繁體
  就不再指向真实文件，直接违反 R10「精确引用」。故凡含 `/` 或常见扩展名的
  token 一律保护。

用法
----
    python3 to_traditional.py <输入.md> <输出.md> [--quiet]

依赖：`pip install opencc-python-reimplemented`（纯 Python，无需编译）。
"""
import argparse
import re
import sys

try:
    import opencc
except ImportError:  # pragma: no cover
    sys.exit('缺少依赖：pip install opencc-python-reimplemented')

# 与政府文件用字对齐的覆盖表（在 s2hk 之后应用）
OVERRIDES = [
    ('集羣', '集群'),      # s2hk 输出「集羣」，政府/澳门用「集群」
    ('資訊', '信息'),      # 政府文件「信息」为主
    ('支援', '支持'),      # 政府文件「支持」为主
    ('軟體', '軟件'),
    ('網路', '網絡'),
    ('晶片', '芯片'),
    ('影片', '視頻'),
    ('伺服器', '服務器'),
    ('最佳化', '優化'),
    ('演算法', '算法'),
    ('人工智慧', '人工智能'),
    ('裏', '裡'),
]

# 保护模式：URL / 行内代码 / 文件路径 / 引用标记
PROTECT = [
    re.compile(r'https?://[^\s)>\]]+'),
    re.compile(r'`[^`\n]*`'),
    re.compile(r'(?<![\w/])(?:[\w.\-]+/)+[\w.\-]*\.(?:md|csv|json|pdf|png|xlsx|docx|html|txt)'),
    re.compile(r'\[\[[0-9,\s]+\]\]'),
]
PLACEHOLDER = '\x00P%d\x00'


def convert_text(text, converter):
    slots = []

    def stash(m):
        slots.append(m.group(0))
        return PLACEHOLDER % (len(slots) - 1)

    for pat in PROTECT:
        text = pat.sub(stash, text)
    # 逐行转换：围栏代码块整块跳过
    out, in_fence = [], False
    for line in text.split('\n'):
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else converter.convert(line))
    text = '\n'.join(out)
    for name, repl in OVERRIDES:
        text = text.replace(name, repl)
    for i, s in enumerate(slots):
        text = text.replace(PLACEHOLDER % i, s)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    converter = opencc.OpenCC('s2hk')
    src = open(a.src, encoding='utf-8').read()
    dst = convert_text(src, converter)
    open(a.dst, 'w', encoding='utf-8').write(dst)

    if not a.quiet:
        han = lambda s: len(re.findall(r'[\u4e00-\u9fff]', s))
        diff = sum(1 for x, y in zip(src, dst) if x != y)
        print('已写出：%s' % a.dst)
        print('  汉字 %d → %d；逐字符改动 %d 处' % (han(src), han(dst), diff))
        # 抽查：路径与 URL 是否原样保留
        paths = PROTECT[2].findall(src)
        kept = [p for p in paths if p in dst]
        print('  文件路径保护 %d/%d；URL 保护 %d/%d'
              % (len(kept), len(paths),
                 len(PROTECT[0].findall(src)),
                 len([u for u in PROTECT[0].findall(src) if u in dst])))


if __name__ == '__main__':
    main()
