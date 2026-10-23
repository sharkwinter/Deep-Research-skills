#!/usr/bin/env python3
"""Export a spec-based survey's RESULTS to (1) a single-page HTML report served
from deploy/static/, and (2) raw data (responses.csv, results.json) + an HTML
copy under the spec's result_dir.

Works for any survey created via create_survey_from_spec.py (spec-driven:
sections/question types come from the spec; live labels come from the API).

Usage: python3 export_survey_results2.py <spec.json>
"""
import csv
import html as htmlmod
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survey_lib as L

TZ = timezone(timedelta(hours=8))
PALETTE = ["#CF0A2C", "#F97316", "#F59E0B", "#CA8A04", "#65A30D", "#0D9488",
           "#0891B2", "#2563EB", "#6366F1", "#A855F7", "#DB2777", "#64748B"]
TYPE_LABEL_ZH = {"single": "單選", "multi": "多選", "open": "開放填寫", "cta": "提示卡"}

# 高校问卷的题干里嵌入了分节名（如「第一部分：高校基本資訊學校名稱」）；
# 结果页本身按分节渲染，剥离该前缀避免重复
SECTION_PREFIX_RE = re.compile(r"^第[一二三四五六七八九十\d]+部分[：:][^，。]{2,30}?(?=學校|當前|如有|您的|如果|基於|考慮)")


def strip_section_prefix(text):
    return SECTION_PREFIX_RE.sub("", text).strip()


