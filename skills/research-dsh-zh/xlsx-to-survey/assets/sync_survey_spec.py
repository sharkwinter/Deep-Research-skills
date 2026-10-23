#!/usr/bin/env python3
"""Sync a spec JSON with the live Formbricks survey (structure-aware).

Two modes:

  (1) Snyc an existing spec to its live survey (after structural edits):
        python3 sync_survey_spec.py <spec.json>
      - Rebuilds spec["questions"] from the live survey (type, headlines,
        subheaders, required, choices, other flag, placeholders, maxSelections).
      - Refits sections: keeps each section's existing question refs that still
        exist (in live order); appends any NEW live questions not already
        referenced to the last section (with a note). Removed questions drop out.
      - Preserves: survey_id, name, welcome/ending, results, slug, section titles.

  (2) Generate a spec from a spec-less live survey:
        python3 sync_survey_spec.py --from-live <surveyId> <out.json>
      - Infers a single "調研問卷 / Survey" section containing all questions.
        Edit the section titles/extras afterwards as needed.

After syncing, re-run export_survey_results2.py to refresh the results page.
The exporter reads question TEXT/choices from the live API, so syncing is only
needed when the survey STRUCTURE changed (added/removed/reordered questions or
changed a question type).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survey_lib as L

TYPE_MAP = {"openText": "open", "multipleChoiceSingle": "single",
            "multipleChoiceMulti": "multi", "cta": "cta"}
TYPE_LABEL = {"open": "openText", "single": "multipleChoiceSingle", "multi": "multipleChoiceMulti"}


def plain(v):
    return re.sub(r"<[^>]+>", "", v or "").strip()


def spec_question(q):
    """Build a spec question entry from a live survey question."""
    t = TYPE_MAP.get(q["type"], "open")
    headline = (q.get("headline") or {})
    subheader = (q.get("subheader") or {})
    out = {
        "id": q["id"],
        "type": t,
        "required": bool(q.get("required")),
        "headline_zh": plain(headline.get("zh-TW") or headline.get("default")),
        "headline_en": plain(headline.get("en-US") or ""),
    }
    if t == "cta":
        return out          # 提示卡只有標題，無選項、無答案
    if subheader.get("zh-TW") or subheader.get("en-US") or subheader.get("default"):
        out["subheader_zh"] = plain(subheader.get("zh-TW") or subheader.get("default"))
        out["subheader_en"] = plain(subheader.get("en-US") or "")
    if t == "open":
        out["long_answer"] = bool(q.get("longAnswer", True))
        if q.get("inputType") == "number":
            out["numeric"] = True
            out["long_answer"] = False
        ph = (q.get("placeholder") or {})
        if ph.get("zh-TW") or ph.get("en-US") or ph.get("default"):
            out["placeholder_zh"] = plain(ph.get("zh-TW") or ph.get("default"))
            out["placeholder_en"] = plain(ph.get("en-US") or "")
    else:
        choices, has_other, other_label = [], False, {}
        for c in q.get("choices", []):
            if c.get("id") == "other":
                has_other = True
                other_label = c.get("label") or {}
                continue
            lab = c.get("label") or {}
            choices.append({"zh": plain(lab.get("zh-TW") or lab.get("default")),
                            "en": plain(lab.get("en-US") or "")})
        out["choices"] = choices
        if has_other:
            out["other"] = True
            out["other_label_zh"] = plain(other_label.get("zh-TW") or other_label.get("default")) or "其他（請說明）"
            out["other_label_en"] = plain(other_label.get("en-US") or "") or "Other (please specify)"
            oph = (q.get("otherOptionPlaceholder") or {})
            out["other_placeholder_zh"] = plain(oph.get("zh-TW") or oph.get("default")) or "請說明"
            out["other_placeholder_en"] = plain(oph.get("en-US") or "") or "Please specify"
        # maxSelections
        for r in ((q.get("validation") or {}).get("rules") or []):
            if r.get("type") == "maxSelections":
                out["max_selections"] = r.get("params", {}).get("max")
    return out


def sync_spec(path):
    spec = json.load(open(path, encoding="utf-8"))
    sid = spec.get("survey_id")
    if not sid:
        raise SystemExit(f"{path} has no survey_id — can't sync to a live survey")
    live = L.api(f"/api/v1/management/surveys/{sid}", key=L.load_key())["data"]
    live_q = {q["id"]: q for q in live["questions"]}
    live_order = [q["id"] for q in live["questions"]]

    # 1) rebuild questions
    spec["questions"] = [spec_question(live_q[i]) for i in live_order]

    # 2) refit sections
    existing_refs = {}
    for sec in spec.get("sections", []):
        existing_refs[id(sec)] = [q for q in sec.get("questions", []) if q in live_q]
    seen = set()
    for sec in spec.get("sections", []):
        sec["questions"] = [q for q in live_order if q in existing_refs[id(sec)]]
        seen.update(sec["questions"])
    new_ids = [q for q in live_order if q not in seen]
    if new_ids:
        (spec["sections"] or [])[-1].setdefault("questions", []).extend(new_ids)
        print(f"  ⚠ 新增题目已并入最后一个分节: {new_ids}（如需调整请手工移动）")
    if not spec.get("sections"):
        spec["sections"] = [{"title_zh": "調研問卷", "title_en": "Survey", "questions": live_order}]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"✓ 已同步 {path}")
    print(f"  questions: {len(spec['questions'])} | sections: {len(spec.get('sections', []))}")
    for sec in spec.get("sections", []):
        print(f"    {sec.get('title_zh')}: {len(sec.get('questions', []))} 题")


def from_live(sid, out):
    live = L.api(f"/api/v1/management/surveys/{sid}", key=L.load_key())["data"]
    qs = [spec_question(q) for q in live["questions"]]
    spec = {
        "survey_id": sid,
        "slug": f"survey-{sid[:8]}",
        "name": live.get("name") or "問卷",
        "name_en": "",
        "welcome": {"headline_zh": "", "headline_en": ""},
        "ending": {"headline_zh": "", "headline_en": ""},
        "sections": [{"title_zh": "調研問卷", "title_en": "Survey", "questions": [q["id"] for q in qs]}],
        "questions": qs,
        "results": {
            "static_name": f"survey_{sid[:8]}_results.html",
            "result_dir": f"/root/Working/polling/polls/macao/result/{sid[:8]}",
            "title_zh": live.get("name") or "問卷結果",
            "title_en": "",
        },
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"✓ 已生成 spec: {out}  ({len(qs)} 题，单个分节)")
    print("  请检查 title_zh/title_en、results 及分节，然后 run export_survey_results2.py")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--from-live":
        from_live(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2:
        sync_spec(sys.argv[1])
    else:
        raise SystemExit(__doc__)
