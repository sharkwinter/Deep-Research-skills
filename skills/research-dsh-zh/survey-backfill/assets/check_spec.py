#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-check a survey spec BEFORE creating the survey, and re-check it against
the live survey AFTER any structural edit.

Usage:
  check_spec.py <spec.json> [--strict] [--live [--survey-id SID]]

Why this exists
---------------
The results page renders questions in **spec['sections'] order**, while
respondents answer them in **spec['questions'] order** (== the live survey's
`blocks` order). If the two orders diverge, the results page silently groups
questions under the wrong heading, or strands cards *after* the CTA card.

The naive check `set(questions) == set(section_refs)` **passes** in that case,
because the two are equal as SETS. This script therefore also compares ORDER.

Checks
------
  R1 duplicate question ids in spec['questions']                       FAIL
  R2 section refs pointing at a non-existent question                  FAIL
  R3 questions not referenced by exactly one section                   FAIL
  R4 spec vs live element ids / order                     --live      FAIL/WARN
  R5 sections-flattened ORDER vs questions ORDER     WARN (FAIL w/ --strict)
  R6 single/multi has choices with unique labels                       FAIL
  R7 `other: true` on a choice question that has real choices          FAIL
  R8 missing headline_zh / headline_en                                 FAIL/WARN
  R9 `numeric: true` but a placeholder that is not purely numeric      WARN
  R10 spec `numeric` flag disagrees with the live inputType  --live    WARN

Exit code: 0 ok, 1 problems found.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

API_KEY_NAMES = ("SURVEY_API_KEY", "MACAO_API_KEY")


