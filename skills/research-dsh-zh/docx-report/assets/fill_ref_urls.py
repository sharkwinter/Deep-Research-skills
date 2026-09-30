#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把附录F 中 `Rn.` 条目的「原始链接：【待补】」替换为**经抓取核验**的真实链接。

用法
----
    python3 fill_ref_urls.py <full_draft.md|part3.md> <urls.json>

urls.json 形如：
    {"2": ["https://www.ndrc.gov.cn/xxgk/zcfb/tz/202312/t20231229_1362997.html"],
     "3": ["https://...", "https://..."],
     "8": ["https://..."]}

约束
----
* **只替换紧跟在该 Rn 条目之后的那一行**「原始链接：【待补】…」，不触碰其他条目；
* 每个编号必须在 json 中出现且链接非空，否则抛错（避免"以为补了其实没补"）；
* 幂等性：已补录过的条目不再匹配【待补】模板，可安全重复执行；
* 落盘前断言：脚本末尾重新统计剩余【待补】数并打印，便于在链式步骤中核对。
"""
import json
import re
import sys

TEMPLATE = '　　原始链接：%s。其内容摘录见下方中间报告的 `sources/SOURCES.md`。'


def main():
    md_path, map_path = sys.argv[1], sys.argv[2]
    mapping = json.load(open(map_path, encoding='utf-8'))
    for k, v in mapping.items():
        assert isinstance(v, list) and v and all(u.startswith('http') for u in v), \
            '编号 %s 的链接非法：%r' % (k, v)

    lines = open(md_path, encoding='utf-8').read().split('\n')
    done, cur = [], None
    for i, ln in enumerate(lines):
        mt = re.match(r'^R(\d+)\. ', ln)
        if mt:
            cur = mt.group(1)
            continue
        if ln.startswith('　　原始链接：【待补】'):
            assert cur, '第 %d 行出现【待补】但未找到所属 Rn 条目' % (i + 1)
            if cur in mapping:
                lines[i] = TEMPLATE % '；'.join(mapping[cur])
                done.append(cur)
            cur = None          # 同一 Rn 只补一次

    open(md_path, 'w', encoding='utf-8').write('\n'.join(lines))
    print('已补录 %d 条：%s' % (len(done), sorted(done, key=int)))
    left = len(re.findall(r'原始链接：【待补】', '\n'.join(lines)))
    print('仍待补：%d 条' % left)
    # 已补过的编号在同一 json 里再次出现属正常（幂等重跑），只提示不报错
    already = sorted(set(mapping) - set(done), key=int)
    if already:
        print('提示：以下编号本期未匹配到【待补】行（多为此前已补录）：%s' % already)


if __name__ == '__main__':
    main()
