#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa_slides.py — 兩頁 PPT 提綱「引用紀律 + 模板對齊」QA（/research-slides 通用版）

用法：
    python3 qa_slides.py [--slug SLUG] [--verbose]

放置位置：與 `results/`、`sources/`、`slides/` 同級的工作區根目錄。

對象清單來源（依序）：
  1. `--slug` 參數（可重複）
  2. 環境變數或本檔頂部 ENTITIES 常數
  3. **自動發現** `results/*.json`（排除底線開頭）

核驗項：
  1. Slide 1／Slide 2 結構
  2. 〈待驗項〉表存在
  3. 引用鍵對照表存在（解析出 ≥5 列）
  4. 引用鍵雙向對齊（正文用 ↔ 表定義）
  5. **被引檔是否真實存在**（遞迴索引 sources/、results/、工作區根）
  6. 量化／算力要素存在
  7. 「核心結論」段落存在
  8. 口徑聲明存在（可依領域自訂關鍵詞，見 CALIBER_PATTERNS）

────────────────────────────────────────────────────────────────
⚠️ 本腳本曾經出現過三類假陽性，以下修正**必須保留**，否則會誤報：
  (a) 非遞迴索引 —— 子代理常把手引檔放在 raw/ 等子目錄，只列頂層會大量誤報「被引檔不存在」
  (b) ASCII-only 檔名正則 —— 中文檔名會被截斷成尾段，同樣誤報
  (c) 多檔名 evidence 字串 —— 一個字串裡用「、」串多個檔名，須先切分
  另：(d) 〈待驗項〉表的 `T1`/`1` 編號會被誤認為引用鍵，故引用鍵字首限 `S`/`M`
