#!/usr/bin/env python3
"""Create a Formbricks survey from a spec JSON, enable zh-TW/en-US languages
(zh-TW default), publish it, and write the survey id back into the spec.

Usage: python3 create_survey_from_spec.py <spec.json>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survey_lib as L


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    if spec.get("survey_id"):
        print(f"spec already has survey_id={spec['survey_id']} — skipping creation "
              "(delete the field to force a new survey)")
        return spec["survey_id"]

    data = L.create_survey(spec)
    sid = data["id"]
    spec["survey_id"] = sid
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    # snapshot + ensure published
    cur = L.api(f"/api/v1/management/surveys/{sid}", key=L.load_key())["data"]
    if cur.get("status") != "inProgress":
        cur = L.update_survey_status(sid)

    res = spec.get("results", {})
    if res.get("result_dir"):
        os.makedirs(res["result_dir"], exist_ok=True)
        with open(os.path.join(res["result_dir"], "survey_definition.json"), "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)

    print(f"survey created: {sid}")
    print(f"  name: {spec['name']}")
    print(f"  status: {cur.get('status')} | questions: {len(cur.get('questions') or [])}")
    print(f"  link: {L.API}/s/{sid}  (?lang=en-US for English)")
    print(f"  spec updated: {spec_path}")
    return sid


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
