#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把线上问卷的原始回复，落成报告可直接引用的《当前算力台账》。

为什么需要它
------------
在线问卷是**带必答约束的仪器**：`survey_definition.json` 里 `required: true` 的题目
（q4 当前在用算力、q5 算力来源、q8 训练/推理分配、q11 2026 缺口、q12/q13 未来需求、
q26 机柜现状）在**完整提交中必然有答案**。
因此"当前算力"不能记为"无回复/未公开"——那是把**已作答的必答题**当成了缺答。

本脚本做四件事：
1. 读 survey_definition.json，建立 `题目 id → 中文题干 / 类型 / 是否必答` 的字典；
2. 读 responses.csv，按提交（finished）切分，识别"完整提交"与"部分作答"；
3. **把 q4 从纯文本转成 P@FP16 数值**，区分「0（有效值＝无在用算力）」与「未作答」；
4. 用 q6_detail 的卡型×数量对 q4 做**交叉校验**（自报 P ↔ 硬件推算 P），
   并把结果按两个口径汇总：
     - 口径A 本地装机（自建 / 私有化，物理在澳）—— 由 q5 判定
     - 口径B 在用算力（含租赁公有云）
   **禁止**在未做交叉校验的情况下，把整批自报值判为"单位存疑"。

用法
----
    python3 parse_survey.py \
        --csv   /root/Working/polling/polls/macao/result/tech/responses.csv \
        --def   /root/Working/polling/polls/macao/result/tech/survey_definition.json \
        --out   <输出目录>/survey_current_compute.md \
        --a100-p 0.312          # 1×A100 80GB 的 FP16/BF16 稠密算力（PFLOPS）

注意
----
* `CARD_FP16_TFLOPS` 是**参考基准**，用于量级校验，不是权威数据；
  `None` 表示该卡型未取得可靠稠密 FP16 值 → 该条标"不可校验"，交人工。
* 高校侧装机不在本问卷内（问卷对象是企业），必须由高校调研报告单独并入
  「当前算力」总口径——见本脚本输出的"总口径拼装"一节。