def strip_rich(v):
    if not isinstance(v, str):
        return ""
    t = re.sub(r"<br\s*/?>", "\n", v)
    t = re.sub(r"</p>|</li>|</ul>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmlmod.unescape(t)
    return "\n".join(x.strip() for x in t.split("\n") if x.strip())


def esc(s):
    return htmlmod.escape(str(s))


def fetch(spec):
    key = L.load_key()
    sid = spec["survey_id"]
    survey = L.api(f"/api/v1/management/surveys/{sid}", key=key)["data"]
    responses = L.api(f"/api/v1/management/responses?surveyId={sid}&limit=1000", key=key)["data"]
    return survey, responses


def normalize_survey(sid):
    """Mirror survey `default` -> zh-TW slot (editor edits land in `default`;
    the respondent page reads zh-TW). Idempotent; PUTs blocks-only if changed.
    Returns True if anything was changed."""
    key = L.load_key()
    import sync_survey_languages as syncer
    s = L.api(f"/api/v1/management/surveys/{sid}", key=key)["data"]
    changes = syncer.sync(s)
    if not changes:
        return False
    body = dict(s)
    body.pop("languages", None)
    if body.get("blocks"):
        body.pop("questions", None)
    L.api(f"/api/v1/management/surveys/{sid}", "PUT", body, key)
    L.flush_redis()
    return True


def fetch(spec):
    key = L.load_key()
    sid = spec["survey_id"]
    normalize_survey(sid)
    survey = L.api(f"/api/v1/management/surveys/{sid}", key=key)["data"]
    responses = L.api(f"/api/v1/management/responses?surveyId={sid}&limit=1000", key=key)["data"]
    return survey, responses


def build_model(spec, survey, responses):
    qmap = {q["id"]: q for q in survey["questions"]}
    spec_q = {q["id"]: q for q in spec["questions"]}

    lut = {}
    for q in survey["questions"]:
        for c in q.get("choices", []):
            lab = c.get("label") or {}
            zh = strip_rich(lab.get("zh-TW") or lab.get("default") or "")
            en = strip_rich(lab.get("en-US") or "")
            for v in {zh, en}:
                if v:
                    lut[v] = (zh, en)

    n_total = len(responses)
    n_done = sum(1 for r in responses if r.get("finished"))
    sections = []
    for sec in spec["sections"]:
        items = []
        for qid in sec["questions"]:
            q = qmap.get(qid)
            if not q:
                continue
            stype = spec_q.get(qid, {}).get("type", "open")
            counts, answers, answered = {}, [], 0
            for r in responses:
                v = (r.get("data") or {}).get(qid)
                if v is None or v == "":
                    continue
                answered += 1
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if not isinstance(x, str):
                        x = str(x)
                    counts[x] = counts.get(x, 0) + 1
                if stype == "open":
                    answers.append({
                        "text": "\n".join(str(x) for x in vals),
                        "at": (r.get("createdAt") or "")[:16].replace("T", " "),
                        "finished": bool(r.get("finished")),
                    })
            item = {
                "id": qid, "type": stype, "required": q.get("required", False),
                "zh": strip_section_prefix(strip_rich((q.get("headline") or {}).get("zh-TW")
                                 or (q.get("headline") or {}).get("default") or "")),
                "en": strip_rich((q.get("headline") or {}).get("en-US") or ""),
                "answered": answered, "answers": answers, "rows": [], "others": [],
                "hist": [],
            }
            if stype == "open":
                # Histogram of free-text answers: group identical texts; if every
                # distinct value is a pure number, sort ascending by numeric value,
                # otherwise sort by frequency (most common first).
                distinct = {}
                for r in responses:
                    v = (r.get("data") or {}).get(qid)
                    if v is None or v == "":
                        continue
                    for x in ([v] if not isinstance(v, list) else v):
                        x = str(x).strip()
                        if x:
                            distinct[x] = distinct.get(x, 0) + 1
                items_hist = [{"text": k, "cnt": c} for k, c in distinct.items()]

                def _is_number(s):
                    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", s.replace(",", "").replace("，", "")))

                is_numeric = bool(items_hist) and all(_is_number(h["text"]) for h in items_hist)
                if is_numeric:
                    items_hist.sort(key=lambda h: float(h["text"].replace(",", "").replace("，", "")))
                    tot_n = sum(h["cnt"] for h in items_hist)
                    if tot_n:
                        item["sum"] = sum(float(h["text"].replace(",", "").replace("，", "")) * h["cnt"]
                                          for h in items_hist)
                        item["mean"] = item["sum"] / tot_n
                else:
                    items_hist.sort(key=lambda h: -h["cnt"])
                item["hist"] = items_hist
            if stype != "open":
                rows, seen = [], set()
                for c in q.get("choices", []):
                    lab = c.get("label") or {}
                    zh = strip_rich(lab.get("zh-TW") or lab.get("default") or "")
                    en = strip_rich(lab.get("en-US") or "")
                    if c.get("id") == "other":
                        # count matched free-text under "other" label itself
                        rows.append({"zh": zh, "en": en, "cnt": counts.get(zh, 0), "stale": False})
                    else:
                        rows.append({"zh": zh, "en": en,
                                     "cnt": counts.get(zh, 0) + counts.get(en, 0), "stale": False})
                    seen.update({zh, en})
                for lab, cnt in sorted(counts.items(), key=lambda kv: -kv[1]):
                    if lab in seen:
                        continue
                    if lab in lut:
                        zh, en = lut[lab]
                        rows.append({"zh": zh, "en": "" if en == zh else en, "cnt": cnt, "stale": True})
                    else:
                        item["others"].append(lab)
                item["rows"] = rows
            items.append(item)
        sections.append((sec, items))
    return sections, n_total, n_done


def build_html(spec, sections, n_total, n_done, latest_str, now_str, logo_url=None):
    R = spec["results"]
    title_zh, title_en = R.get("title_zh", spec["name"]), R.get("title_en", spec.get("name_en", ""))
    parts = [f"""<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title_zh)} 結果 / Results</title>
<style>
  :root {{ --red:#CF0A2C; --grey:#666; --line:#eee; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:"Microsoft JhengHei","PingFang TC","Noto Sans TC",sans-serif;
         margin:0; color:#222; background:#fafafa; }}
  .wrap {{ max-width:860px; margin:0 auto; padding:32px 20px 80px; }}
  header {{ text-align:center; padding:24px 0 4px; }}
  header img {{ height:56px; }}
  h1 {{ color:var(--red); font-size:26px; margin:14px 0 4px; }}
  .sub {{ color:var(--grey); font-size:15px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:12px; justify-content:center; margin:18px 0 6px; }}
  .stat {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:10px 18px; min-width:120px; }}
  .stat .v {{ font-size:22px; font-weight:700; color:var(--red); }}
  .stat .k {{ font-size:11.5px; color:var(--grey); }}
  .meta {{ color:#999; font-size:12px; margin-top:10px; }}
  h2 {{ color:var(--red); font-size:17px; border-bottom:2px solid var(--red);
        padding-bottom:6px; margin:44px 0 4px; }}
  h2 .en {{ color:var(--grey); font-size:12px; font-weight:400; }}
  .q {{ background:#fff; border:1px solid var(--line); border-radius:10px;
        padding:18px 20px; margin:14px 0; page-break-inside:avoid; }}
  .q h3 {{ margin:0 0 2px; font-size:15.5px; }}
  .q .en {{ color:var(--grey); font-size:12.5px; font-style:italic; margin:0 0 4px; }}
  .q .info {{ font-size:11.5px; color:var(--grey); margin:2px 0 10px; }}
  .q .info span {{ background:#f4e6e9; color:var(--red); border-radius:4px; padding:1px 7px; margin-right:4px; }}
  .toggle {{ position:sticky; top:0; z-index:20; display:flex; justify-content:center; gap:10px;
             padding:12px 0 10px; background:rgba(250,250,250,.96); }}
  .toggle button {{ border:1px solid var(--line); background:#fff; border-radius:20px; padding:6px 20px;
                    font-size:13px; cursor:pointer; color:#555; font-family:inherit; }}
  .toggle button:hover {{ border-color:var(--red); color:var(--red); }}
  .toggle button.on {{ background:var(--red); color:#fff; border-color:var(--red); }}
  body.view-bar .chart-pie {{ display:none; }}
  body.view-pie .chart-bar {{ display:none; }}
  body.view-bar .only-pie {{ display:none; }}
  body.view-pie .only-bar {{ display:none; }}
  .row {{ display:flex; align-items:center; gap:10px; margin:7px 0; }}
  .lab {{ width:46%; font-size:13.5px; line-height:1.35; }}
  .lab .en {{ color:var(--grey); font-size:11.5px; font-style:italic; }}
  .lab .stale {{ color:#b8860b; font-size:10.5px; }}
  .bar {{ flex:1; height:18px; background:#f4f4f5; border-radius:4px; overflow:hidden; }}
  .fill {{ height:100%; background:var(--red); border-radius:4px; min-width:2px; }}
  .fill.mt {{ background:#d9a0ac; }}
  .cnt {{ width:88px; text-align:right; font-size:12.5px; color:#444; white-space:nowrap; }}
  .chart-pie {{ display:flex; gap:24px; align-items:center; flex-wrap:wrap; }}
  .pie {{ width:160px; height:160px; border-radius:50%; position:relative; flex:none;
          border:1px solid var(--line); cursor:crosshair; }}
  .pie .hole {{ position:absolute; inset:23%; background:#fff; border-radius:50%;
                display:flex; align-items:center; justify-content:center; text-align:center; }}
  .hole .hn {{ font-size:20px; font-weight:700; color:var(--red); line-height:1.1; }}
  .hole .hl {{ font-size:10px; color:var(--grey); }}
  .legend {{ flex:1; min-width:230px; }}
  .lg {{ display:flex; align-items:flex-start; gap:8px; margin:4px 0; font-size:13px; line-height:1.35; }}
  .lg .dot {{ width:11px; height:11px; border-radius:3px; flex:none; margin-top:3px; }}
  .lg .num {{ margin-left:auto; white-space:nowrap; color:#555; font-size:12px; }}
  .lg.zero {{ opacity:.45; }}
  .lg.hl {{ background:#fdf2f4; border-radius:4px; padding:2px 4px; margin:2px -4px; }}
  .lg .en {{ color:var(--grey); font-size:11.5px; font-style:italic; }}
  .lg .stale {{ color:#b8860b; font-size:10.5px; }}
  .pie-note {{ width:100%; font-size:11px; color:#999; margin-top:6px; }}
  .cta-note {{ background:#f7f7f7; border-radius:6px; padding:8px 12px; font-size:12.5px; color:#555; }}
  #pieTip {{ position:fixed; z-index:99; pointer-events:none; background:#fff;
             border:1px solid var(--line); border-radius:8px; box-shadow:0 4px 14px rgba(0,0,0,.14);
             padding:8px 12px; font-size:12.5px; max-width:300px; display:none; }}
  #pieTip .t {{ display:flex; align-items:center; gap:6px; font-weight:600; line-height:1.3; }}
  #pieTip .dot {{ width:10px; height:10px; border-radius:3px; flex:none; }}
  #pieTip .n {{ color:#555; margin-top:3px; }}
  .answers {{ margin-top:4px; }}
  .ans {{ border-left:3px solid var(--red); background:#faf7f8; border-radius:0 6px 6px 0;
          padding:8px 12px; margin:8px 0; font-size:13px; white-space:pre-wrap; }}
  .ans .at {{ color:#999; font-size:11px; }}
  .ans.none {{ border-color:#ddd; color:#999; }}
  .hist {{ margin:2px 0 8px; }}
  .hist .lab {{ width:auto; flex:1.4; font-weight:600; }}
  details.raw {{ margin-top:8px; font-size:12.5px; }}
  details.raw summary {{ cursor:pointer; color:var(--red); font-weight:600; user-select:none; }}
  .others {{ background:#f7f7f7; border-radius:6px; padding:8px 12px; font-size:12.5px;
             color:#555; margin-top:10px; }}
  .others b {{ color:var(--red); font-weight:600; }}
  footer {{ text-align:center; color:#999; font-size:12px; margin-top:48px; }}
  @media print {{ body{{background:#fff}} .q{{border-color:#ddd}} h2{{margin-top:24px}} .toggle{{display:none}} }}
</style>
</head>
<body class="view-bar">
<div class="wrap">
<header>
  <img src="{esc(logo_url or '/static/huawei-logo.png')}" alt="Logo">
  <h1>{esc(title_zh)}</h1>
  <div class="sub">{esc(title_en)} — Results</div>
  <div class="stats">
    <div class="stat"><div class="v">{n_total}</div><div class="k">總回應 Responses</div></div>
    <div class="stat"><div class="v">{n_done}</div><div class="k">已完成 Finished</div></div>
    <div class="stat"><div class="v">{n_total - n_done}</div><div class="k">進行中 Partial</div></div>
  </div>
  <div class="meta">最新回應 Latest response: {esc(latest_str)}　·　報告生成 Generated: {now_str}（UTC+8）</div>
</header>
<div class="toggle">
  <button id="btnBar" class="on" onclick="setMode('bar')">條形圖 Bar</button>
  <button id="btnPie" onclick="setMode('pie')">分布圖 Distribution</button>
</div>
"""]
    num = 0
    for sec, items in sections:
        en = f' <span class="en">{esc(sec["title_en"])}</span>' if sec.get("title_en") else ""
        parts.append(f"<h2>{esc(sec['title_zh'])}{en}</h2>\n")
        for item in items:
            num += 1
            req = " <small style='color:var(--red)'>＊</small>" if item["required"] else ""
            parts.append('<div class="q">')
            parts.append(f'<h3>{num}. {esc(item["zh"])}{req}</h3>')
            if item["en"]:
                parts.append(f'<div class="en">{esc(item["en"])}</div>')
            tags = [TYPE_LABEL_ZH.get(item["type"], item["type"]),
                    f'已答 answered {item["answered"]}/{n_total}']
            if item.get("mean") is not None:
                m = item["mean"]
                mtxt = str(int(m)) if abs(m - round(m)) < 1e-9 else f"{m:.2f}".rstrip("0").rstrip(".")
                tags.append(f'均值 mean {mtxt}')
            if item.get("sum") is not None:
                s = item["sum"]
                stxt = str(int(s)) if abs(s - round(s)) < 1e-9 else f"{s:.2f}".rstrip("0").rstrip(".")
                tags.append(f'总和 sum {stxt}')
            parts.append('<div class="info">' + "".join(f"<span>{esc(t)}</span>" for t in tags) + "</div>")

            if item["type"] == "cta":
                parts.append('<div class="cta-note">※ 提示卡（不收集答案）/ Info card — no response data collected</div>')
                parts.append("</div>\n")
                continue
            if item["type"] == "open":
                if item["hist"]:
                    mx = max(r["cnt"] for r in item["hist"]) or 1
                    parts.append('<div class="hist">')
                    for r in item["hist"]:
                        w = round(r["cnt"] / mx * 100)
                        lab = esc(r["text"])
                        parts.append(
                            f'<div class="row"><div class="lab">{lab}</div>'
                            f'<div class="bar"><div class="fill" style="width:{w}%"></div></div>'
                            f'<div class="cnt">{r["cnt"]}</div></div>')
                    parts.append('</div>')
                    if item["answers"]:
                        parts.append('<details class="raw"><summary>檢視原始回答 '
                                     f'({len(item["answers"])}) / View raw answers</summary>')
                        parts.append('<div class="answers">')
                        for a in item["answers"]:
                            parts.append(f'<div class="ans">{esc(a["text"])}'
                                         f'<div class="at">{a["at"]}{" · 已完成" if a["finished"] else " · 未完成"}</div></div>')
                        parts.append('</div></details>')
                elif item["answers"]:
                    parts.append('<div class="answers">')
                    for a in item["answers"]:
                        parts.append(f'<div class="ans">{esc(a["text"])}'
                                     f'<div class="at">{a["at"]}{" · 已完成" if a["finished"] else " · 未完成"}</div></div>')
                    parts.append("</div>")
                else:
                    parts.append('<div class="ans none">暫無回答 No answers yet</div>')
            else:
                for i, r in enumerate(item["rows"]):
                    r["color"] = PALETTE[i % len(PALETTE)]
                parts.append('<div class="chart-bar">')
                mx = max([r["cnt"] for r in item["rows"]] or [1]) or 1
                for r in item["rows"]:
                    w = round(r["cnt"] / mx * 100) if r["cnt"] else 0
                    mt = " mt" if r["cnt"] == 0 else ""
                    en2 = f' <span class="en">{esc(r["en"])}</span>' if r["en"] else ""
                    stale = ' <span class="stale">（舊選項 old label）</span>' if r["stale"] else ""
                    pct = f" · {r['cnt'] / item['answered'] * 100:.0f}%" if item["answered"] else ""
                    parts.append(
                        f'<div class="row"><div class="lab">{esc(r["zh"])}{en2}{stale}</div>'
                        f'<div class="bar"><div class="fill{mt}" style="width:{w}%"></div></div>'
                        f'<div class="cnt">{r["cnt"]}{pct}</div></div>')
                parts.append("</div>")
                total_sel = sum(r["cnt"] for r in item["rows"])
                segs, acc, data = [], 0.0, []
                for i, r in enumerate(item["rows"]):
                    if r["cnt"] > 0 and total_sel > 0:
                        pct = r["cnt"] / total_sel * 100
                        segs.append(f"{r['color']} {acc:.3f}% {acc + pct:.3f}%")
                        data.append({"i": i, "zh": r["zh"], "en": r["en"], "cnt": r["cnt"],
                                     "pct": round(pct, 1), "c": r["color"],
                                     "a0": round(acc * 3.6, 2), "a1": round((acc + pct) * 3.6, 2)})
                        acc += pct
                style = f"background:conic-gradient({','.join(segs)})" if segs else "background:#f4f4f5"
                segs_attr = htmlmod.escape(json.dumps(data, ensure_ascii=False), quote=True) if data else ""
                parts.append('<div class="chart-pie">')
                parts.append(
                    f'<div class="pie" data-segs="{segs_attr}" style="{style}"><div class="hole">'
                    f'<div><div class="hn">{item["answered"]}</div><div class="hl">已答</div></div>'
                    f"</div></div>")
                parts.append('<div class="legend">')
                for i, r in enumerate(item["rows"]):
                    zero = " zero" if r["cnt"] == 0 else ""
                    en2 = f' <span class="en">{esc(r["en"])}</span>' if r["en"] else ""
                    stale = ' <span class="stale">（舊選項）</span>' if r["stale"] else ""
                    pct = f" · {r['cnt'] / total_sel * 100:.0f}%" if total_sel else ""
                    parts.append(
                        f'<div class="lg{zero}" data-i="{i}"><span class="dot" style="background:{r["color"]}"></span>'
                        f'<span>{esc(r["zh"])}{en2}{stale}</span>'
                        f'<span class="num">{r["cnt"]}{pct}</span></div>')
                parts.append("</div>")
                if item["type"] == "multi" and total_sel:
                    parts.append('<div class="pie-note">※ 多選題：分布圖扇區角度按各選項被選次數佔全部選擇次數的比例 / '
                                 'multi-select: slice size = share of total selections</div>')
                parts.append("</div>")
                if item["others"]:
                    texts = "；".join(esc(t) for t in item["others"])
                    parts.append(f'<div class="others"><b>其他（自填）Other (free text)：</b>{texts}</div>')
            parts.append("</div>\n")
    parts.append(f"""<footer>{esc(title_zh)} — 結果報告由回應數據自動生成 / auto-generated from survey responses</footer>
</div>
<script>
function setMode(m){{
  document.body.className='view-'+m;
  document.getElementById('btnBar').classList.toggle('on',m==='bar');
  document.getElementById('btnPie').classList.toggle('on',m==='pie');
  try{{localStorage.setItem('resChartMode_{esc(spec.get("slug","s"))}',m)}}catch(e){{}}
}}
try{{if(localStorage.getItem('resChartMode_{esc(spec.get("slug","s"))}')==='pie')setMode('pie')}}catch(e){{}}

var tip=document.createElement('div');tip.id='pieTip';document.body.appendChild(tip);
var lastLg=null;
function segAt(pie,ev){{
  var segs;try{{segs=JSON.parse(pie.getAttribute('data-segs'))}}catch(e){{return null}}
  if(!segs||!segs.length)return null;
  var r=pie.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2;
  var dx=ev.clientX-cx,dy=ev.clientY-cy;
  if(dx*dx+dy*dy>(r.width/2)*(r.width/2))return null;
  var ang=(Math.atan2(dx,-dy)*180/Math.PI+360)%360;
  for(var k=0;k<segs.length;k++){{
    var s=segs[k];
    if(ang>=s.a0&&(ang<s.a1||k===segs.length-1))return s;
  }}
  return segs[segs.length-1];
}}
document.querySelectorAll('.pie').forEach(function(pie){{
  pie.addEventListener('mousemove',function(ev){{
    var s=segAt(pie,ev);
    if(!s){{tip.style.display='none';if(lastLg)lastLg.classList.remove('hl');lastLg=null;return}}
    var html='<div class="t"><span class="dot" style="background:'+s.c+'"></span>'+s.zh+'</div>';
    if(s.en)html+='<div class="n" style="font-style:italic">'+s.en+'</div>';
    html+='<div class="n">'+s.cnt+' 次 · '+s.pct+'%</div>';
    tip.innerHTML=html;tip.style.display='block';
    var x=ev.clientX+14,y=ev.clientY+14;
    if(x+tip.offsetWidth>innerWidth-8)x=ev.clientX-14-tip.offsetWidth;
    if(y+tip.offsetHeight>innerHeight-8)y=ev.clientY-14-tip.offsetHeight;
    tip.style.left=x+'px';tip.style.top=y+'px';
    if(lastLg)lastLg.classList.remove('hl');
    lastLg=pie.parentElement.querySelector('.lg[data-i="'+s.i+'"]');
    if(lastLg)lastLg.classList.add('hl');
  }});
  pie.addEventListener('mouseleave',function(){{
    tip.style.display='none';
    if(lastLg){{lastLg.classList.remove('hl');lastLg=null}}
  }});
}});
</script>
</body>
</html>""")
    return "\n".join(parts)


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    if not spec.get("survey_id"):
        raise SystemExit("spec has no survey_id — run create_survey_from_spec.py first")
    survey, responses = fetch(spec)
    sections, n_total, n_done = build_model(spec, survey, responses)

    latest = max((r.get("createdAt") or "" for r in responses), default="")
    try:
        latest_str = datetime.fromisoformat(latest.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        latest_str = "—"
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    html = build_html(spec, sections, n_total, n_done, latest_str, now_str,
                       logo_url=L.get_survey_logo(survey))

    R = spec["results"]
    out_static = os.path.join(L.HERE, "static", R["static_name"])
    with open(out_static, "w", encoding="utf-8") as f:
        f.write(html)
    if R.get("result_dir"):
        os.makedirs(R["result_dir"], exist_ok=True)
        with open(os.path.join(R["result_dir"], "survey_results.html"), "w", encoding="utf-8") as f:
            f.write(html)
        # responses.csv: one row per response; header text pulled from the LIVE
        # survey (so it stays consistent with the respondent page, not the spec).
        # A spec question that is absent from the live survey must NOT abort the
        # export: fall back to the spec headline, keep the (empty) column and warn
        # loudly. Files are written atomically, so a failure can never leave a
        # truncated CSV / JSON behind (that is what killed this export for 2.5 days).
        qids = [q["id"] for q in spec["questions"]]
        spec_head = {q["id"]: strip_rich((q.get("headline") or {}).get("zh-TW")
                                         or (q.get("headline") or {}).get("default")
                                         or q.get("headline_zh") or "")
                     for q in spec["questions"]}
        zh_head = {q["id"]: strip_rich((q.get("headline") or {}).get("zh-TW")
                                       or (q.get("headline") or {}).get("default") or "")
                   for q in survey["questions"] if q["id"] in qids}
        missing = [q for q in qids if q not in zh_head]
        if missing:
            print(f"  !! spec questions absent from the live survey: {missing} "
                  "-> kept as empty columns; align the spec with the survey")
            for q in missing:
                zh_head[q] = spec_head.get(q) or q
        out_csv = os.path.join(R["result_dir"], "responses.csv")
        tmp_csv = out_csv + ".tmp"
        with open(tmp_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["created_at", "finished", "language"] + [f"{zh_head[q]} ({q})" for q in qids])
            for r in sorted(responses, key=lambda x: x.get("createdAt") or ""):
                row = [r.get("createdAt", ""), r.get("finished", ""), r.get("language", "")]
                for qid in qids:
                    v = (r.get("data") or {}).get(qid)
                    row.append("；".join(v) if isinstance(v, list) else (v if v is not None else ""))
                w.writerow(row)
        os.replace(tmp_csv, out_csv)
        # results.json: aggregates
        agg = {"survey_id": spec["survey_id"], "name": spec["name"], "exported_at": now_str,
               "total": n_total, "finished": n_done,
               "sections": [
                   {"title_zh": sec["title_zh"], "title_en": sec.get("title_en", ""),
                    "questions": [
                        {k: item[k] for k in ("id", "type", "zh", "en", "answered", "rows", "others", "answers")
                         if item.get(k) is not None}
                        for item in items]}
                   for sec, items in sections]}
        out_json = os.path.join(R["result_dir"], "results.json")
        tmp_json = out_json + ".tmp"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(agg, f, ensure_ascii=False, indent=2)
        os.replace(tmp_json, out_json)

    print(f"html: {out_static} ({os.path.getsize(out_static)//1024} KB)")
    if R.get("result_dir"):
        print(f"data : {R['result_dir']} (survey_results.html, responses.csv, results.json)")
    print(f"responses: {n_total} (finished {n_done}, partial {n_total - n_done})")
    for sec, items in sections:
        for item in items:
            if item["type"] == "open":
                print(f"  {item['id']:<16} answered {item['answered']}/{n_total}")
            else:
                top = max(item["rows"], key=lambda r: r["cnt"]) if item["rows"] else None
                top_s = f"top: {top['zh'][:22]} ({top['cnt']})" if top and top["cnt"] else "no answers yet"
                print(f"  {item['id']:<16} answered {item['answered']}/{n_total:<3} {top_s}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
