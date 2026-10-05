#!/usr/bin/env python3
"""Submit / verify / delete survey responses through a management API.

Companion to the `survey-backfill` skill (Step 6-8). Dependency-free (urllib).

Usage:
  submit_responses.py list   --base URL --key-file F --survey-id SID [--limit 50]
  submit_responses.py pilot  --base URL --key-file F --payloads P [--index 0]
  submit_responses.py bulk   --base URL --key-file F --payloads P [--start 0] [--json-out F]
  submit_responses.py verify --base URL --key-file F --survey-id SID [--expect N] [--summary]
  submit_responses.py delete --base URL --key-file F --response-id RID

Payload file format (JSON array):
  [{"page": 1, "respondent": "NAME",
    "body": {"surveyId": "...", "workspaceId": "...", "finished": true,
             "data": {"<questionId>": "<value>"}}}, ...]

The API key is read from --key-file: a raw key file, or a KEY=VALUE file (.env).
With --key-name the named variable is used; otherwise the first value that looks
like an API key (fbk_... or *API_KEY* variable) is taken. The key is never printed.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

DEFAULT_KEY_RE = re.compile(r"^(?:fbk_|[A-Za-z0-9_]*API_KEY$)")


def read_key(path, name=None):
    """Pick the API key. Priority: --key-name, then a value starting with fbk_
    (Formbricks), then the first *API_KEY* variable — a .env may hold several
    service keys and the wrong one yields HTTP 401."""
    text = open(path, encoding="utf-8").read()
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        pairs.append((k.strip(), v.strip().strip('"').strip("'")))
    if name:
        for k, v in pairs:
            if k == name:
                print(f"[key] using variable {k} from {path}", file=sys.stderr)
                return v
        raise SystemExit(f"ERROR: variable {name} not found in {path}")
    for k, v in pairs:
        if v.startswith("fbk_"):
            print(f"[key] using variable {k} from {path}", file=sys.stderr)
            return v
    for k, v in pairs:
        if DEFAULT_KEY_RE.match(k):
            print(f"[key] using variable {k} from {path}", file=sys.stderr)
            return v
    raw = text.strip()
    if raw and "=" not in raw and "\n" not in raw:
        return raw
    raise SystemExit(f"ERROR: no API key found in {path} "
                     f"(pass --key-name to pick a variable explicitly)")


def call(method, url, key=None, body=None, timeout=30):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if key:
        req.add_header("X-API-KEY", key)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def fetch_all(base, key, sid, limit=50):
    out, skip = [], 0
    while True:
        st, d = call("GET", f"{base}/api/v1/management/responses"
                             f"?surveyId={sid}&limit={limit}&skip={skip}", key)
        if st != 200 or not isinstance(d, dict):
            raise SystemExit(f"ERROR: list failed HTTP {st}: {str(d)[:200]}")
        page = d.get("data") or []
        if not page:
            break
        out.extend(page)
        skip += len(page)
        if len(page) < limit:
            break
    return out


def is_number(v):
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", str(v).replace(",", "").replace("，", "")))


def cmd_list(a):
    key = read_key(a.key_file, a.key_name)
    rs = fetch_all(a.base, key, a.survey_id)
    print(f"responses: {len(rs)}")
    for r in rs:
        print(" ", r["id"], r.get("createdAt", ""), "finished" if r.get("finished") else "partial",
              json.dumps(r.get("data", {}), ensure_ascii=False)[:100])


def cmd_pilot(a):
    key = read_key(a.key_file, a.key_name)
    payloads = json.load(open(a.payloads, encoding="utf-8"))
    p = payloads[a.index]
    st, d = call("POST", f"{a.base}/api/v1/management/responses", key, p["body"])
    if st != 200:
        raise SystemExit(f"PILOT FAILED HTTP {st}: {json.dumps(d, ensure_ascii=False)[:400]}")
    rid = d["data"]["id"]
    print(f"PILOT OK  page={p.get('page')}  respondent={p.get('respondent')}  id={rid}")
    print(json.dumps(d["data"]["data"], ensure_ascii=False, indent=1))
    print(f"\nRead back:  {sys.argv[0]} verify --base {a.base} --key-file {a.key_file} "
          f"--survey-id {a.body_sid or '<surveyId>'}")
    print(f"Clean up:   {sys.argv[0]} delete --base {a.base} --key-file {a.key_file} --response-id {rid}")


def cmd_bulk(a):
    key = read_key(a.key_file, a.key_name)
    payloads = json.load(open(a.payloads, encoding="utf-8"))
    ok, fails = 0, []
    for i, p in enumerate(payloads):
        if i < a.start:
            continue
        if a.dry_run:
            print(f"[dry-run] p{p.get('page')} {p.get('respondent')}: "
                  f"{len(p['body'].get('data', {}))} fields")
            continue
        st, d = call("POST", f"{a.base}/api/v1/management/responses", key, p["body"])
        if st == 200:
            ok += 1
            print(f"p{p.get('page'):02} {p.get('respondent')}: OK {d['data']['id']}")
        else:
            msg = json.dumps(d, ensure_ascii=False)[:200]
            fails.append({"page": p.get("page"), "error": msg})
            print(f"p{p.get('page'):02} {p.get('respondent')}: FAIL {msg}")
    print(f"\nsubmitted OK: {ok}, failed: {len(fails)}")
    if fails and a.json_out:
        json.dump(fails, open(a.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"failures written to {a.json_out}")


def cmd_verify(a):
    key = read_key(a.key_file, a.key_name)
    rs = fetch_all(a.base, key, a.survey_id)
    total = len(rs)
    done = sum(1 for r in rs if r.get("finished"))
    print(f"responses: {total} (finished {done}, partial {total - done})")
    if a.expect is not None:
        print("EXPECTED", a.expect, "->", "OK" if total == a.expect else "MISMATCH")
    if not a.summary:
        return
    keys = {}
    for r in rs:
        for k, v in (r.get("data") or {}).items():
            keys.setdefault(k, []).append(v)
    print("\nper-question answered:")
    for k, vals in keys.items():
        nums = [float(v) for v in vals if is_number(v)]
        extra = ""
        if nums and len(nums) == len(vals):
            extra = f"  mean {round(sum(nums) / len(nums), 2)}  sum {round(sum(nums), 2)}"
        print(f"  {k:32} {len(vals)}/{total}{extra}")


def cmd_delete(a):
    key = read_key(a.key_file, a.key_name)
    st, d = call("DELETE", f"{a.base}/api/v1/management/responses/{a.response_id}", key)
    print("deleted" if st == 200 else f"HTTP {st}: {str(d)[:200]}", a.response_id)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=None, help="platform base URL, e.g. http://host:port")
    ap.add_argument("--key-file", default=None, help="file holding the API key (.env or raw)")
    ap.add_argument("--key-name", default=None, help="variable name inside --key-file")
    # Accept the same three options after the subcommand too (SUPPRESS = don't clobber
    # values given before the subcommand).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base", default=argparse.SUPPRESS)
    common.add_argument("--key-file", default=argparse.SUPPRESS)
    common.add_argument("--key-name", default=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", parents=[common]); p.add_argument("--survey-id", required=True); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("pilot", parents=[common])
    p.add_argument("--payloads", required=True); p.add_argument("--index", type=int, default=0)
    p.add_argument("--body-sid", default=None); p.set_defaults(fn=cmd_pilot)
    p = sub.add_parser("bulk", parents=[common])
    p.add_argument("--payloads", required=True); p.add_argument("--start", type=int, default=0)
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--json-out", default=None)
    p.set_defaults(fn=cmd_bulk)
    p = sub.add_parser("verify", parents=[common])
    p.add_argument("--survey-id", required=True); p.add_argument("--expect", type=int, default=None)
    p.add_argument("--summary", action="store_true"); p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("delete", parents=[common]); p.add_argument("--response-id", required=True); p.set_defaults(fn=cmd_delete)

    a = ap.parse_args()
    if not getattr(a, "base", None) or not getattr(a, "key_file", None):
        ap.error("--base and --key-file are required (before or after the subcommand)")
    a.base = a.base.rstrip("/")
    a.fn(a)


if __name__ == "__main__":
    main()