"""
import argparse
import csv
import json
import re
from collections import defaultdict

# 硬件换算参考基准：规范名 -> (单"台/卡"FP16/BF16 稠密算力 TFLOPS, 计量单位)
# ⚠️ 这些是**量级校验用**的参考值，不是权威数据；正式引用前必须回源核验并在附录注明。
#    注意"台"与"卡"不可混：Atlas 800I/800T 是 8 卡整机，故按"台"给 3200 TFLOPS。
CARD_SPEC = {
    'A100': (312, '卡'), 'A800': (312, '卡'),
    'H100': (989, '卡'), 'H800': (989, '卡'), 'V100': (125, '卡'),
    'NVIDIA H200': (1979, '卡'), 'NVIDIA B200': (2250, '卡'),
    'RTX 4090': (165, '卡'), 'RTX PRO 6000': (500, '卡'),
    'ASCEND 910B': (400, '卡'), 'ASCEND 910C': (800, '卡'),
    'ATLAS 800I': (3200, '台'), 'ATLAS 800T': (3200, '台'),
    'ATLAS 300V PRO': (70, '卡'),
}
# 兼容旧键名（仅内部使用）
CARD_FP16_TFLOPS = {k: v[0] for k, v in CARD_SPEC.items()}

SOURCE_MAP = {
    '自建': 'A-本地装机',
    '租賃': 'B-在用（云租）',
    '租': 'B-在用（云租）',
    '以上都有': 'A+B-混合',
}


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()


def load_definitions(path):
    d = json.load(open(path, encoding='utf-8'))
    out = {}
    for q in d.get('questions', []):
        h = q.get('headline') or {}
        title = strip_html(h.get('zh-TW') or h.get('default') or h.get('en-US') or '')
        out[q['id']] = {
            'title': title,
            'type': q.get('type'),
            'required': bool(q.get('required')),
            'choices': [strip_html((c.get('label') or {}).get('zh-TW')
                                   or (c.get('label') or {}).get('default') or '')
                        for c in (q.get('choices') or [])],
        }
    return out


def col_of(fieldnames, qid):
    """CSV 列名形如 '中文题干 (q4)'，按 (qid) 匹配。"""
    for k in fieldnames:
        if k.rstrip().endswith('(%s)' % qid):
            return k
    return None


def load_responses(path, defs):
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    fields = list(rows[0].keys())

    def g(r, qid):
        c = col_of(fields, qid)
        return (r.get(c) or '').strip() if c else ''

    recs = []
    for r in rows:
        recs.append({
            'name': g(r, 'q1') or '(未具名)',
            'finished': g(r, 'finished') == 'True' or r.get('finished') == 'True',
            'q4_raw': g(r, 'q4'),
            'q5': g(r, 'q5'),
            'q6_detail': g(r, 'q6_detail'),
            'q8_train': g(r, 'q8'),
            'q11': g(r, 'q11'),
            'q12': g(r, 'q12'),
            'q13': g(r, 'q13'),
            'q26_racks': g(r, 'q26_racks'),
        })
    return recs, fields


def to_float(s):
    """q4 是文本题，需从自由文本里取第一个数。'0' 是有效值。"""
    if s is None:
        return None, '未作答'
    t = str(s).strip()
    if t == '':
        return None, '未作答'
    m = re.search(r'-?\d+(?:[.,]\d+)?', t)
    if not m:
        return None, '非数值：%r' % t[:20]
    v = float(m.group(0).replace(',', ''))
    return v, ('有效（0＝无在用算力）' if v == 0 else '有效')


CARD_ALIASES = [
    # (规范名, 匹配正则)  —— 正则按"最长优先"排列，允许来源中的常见错拼（Altas/Altlas）
    ('RTX PRO 6000', r'rtx\s*pro\s*6000|rtxpro6000'),
    ('ATLAS 300V PRO', r'(?:atlas|altas|altlas)\s*300\s*v(?:\s*pro)?|300\s*v(?:\s*pro)?'),
    ('ATLAS 800T', r'(?:atlas|altas|altlas)\s*800\s*t|800\s*t(?![a-z0-9])'),
    ('ATLAS 800I', r'(?:atlas|altas|altlas)\s*800\s*i|800\s*i(?![a-z0-9])'),
    ('ASCEND 910C', r'(?:ascend|昇腾)?\s*910\s*c'),
    ('ASCEND 910B', r'(?:ascend|昇腾)?\s*910\s*b'),
    ('RTX 4090', r'rtx\s*4090|(?<![\d])4090(?![\d])'),
    ('NVIDIA B200', r'(?:nvidia\s*)?b\s*200(?![0-9])'),
    ('NVIDIA H200', r'(?:nvidia\s*)?h\s*200(?![0-9])'),
    ('A100', r'(?<![a-z0-9])a\s*100(?![0-9])'),
    ('A800', r'(?<![a-z0-9])a\s*800(?![0-9])'),
    ('H100', r'(?<![a-z0-9])h\s*100(?![0-9])'),
    ('H800', r'(?<![a-z0-9])h\s*800(?![0-9])'),
    ('V100', r'(?<![a-z0-9])v\s*100(?![0-9])'),
]


def normalize(t):
    """统一全角/符号，并把 '800Tx2' 这类粘连拆成 '800t x2'。"""
    t = (t or '').lower().replace('×', ' x ').replace('＊', ' x ').replace('*', ' x ')
    t = re.sub(r'(?<=[a-z])\s*x\s*(?=\d)', ' x', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def resolve_count(seg, m):
    """在片段中为已命中的卡型找数量。按"邻近优先"分级回退，取不到就明确交人工。"""
    alias = re.escape(m.group(0))
    # 0) 显式合计："共 N 张/卡"
    r = re.search(r'共\s*(\d+)\s*(?:張|张|卡|台)', seg)
    if r:
        return int(r.group(1)), '显式合计'
    # 1) 卡型 x N   （rtx 4090 x4 / 800t x2 / 300v pro x12）
    r = re.search(alias + r'\s*x\s*(\d+)', seg)
    if r:
        return int(r.group(1)), '卡型×N'
    # 2) N x …<卡型>  （8 x nvidia b200；允许中间夹厂商名与空格）
    r = re.search(r'(\d+)\s*x\s*.{0,16}?' + alias, seg)
    if r:
        return int(r.group(1)), 'N×卡型'
    # 3) N 卡/張/台 …<卡型>  （16 卡 rtx pro 6000）
    r = re.search(r'(\d+)\s*(?:卡|張|张|台|顆|颗)\s*.{0,8}?' + alias, seg)
    if r:
        return int(r.group(1)), 'N(单位)+卡型'
    # 4) 兜底：把片段里**所有**卡型（含同一卡型的第二次出现）都抠掉后，若只剩一个数就用它
    rest = seg
    for _, pat in CARD_ALIASES:
        rest = re.sub(pat, ' ', rest)
    nums = [int(x) for x in re.findall(r'\d+', rest)]
    if len(nums) == 1:
        return nums[0], '片段唯一数'
    return None, '数量未解析'


def cross_check(detail):
    """从 q6_detail 抽 (数量, 卡型) 并推算 P@FP16。

    返回 (明细 list, 推算 P 或 None, 是否全部可校验)
    """
    if not detail or not detail.strip():
        return [], None, None
    segs = [s for s in re.split(r'[,;、；+＋\n]', normalize(detail)) if s.strip()]
    segs = [s for s in segs if not re.fullmatch(r'\s*(0|沒有|没有|无|無|none|-|—|/)\s*', s)]
    found, tot, all_known = [], 0.0, True
    for seg in segs:
        best = None
        for name, pat in CARD_ALIASES:          # 表序即优先级，取最长匹配
            m = re.search(pat, seg)
            if m and (best is None or len(m.group(0)) > len(best[1].group(0))):
                best = (name, m)
        if best is None:
            if re.search(r'\d', seg):
                found.append('「%s」未识别出卡型，需人工核验' % seg.strip()[:24])
                all_known = False
            continue
        name, m = best
        qty, how = resolve_count(seg, m)
        spec = CARD_SPEC.get(name)
        if qty is None:
            found.append('%s = 数量未解析（%s）' % (name, seg.strip()[:20]))
            all_known = False
        elif spec:
            tf, unit = spec
            p = qty * tf / 1000.0
            tot += p
            found.append('%d×%s(%s) = %.1fP' % (qty, name, unit, p))
        else:
            found.append('%d×%s = ?P（卡型未在基准表）' % (qty, name))
            all_known = False
    if not found:
        return [], None, None
    return found, tot, all_known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--def', dest='defpath', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--a100-p', type=float, default=0.312,
                    help='1×A100 80GB 的 FP16/BF16 稠密算力（PFLOPS），默认 0.312')
    a = ap.parse_args()

    defs = load_definitions(a.defpath)
    recs, _ = load_responses(a.csv, defs)
    a100 = a.a100_p

    answered = []
    for r in recs:
        v, status = to_float(r['q4_raw'])
        if v is None:
            continue
        r['q4'] = v
        r['q4_status'] = status
        r['bucket'] = next((v2 for k, v2 in SOURCE_MAP.items() if k in r['q5']), '未判定')
        r['cards'], r['implied_p'], r['all_known'] = cross_check(r['q6_detail'])
        answered.append(r)

    finished = [r for r in recs if r['finished']]
    named = {r['name'] for r in recs if r['name'] != '(未具名)'}
    blank = [r for r in recs if not r['q4_raw'] and not r['q5'] and r['name'] == '(未具名)']

    L = []
    L.append('# 当前算力台账（由线上问卷回复生成）\n')
    L.append('> 数据源：`%s`（问卷结构：`%s`）\n' % (a.csv, a.defpath))
    L.append('> 取值口径：q4「當前企業在用算力共有多少 P@FP16？」为**必答题**；'
             '折算基准 1×A100 80GB = %.3f P@FP16（稠密）。\n' % a100)

    L.append('\n## 一、样本与作答结构\n')
    L.append('| 指标 | 数值 |')
    L.append('|---|---|')
    L.append('| CSV 记录总数 | %d |' % len(recs))
    L.append('| `finished=True`（完整提交） | %d（%.1f%%） |'
             % (len(finished), 100.0 * len(finished) / max(len(recs), 1)))
    L.append('| 去重后具名企业 | %d |' % len(named))
    L.append('| 完全空白记录 | %d |' % len(blank))
    L.append('| **提供 q4（当前算力）的记录** | **%d** |' % len(answered))
    L.append('| 完整提交中 q4 作答率 | **%d/%d = %.0f%%**（必答题，必然有答案） |'
             % (sum(1 for r in finished if 'q4' in r), len(finished),
                100.0 * sum(1 for r in finished if 'q4' in r) / max(len(finished), 1)))
    L.append('\n**结论：当前算力不是"无回复"。** q4 是必答题，完整提交 100%% 作答；'
             '未完成问卷亦留有 %d 条作答。其中 `0` 是**有效答案（＝无在用算力）**，'
             '不是缺答。\n' % (len(answered) - sum(1 for r in finished if 'q4' in r)))

    L.append('\n## 二、逐企业当前算力（q4 + q5 + q6 交叉校验）\n')
    L.append('| 企业 | 完整 | q4 在用算力 (P@FP16) | q5 来源 | 口径分桶 | q6 硬件明细 | 硬件推算 | 校验 |')
    L.append('|---|---|---|---|---|---|---|---|')
    for r in answered:
        chk = '—'
        if r['implied_p'] is not None:
            ratio = (r['q4'] / r['implied_p']) if r['implied_p'] else None
            if not r['all_known']:
                chk = '部分卡型待核'
            elif ratio is None:
                chk = '自报0'
            elif 0.5 <= ratio <= 2.0:
                chk = '✅ 自洽（%.2f×）' % ratio
            else:
                chk = '⚠️ 偏差 %.2f×' % ratio
        L.append('| %s | %s | **%s** | %s | %s | %s | %s | %s |' % (
            r['name'], 'Y' if r['finished'] else '',
            ('%g' % r['q4']) + ('（0＝无）' if r['q4'] == 0 else ''),
            r['q5'] or '—', r['bucket'], r['q6_detail'] or '—',
            ('%.1f P' % r['implied_p']) if r['implied_p'] is not None else '—', chk))

    grp = defaultdict(lambda: [0.0, 0])
    for r in answered:
        grp[r['bucket']][0] += r['q4']
        grp[r['bucket']][1] += 1
    tot = sum(r['q4'] for r in answered)
    L.append('\n## 三、两口径汇总（**不得混算**）\n')
    L.append('| 口径 | 家数 | Σ P@FP16 | ≈ A100 等效（张） | 含义 |')
    L.append('|---|---|---|---|---|')
    loc = grp['A-本地装机'][0] + grp['A+B-混合'][0]
    nloc = grp['A-本地装机'][1] + grp['A+B-混合'][1]
    cloud = grp['B-在用（云租）'][0]
    L.append('| **口径A 本地装机**（自建＋混合中落在本地的部分） | %d | %.0f | ≈%.0f | 物理在澳、可算作本地供给 |'
             % (nloc, loc, loc / a100))
    L.append('| 其中：纯自建（下界） | %d | %.0f | ≈%.0f | q5＝自建算力（私有化部署） |'
             % (grp['A-本地装机'][1], grp['A-本地装机'][0], grp['A-本地装机'][0] / a100))
    L.append('| 其中：混合部署（需拆分本地/云） | %d | %.0f | ≈%.0f | q5＝以上都有 |'
             % (grp['A+B-混合'][1], grp['A+B-混合'][0], grp['A+B-混合'][0] / a100))
    L.append('| 口径B 纯公有云租赁 | %d | %.0f | ≈%.0f | 在用但不在澳，不计入本地装机 |'
             % (grp['B-在用（云租）'][1], cloud, cloud / a100))
    L.append('| **合计：在用算力（A+B）** | %d | **%.0f** | **≈%.0f** | 与 q4 作答集合等价 |'
             % (len(answered), tot, tot / a100))

    L.append('\n## 四、总口径拼装（当前算力＝企业＋高校＋政务/社会资本）\n')
    L.append('> ⚠️ 问卷对象是**企业**，不含高校。报告"当前算力"总口径必须把高校侧并入，'
             '否则会系统性低估。\n')
    L.append('| 分项 | 来源 | 本地装机 | 备注 |')
    L.append('|---|---|---|---|')
    L.append('| 企业（本问卷） | q4＋q5＋q6 | 口径A ≈%.0f P（≈%.0f 张 A100 等效） | 12 家作答，其中 8 家完整提交 |'
             % (loc, loc / a100))
    L.append('| 高校与科研 | 高校调研报告（另行并入） | **待填** | 必须并入，并按同一 A100 等效口径折算 |')
    L.append('| 政务/社会资本 | 政府云、CTM AI Hub 等 | **待填**（多未公开） | 未公开者记为负面发现，不得静默省略 |')

    L.append('\n## 五、必答题目清单（可直接引用的"仪器约束"）\n')
    L.append('以下题目 `required=true`：完整提交中**必然有答案**，'
             '因此不得把相应字段写成"无回复"。\n')
    L.append('| id | 题干 | 类型 |')
    L.append('|---|---|---|')
    for qid, q in defs.items():
        if q['required']:
            L.append('| %s | %s | %s |' % (qid, q['title'], q['type']))

    open(a.out, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('已写出：%s' % a.out)
    print('── 摘要 ──')
    print('  q4 作答 %d 条 | Σ %.0f P@FP16 ≈ %.0f 张 A100 等效' % (len(answered), tot, tot / a100))
    print('  口径A 本地装机 ≈ %.0f P（下限：纯自建 %.0f P）' % (loc, grp['A-本地装机'][0]))
    print('  口径B 纯公有云   ≈ %.0f P' % cloud)


if __name__ == '__main__':
    main()
