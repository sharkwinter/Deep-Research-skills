#!/usr/bin/env python3
"""Shared library: build Formbricks surveys from JSON specs, call the v1 API,
and manage survey languages (SQL — v1 API cannot accept ZLanguage date fields).

Spec schema (see skills/xlsx-to-survey/SKILL.md):
{
  "survey_id": null,                  # filled in after creation
  "name": "...", "name_en": "...",
  "welcome": {"headline_zh","headline_en","subheader_zh","subheader_en","button_zh","button_en"},
  "ending":  {"headline_zh","headline_en","subheader_zh","subheader_en"},
  "sections": [{"title_zh","title_en","questions":[qid...]}],
  "questions": [
    {"id","type":"open|single|multi","required",
     "headline_zh","headline_en","subheader_zh","subheader_en",
     "placeholder_zh","placeholder_en","long_answer",
     "choices":[{"zh","en"}],"other","other_placeholder_zh","other_placeholder_en",
     "max_selections"}
  ],
  "results": {"static_name","result_dir","title_zh","title_en"}
}
"""
import json
import os
import subprocess
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 可移植設定。本檔是 repo 內的可移植版本；參考部署仍以 deploy/ 內同名檔為準
# （deploy 版把所有值寫死，兩者行為在預設值下一致）。
#
# 設定來源，優先序由高到低：
#   1. 環境變數  SURVEY_API_BASE / SURVEY_WORKSPACE_ID / SURVEY_API_KEY
#               SURVEY_DEPLOY_DIR / SURVEY_DB_CONTAINER / SURVEY_DB_NAME
#   2. 設定檔    $SURVEY_CONFIG 指向的 .env，否則 assets/.env（KEY=VALUE）
#   3. 內建預設  僅 SURVEY_DEPLOY_DIR 沒預設（未設時 SQL/redis 功能會提示）
#
# 舊變數名 MACAO_API_KEY 仍相容。
# ---------------------------------------------------------------------------
def _load_settings_file():
    path = os.environ.get("SURVEY_CONFIG") or os.path.join(HERE, ".env")
    if not os.path.isfile(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


SETTINGS = _load_settings_file()


def _cfg(name, default=None):
    return os.environ.get(name) or SETTINGS.get(name) or default


API = (_cfg("SURVEY_API_BASE", "http://localhost")).rstrip("/")
WORKSPACE_ID = _cfg("SURVEY_WORKSPACE_ID", "cmth1r8g1000101ql8rcdp3it")
BRAND_COLOR = _cfg("SURVEY_BRAND_COLOR", "#CF0A2C")
# docker compose 專案目錄（SQL / redis 操作需要）
DEPLOY_DIR = _cfg("SURVEY_DEPLOY_DIR", HERE)
DB_CONTAINER = _cfg("SURVEY_DB_CONTAINER", "postgres")
DB_NAME = _cfg("SURVEY_DB_NAME", "formbricks")


# ---------- API ----------
def load_key():
    k = (os.environ.get("SURVEY_API_KEY") or os.environ.get("MACAO_API_KEY")
         or SETTINGS.get("SURVEY_API_KEY") or SETTINGS.get("MACAO_API_KEY"))
    if k:
        return k
    for line in open(os.path.join(HERE, ".env")):
        if line.startswith("MACAO_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no API key: set SURVEY_API_KEY (or MACAO_API_KEY), or put it in "
                     "$SURVEY_CONFIG / assets/.env")


def api(path, method="GET", body=None, key=None):
    key = key or load_key()
    r = urllib.request.Request(
        f"{API}{path}", method=method,
        headers={"x-api-key": key, "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        return json.load(urllib.request.urlopen(r, timeout=60))
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:800]
        raise RuntimeError(f"API {method} {path} -> HTTP {e.code}: {detail}") from e


def psql(sql):
    """Run SQL inside the postgres container (stdin; avoids shell quoting)."""
    return subprocess.run(
        ["docker", "compose", "exec", "-T", DB_CONTAINER, "psql", "-U", "postgres", "-d", DB_NAME],
        input=sql, capture_output=True, text=True, cwd=DEPLOY_DIR, timeout=60)


def flush_redis():
    subprocess.run(["docker", "compose", "exec", "-T", "redis", "redis-cli", "FLUSHALL"],
                   cwd=DEPLOY_DIR, capture_output=True, timeout=30)


def set_survey_languages(survey_id, default_code="zh-TW", codes=("zh-TW", "en-US")):
    """Insert SurveyLanguage rows (v1 API can't serialize ZLanguage dates)."""
    code_list = ",".join(f"'{c}'" for c in codes)
    sql = (
        f'INSERT INTO "SurveyLanguage" ("languageId","surveyId","default","enabled") '
        f'SELECT l.id, \'{survey_id}\', (l.code=\'{default_code}\'), true '
        f'FROM "Language" l WHERE l."workspaceId"=\'{WORKSPACE_ID}\' AND l.code IN ({code_list}) '
        f'ON CONFLICT DO NOTHING;'
    )
    r = psql(sql)
    if r.returncode != 0:
        raise RuntimeError(f"SurveyLanguage insert failed: {r.stderr}")
    return r.stdout


# ---------- i18n helpers ----------
def hl_html(text):
    return ('<p class="fb-editor-paragraph"><b><strong class="fb-editor-text-bold" style="">'
            f"{text}</strong></b></p>")


def sub_html(text):
    """Plain subheader; \n -> <br>."""
    return ('<p class="fb-editor-paragraph"><span style="">'
            f"{text.replace(chr(10), '<br>')}</span></p>")


def i18n(zh, en, wrapper=lambda t: t):
    return {"default": wrapper(zh), "zh-TW": wrapper(zh), "en-US": wrapper(en)}


TYPE_MAP = {"open": "openText", "single": "multipleChoiceSingle",
            "multi": "multipleChoiceMulti", "cta": "cta"}


def build_question(q):
    t = TYPE_MAP[q["type"]]
    out = {
        "id": q["id"],
        "type": t,
        "headline": i18n(q["headline_zh"], q["headline_en"], hl_html),
        "required": bool(q.get("required")),
        "backButtonLabel": i18n("上一步", "Back"),
    }
    if t == "cta":
        # 提示卡（感謝／提交卡）：不收集答案，只有標題
        out["required"] = False
        return out
    if q.get("subheader_zh") or q.get("subheader_en"):
        out["subheader"] = i18n(q.get("subheader_zh", ""), q.get("subheader_en", ""), sub_html)
    if t == "openText":
        numeric = bool(q.get("numeric"))
        out["inputType"] = "number" if numeric else "text"
        out["longAnswer"] = bool(q.get("long_answer", True)) and not numeric
        out["charLimit"] = {"enabled": False}
        if q.get("placeholder_zh") or q.get("placeholder_en"):
            out["placeholder"] = i18n(q.get("placeholder_zh", ""), q.get("placeholder_en", ""))
        if numeric:
            # Server-side enforcement: Formbricks only adds implicit rules for
            # email/url/phone — inputType "number" needs an explicit pattern rule.
            out["validation"] = {"logic": "and", "rules": [{
                "id": f"rule_num_{q['id']}",
                "type": "pattern",
                "params": {"pattern": r"^-?\d+(\.\d+)?$"},
            }]}
    else:
        choices = []
        for i, c in enumerate(q.get("choices", []), 1):
            choices.append({"id": f"{q['id']}_c{i}", "label": i18n(c["zh"], c["en"])})
        if q.get("other"):
            # 可自訂 other 標籤：問卷把「精確填寫」等追問折進母題的 other 選項時需要
            choices.append({"id": "other", "label": i18n(
                q.get("other_label_zh", "其他（請說明）"),
                q.get("other_label_en", "Other (please specify)"))})
            out["otherOptionPlaceholder"] = i18n(
                q.get("other_placeholder_zh", "請說明"), q.get("other_placeholder_en", "Please specify"))
        out["choices"] = choices
        rules = []
        if q.get("max_selections"):
            rules.append({"id": f"rule_max_{q['id']}", "type": "maxSelections",
                          "params": {"max": q["max_selections"]}})
        out["validation"] = {"logic": "and", "rules": rules}
    return out


def build_survey_body(spec):
    welcome = spec.get("welcome", {})
    ending = spec.get("ending", {})
    body = {
        "workspaceId": WORKSPACE_ID,
        "name": spec["name"],
        "type": "link",
        "status": "inProgress",
        "showLanguageSwitch": True,
        "displayOption": "displayOnce",
        "recontactDays": 0,
        "autoClose": None,
        "closeOn": None,
        "delay": 0,
        "displayLimit": None,
        "runOnDate": None,
        "styling": {
            "brandColor": {"light": BRAND_COLOR},
            "isLogoHidden": False,
            "hideProgressBar": False,
        },
        "questions": [build_question(q) for q in spec["questions"]],
        "welcomeCard": {
            "enabled": bool(welcome.get("headline_zh")),
            "headline": i18n(welcome.get("headline_zh", ""), welcome.get("headline_en", ""), hl_html),
            "subheader": i18n(welcome.get("subheader_zh", ""), welcome.get("subheader_en", ""), sub_html),
            "buttonLabel": i18n(welcome.get("button_zh", "開始填寫"), welcome.get("button_en", "Start")),
            "timeToFinish": True,
            "showResponseCount": False,
        },
        "endings": [{
            "id": "ck8f2m1q0v3x7z9a4b6d5e8f",
            "type": "endScreen",
            "headline": i18n(ending.get("headline_zh", "感謝您的填寫！"),
                             ending.get("headline_en", "Thank you!"), hl_html),
            "subheader": i18n(ending.get("subheader_zh", ""), ending.get("subheader_en", ""), sub_html),
        }] if (ending.get("headline_zh") or ending.get("headline_en")) else [],
        "hiddenFields": {"enabled": False},
        "variables": [],
        "triggers": [],
    }
    return body


def create_survey(spec):
    """POST spec -> new survey; set languages; return survey data dict."""
    key = load_key()
    body = build_survey_body(spec)
    res = api("/api/v1/management/surveys", "POST", body, key)
    sid = res["data"]["id"]
    set_survey_languages(sid)
    flush_redis()
    return res["data"]


def psql_value(sql):
    """Run SQL, return the single scalar value (tuples-only, unaligned)."""
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", DB_CONTAINER, "psql", "-U", "postgres",
         "-d", DB_NAME, "-t", "-A", "-c", sql],
        capture_output=True, text=True, cwd=DEPLOY_DIR, timeout=60)
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def get_survey_logo(survey):
    """Survey styling logo first, then workspace logo (DB), else None.
    Returns a relative /storage/... URL usable same-origin by the web pages."""
    logo = (survey.get("styling") or {}).get("logo")
    if isinstance(logo, dict) and logo.get("url"):
        return logo["url"]
    if isinstance(logo, str) and logo:
        return logo
    ws = psql_value(f"select coalesce(logo->>'url','') from \"Workspace\" where id='{survey['workspaceId']}'")
    if ws:
        return ws
    return None


def update_survey_status(sid, status="inProgress"):
    """Flip status via blocks-only PUT (v1 rejects questions+blocks together)."""
    key = load_key()
    s = api(f"/api/v1/management/surveys/{sid}", key=key)["data"]
    s["status"] = status
    body = dict(s)
    body.pop("languages", None)
    if body.get("blocks"):
        body.pop("questions", None)
    res = api(f"/api/v1/management/surveys/{sid}", "PUT", body, key)
    flush_redis()
    return res["data"]