────────────────────────────────────────────────────────────────
"""
import os, re, sys, json, argparse

BASE = os.path.dirname(os.path.abspath(__file__))
SLIDES = os.path.join(BASE, "slides")
RESULTS = os.path.join(BASE, "results")

# 可選：在此硬編碼對象清單；留空則自動發現 results/*.json
ENTITIES = []

# 額外索引根目錄：預設含「上一層」（因為子代理常引用被重用的兄弟調研目錄，
# 如 ../<other-research>/xxx.json）。這些引用是合法的，但**必須在對照表明示**，
# 故本腳本將其歸為 warn（跨目錄）而非 err。
EXTRA_ROOTS = [os.path.dirname(BASE)]

# 引用鍵字首：S=來源檔、M=模型/中間檔輸出。**不含 T**（以免誤吃〈待驗項〉編號）
KEY_PREFIX = "SM"

# 口徑聲明關鍵詞（依領域自訂；任一命中即算通過）
CALIBER_PATTERNS = r"AI-only|等效卡時|A100|PFLOPS|等效|口徑聲明|口徑|only"

ROW_RE = re.compile(rf"\|\s*\[?([{KEY_PREFIX}]\d+[a-z]?)\]?\s*\|(.+?)\|", re.M)
KEY_RE = re.compile(rf"\[([{KEY_PREFIX}]\d+[a-z]?)\]")
MALFORMED_RE = re.compile(rf"\[[{KEY_PREFIX}]\d+\s*[→\-–>]")

# (b) 支援 CJK 檔名
FNAME_RE = re.compile(
    r"`?([\w\u4e00-\u9fff\u3400-\u4dbf\.\-]+\.(?:md|pdf|html|txt|json|csv|py|xlsx?))`?")

NUM_PATTERN = r"卡時|A100|PFLOPS|等效|營收|收入|市佔|萬|億|MOP|HK\$|USD"


def split_evidence(s):
    """(c) 多檔名 evidence 字串：以「、」「，」「;」切分後逐檔比對。"""
    if not isinstance(s, str):
        return []
    out = []
    for p in re.split(r"[、,;；\n]+", s):
        p = p.strip().strip("`").strip()
        m = re.match(r"^([^\s]+\.(?:md|pdf|html|txt|json|csv|py|xlsx?))", p, re.I)
        if m:
            out.append(m.group(1))
    return out


def build_index():
    """(a) 遞迴索引 sources/、results/ 與工作區根檔案。"""
    idx = set()
    for sub in ("sources", "results", "slides"):
        d = os.path.join(BASE, sub)
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            rel = os.path.relpath(root, BASE)
            for f in files:
                idx.add(f)
                idx.add(os.path.join(rel, f))
                idx.add(os.path.join(sub, f))
    for f in os.listdir(BASE):
        if os.path.isfile(os.path.join(BASE, f)):
            idx.add(f)
    # 額外根（預設上層目錄）：僅索引檔名，用於識別「合法的跨目錄引用」
    for extra in EXTRA_ROOTS:
        if not os.path.isdir(extra):
            continue
        for root, dirs, files in os.walk(extra):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "node_modules", "__pycache__", ".venv")]
            for f in files:
                idx.add(f)
    return idx


def collect_evidence(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "evidence":
                if isinstance(v, str):
                    out.extend(split_evidence(v))
                elif isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            out.extend(split_evidence(x))
            else:
                collect_evidence(v, out)
    elif isinstance(node, list):
        for x in node:
            collect_evidence(x, out)


def check(slug, idx, verbose=False):
    path = os.path.join(SLIDES, f"{slug}_两页PPT提纲.md")
    if not os.path.isfile(path):
        return None
    txt = open(path, encoding="utf-8", errors="ignore").read()
    r = {"slug": slug, "bytes": os.path.getsize(path), "ok": [], "warn": [], "err": []}

    s1 = bool(re.search(r"Slide\s*1", txt))
    s2 = bool(re.search(r"Slide\s*2", txt))
    (r["ok"] if s1 and s2 else r["err"]).append(f"Slide1={s1} Slide2={s2}")

    if re.search(r"待驗項|待验项|待核項", txt):
        r["ok"].append("含〈待驗項〉表")
    else:
        r["err"].append("缺〈待驗項〉表")

    rows = ROW_RE.findall(txt)
    if len(rows) >= 5:
        r["ok"].append(f"引用鍵對照表 {len(rows)} 列")
    else:
        r["err"].append(f"引用鍵對照表列數不足（{len(rows)}）")

    defined = {}
    for m in ROW_RE.finditer(txt):
        defined.setdefault(m.group(1), []).extend(FNAME_RE.findall(m.group(2)))
    used = set(KEY_RE.findall(txt))
    if defined:
        r["ok"].append(f"引用鍵 defined={len(defined)} used={len(used)}")
        unused = sorted(set(defined) - used)
        undef = sorted(used - set(defined))
        if unused:
            r["warn"].append(f"{len(unused)} 鍵定義未用: {unused[:5]}")
        if undef:
            r["warn"].append(f"{len(undef)} 鍵正文用了但未定義: {undef[:5]}")
    else:
        r["warn"].append("未解析出引用鍵對照表列（格式可能不同）")

    # 先建立「本專案內」的檔案集合，用於區分本專案引用與跨目錄引用
    local = set()
    for sub in ("sources", "results", "slides"):
        d = os.path.join(BASE, sub)
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in files:
                local.add(f)
    for f in os.listdir(BASE):
        if os.path.isfile(os.path.join(BASE, f)):
            local.add(f)

    cited, crossdir, missing = set(), [], []
    for files in defined.values():
        for f in files:
            base = os.path.basename(f)
            if f in local or base in local:
                cited.add(f)
            elif f in idx or base in idx:
                crossdir.append(f)          # 存在於上層／兄弟目錄 → 合法但須明示
            else:
                missing.append(f)
    if cited:
        r["ok"].append(f"{len(cited)} 被引檔在本專案內存在")
    if crossdir:
        r["warn"].append(f"{len(crossdir)} 個跨目錄引用（須在對照表明示）: {sorted(set(crossdir))[:5]}")
    if missing:
        r["err"].append(f"{len(missing)} 被引檔不存在: {missing[:6]}")

    if re.search(NUM_PATTERN, txt):
        r["ok"].append("含量化／算力要素")
    else:
        r["warn"].append("未見量化要素")

    if re.search(r"核心結論|核心结论", txt):
        r["ok"].append("含核心結論")
    else:
        r["warn"].append("未見「核心結論」")

    if re.search(CALIBER_PATTERNS, txt):
        r["ok"].append("含口徑聲明")
    else:
        r["warn"].append("未見口徑聲明")

    bad = MALFORMED_RE.findall(txt)
    if bad:
        r["warn"].append(f"疑似畸形引用鍵: {bad[:4]}")

    # 額外：若 results/<slug>.json 存在，抽查其 evidence 是否可解析（(c) 修正）
    jp = os.path.join(RESULTS, f"{slug}.json")
    if os.path.isfile(jp):
        try:
            ev = []
            collect_evidence(json.load(open(jp, encoding="utf-8")), ev)
            ev = sorted(set(ev))
            bad_ev = [e for e in ev if e not in idx and os.path.basename(e) not in idx
                      and not e.startswith("http")]
            ev_local = [e for e in ev if e in local or os.path.basename(e) in local]
            ev_cross = [e for e in ev if e not in local and os.path.basename(e) not in local
                        and e in idx]
            if ev_local:
                r["ok"].append(f"results JSON evidence 本專案內 {len(ev_local)} 條可解析")
            if ev_cross:
                r["warn"].append(f"results JSON evidence {len(ev_cross)} 條為跨目錄引用: {sorted(set(ev_cross))[:3]}")
            if bad_ev:
                r["warn"].append(f"results JSON 內 {len(bad_ev)} 個 evidence 檔不存在: {bad_ev[:4]}")
        except Exception as e:
            r["err"].append(f"results JSON 解析失敗: {e}")

    return r


def discover():
    if ENTITIES:
        return ENTITIES
    if os.path.isdir(RESULTS):
        return sorted(os.path.basename(f)[:-5] for f in os.listdir(RESULTS)
                      if f.endswith(".json") and not f.startswith("_"))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", action="append", default=[])
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    slugs = a.slug or discover()
    if not slugs:
        print("!! 未發現任何對象（results/*.json 為空且未指定 --slug）")
        return 1
    idx = build_index()
    rows, done = [], 0
    for slug in slugs:
        r = check(slug, idx, a.verbose)
        if r is None:
            print(f"[MISS] {slug:22s} slides/{slug}_两页PPT提纲.md 尚未產出")
            continue
        done += 1
        rows.append(r)
        st = "ERR " if r["err"] else ("WARN" if r["warn"] else "OK  ")
        print(f"[{st}] {slug:22s} {r['bytes']:>8,} B")
        if a.verbose or r["err"]:
            for x in r["ok"]:
                print(f"        ok   : {x}")
        for x in r["warn"]:
            print(f"        warn : {x}")
        for x in r["err"]:
            print(f"        ERROR: {x}")
    print()
    print(f"=== 已交付提綱 {done}/{len(slugs)} ===")
    bad = [x["slug"] for x in rows if x["err"]]
    print("有錯誤：" + (", ".join(bad) if bad else "無"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