def plain(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", v or "")).strip()


def read_key_file(path):
    """Priority: SURVEY_API_KEY / MACAO_API_KEY, then any fbk_ value."""
    pairs = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            pairs.append((k.strip(), v.strip().strip('"').strip("'")))
    for name in API_KEY_NAMES:
        for k, v in pairs:
            if k == name and v:
                return v
    for k, v in pairs:
        if v.startswith("fbk_"):
            return v
    return None


def fetch_live(base, key, sid):
    req = urllib.request.Request(f"{base.rstrip('/')}/api/v1/management/surveys/{sid}",
                                 headers={"x-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return d.get("data", d)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--strict", action="store_true",
                    help="treat order divergence (R5) as a failure")
    ap.add_argument("--live", action="store_true",
                    help="also diff the spec against the live survey")
    ap.add_argument("--base", help="API base URL, e.g. http://host:port")
    ap.add_argument("--key-file", help=".env / key file holding the API key")
    ap.add_argument("--survey-id", help="override spec['survey_id']")
    a = ap.parse_args()

    spec = json.load(open(a.spec, encoding="utf-8"))
    questions = spec.get("questions") or []
    sections = spec.get("sections") or []
    qids = [q["id"] for q in questions]
    flat = [qid for s in sections for qid in (s.get("questions") or [])]

    fails, warns, notes = [], [], []

    # ---- R1 ---------------------------------------------------------------
    dupes = sorted({x for x in qids if qids.count(x) > 1})
    if dupes:
        fails.append(f"R1 duplicate question ids in spec['questions']: {dupes}")

    # ---- R2 / R3 ----------------------------------------------------------
    unknown = sorted({x for x in flat if x not in set(qids)})
    if unknown:
        fails.append(f"R2 section refs to non-existent questions: {unknown}")
    unreferenced = sorted(set(qids) - set(flat))
    if unreferenced:
        fails.append(f"R3 questions not referenced by any section: {unreferenced}")
    multi_ref = sorted({x for x in flat if flat.count(x) > 1})
    if multi_ref:
        fails.append(f"R3 question referenced by more than one section: {multi_ref}")

    # ---- R5: the check a set comparison misses ----------------------------
    if not unknown and not unreferenced:
        if flat == qids:
            notes.append("R5 sections order == questions order")
        else:
            pos = {q: i for i, q in enumerate(flat)}
            where = [(i, pos.get(q), q) for i, q in enumerate(qids) if pos.get(q) != i]
            head = "\n".join(
                f"       questions[{i:>2}] {q:<28} actually sits at sections[{p}]"
                for i, p, q in where[:12])
            more = f"\n       … and {len(where) - 12} more" if len(where) > 12 else ""
            msg = (f"R5 sections ORDER != questions ORDER ({len(where)} position(s) differ).\n"
                   f"     The results page renders in SECTIONS order; respondents answer in\n"
                   f"     QUESTIONS order (== live blocks order). Fix by moving each question\n"
                   f"     back into its correct section (a wrong section assignment shows up\n"
                   f"     as a whole run of shifted positions).\n{head}{more}")
            (fails if a.strict else warns).append(msg)

    # ---- R6 / R7 / R8 / R9 ------------------------------------------------
    for q in questions:
        qid, t = q["id"], q.get("type")
        if not q.get("headline_zh"):
            fails.append(f"R8 {qid}: missing headline_zh")
        if not q.get("headline_en"):
            warns.append(f"R8 {qid}: missing headline_en (blocks bilingual rendering)")

        if t in ("single", "multi"):
            ch = q.get("choices") or []
            if not ch:
                fails.append(f"R6 {qid}: {t} with no choices")
            if q.get("other") and not ch:
                fails.append(f"R7 {qid}: other=true leaves only the auto-added 「其他」")
            labels = [plain(c.get("zh")) for c in ch]
            if len(labels) != len(set(labels)):
                fails.append(f"R6 {qid}: duplicate choice labels {labels}")
            # an explicit id="other" entry collides with the auto-generated one
            if any((c.get("id") or "") == "other" for c in ch):
                fails.append(f"R6 {qid}: choices already contain id 'other' — "
                             "survey_lib adds it automatically; drop it or set other:false")

        if t == "open" and q.get("numeric"):
            ph = q.get("placeholder_zh") or q.get("placeholder") or ""
            if ph and not re.fullmatch(r"[\d\s.,，]+", plain(ph)):
                warns.append(f"R9 {qid}: numeric:true but placeholder {ph!r} is not purely "
                             "numeric — a numeric question renders <input type=number>")

    # ---- R4 / R10: live diff ---------------------------------------------
    if a.live:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import survey_lib as L
        base = a.base or L.API
        key = read_key_file(a.key_file) if a.key_file else None
        if not key:
            try:
                key = L.load_key()
            except SystemExit as e:
                fails.append(f"R4 cannot resolve API key: {e}")
                key = None
        sid = a.survey_id or spec.get("survey_id")
        if key and not sid:
            fails.append("R4 --live given but no survey_id (spec or --survey-id)")
        elif key:
            live = fetch_live(base, key, sid)
            blocks = live.get("blocks") or []
            live_ids = [e["id"] for b in blocks for e in b.get("elements") or []]
            if not live_ids:
                live_ids = [q["id"] for q in live.get("questions") or []]
            only_spec = sorted(set(qids) - set(live_ids))
            only_live = sorted(set(live_ids) - set(qids))
            if only_spec:
                fails.append(f"R4 in spec but not live: {only_spec}")
            if only_live:
                fails.append(f"R4 in live but not spec — the results page will omit them: "
                             f"{only_live}")
            if not only_spec and not only_live:
                if live_ids == qids:
                    notes.append(f"R4 spec == live ({len(live_ids)} elements, same order)")
                else:
                    warns.append("R4 spec and live carry the same ids in a DIFFERENT order — "
                                 "respondents are seeing a different order than the spec renders")

            LQ = {q["id"]: q for q in live.get("questions") or []}
            for q in questions:
                lq = LQ.get(q["id"])
                if not lq:
                    continue
                if q.get("type") == "open" and bool(q.get("numeric")) != (lq.get("inputType") == "number"):
                    warns.append(f"R10 {q['id']}: spec numeric={bool(q.get('numeric'))} but live "
                                 f"inputType={lq.get('inputType')!r} — spec drift")

    print(f"spec: {a.spec}")
    print(f"questions: {len(qids)} | sections: {len(sections)} | section refs: {len(flat)}")
    for n in notes:
        print(f"  OK   {n}")
    for w in warns:
        print(f"  WARN {w}")
    for f in fails:
        print(f"  FAIL {f}")
    if fails:
        print(f"\nRESULT: {len(fails)} failure(s), {len(warns)} warning(s)")
        return 1
    print(f"\nRESULT: OK ({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
