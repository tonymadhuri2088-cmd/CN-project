"""Presentation layer of the NetWing web UI: design system, page shell, overview and reproducibility pages.

Everything here is server-rendered HTML with inline CSS and inline SVG. There is no JavaScript, so the strict Content-Security-Policy in
`webui` stays as it is. The numbers on the overview and results pages are *measured from the raw run logs when the page is built* (using the
same code as `python -m netwing.reproduce check`), never typed in, so the page cannot drift from the evidence.
"""
from __future__ import annotations

import json
import os
import threading
from html import escape as e
from typing import Any

from . import reproduce

REPO_URL = "https://github.com/tonymadhuri2088-cmd/CN-project"
AUTHOR = "Tony Madhuri"
GUIDE = "Dr. Mehbub Alam"
AUTHOR_LINE = f"{AUTHOR} · B.Tech 3rd year, AI&DS · IIIT Raichur · Computer Networks project · Guide: {GUIDE}"
STATE: dict[str, Any] = {"read_only": False}  # set by webui.make_handler; read by page()

_FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' "
            "fill='%231e3a8a'/%3E%3Cpath d='M7 11h18M7 16h12M7 21h8' stroke='%23fff' stroke-width='2.4' stroke-linecap='round'/%3E"
            "%3Cpath d='M20 21l3 3 5-6' stroke='%2334d399' stroke-width='2.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")

_LOGO = ("<svg width='28' height='28' viewBox='0 0 32 32' aria-hidden='true'><rect width='32' height='32' rx='7' fill='#fff' fill-opacity='.14'/>"
         "<path d='M7 11h18M7 16h12M7 21h8' stroke='#fff' stroke-width='2.4' stroke-linecap='round'/>"
         "<path d='M20 21l3 3 5-6' stroke='#34d399' stroke-width='2.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>")

CSS = """
:root{--ink:#0f172a;--muted:#475569;--line:#e3e6f5;--bg:#f5f6ff;--card:#fff;--brand:#4338ca;--brand2:#7c3aed;--accent:#4f46e5;
--ok:#047857;--okbg:#ecfdf5;--warn:#92400e;--warnbg:#fffbeb;--bad:#b91c1c;--badbg:#fef2f2;--chip:#eef0ff;--code:#f1f3fb;--bar:#e3e6f5;--teal:#0d9488;--pink:#db2777;--amber:#d97706}
@media (prefers-color-scheme:dark){:root{--ink:#e5e7eb;--muted:#a3adbd;--line:#2b2856;--bg:#0c0a1f;--card:#15132e;--brand:#4338ca;--brand2:#7c3aed;
--accent:#a5b4fc;--ok:#6ee7b7;--okbg:#06281d;--warn:#fcd34d;--warnbg:#2b1d05;--bad:#fca5a5;--badbg:#2d1010;--chip:#221f4a;--code:#1b1938;--bar:#2b2856;--teal:#2dd4bf;--pink:#f472b6;--amber:#fbbf24}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:15px/1.6 system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--accent);text-underline-offset:2px}a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #f59e0b;outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px;top:0;background:#fff;color:#000;padding:8px 12px;z-index:10}.skip:focus{left:8px;top:8px}
header.top{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff}
.bar{max-width:1120px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;font-weight:700;font-size:18px;letter-spacing:.2px}
.brand small{font-weight:500;opacity:.75;font-size:12px;display:block;line-height:1.1}
nav.main{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto}
nav.main a{color:#e0e7ff;text-decoration:none;padding:7px 12px;border-radius:8px;font-size:14px}
nav.main a:hover{background:rgba(255,255,255,.12);color:#fff}nav.main a[aria-current=page]{background:rgba(255,255,255,.2);color:#fff;font-weight:600}
.banner{background:var(--warnbg);color:var(--warn);border-bottom:1px solid var(--line);font-size:13.5px}
.banner div{max-width:1120px;margin:0 auto;padding:8px 20px}
main{max-width:1120px;margin:0 auto;padding:26px 20px 40px}
h1{font-size:28px;line-height:1.2;margin:0 0 10px;letter-spacing:-.3px}h2{font-size:22px;margin:38px 0 12px;letter-spacing:-.3px}h3{font-size:16px;margin:0 0 6px}
p{margin:0 0 12px}.lead{font-size:17px;color:var(--muted);max-width:760px}.muted,.nm{color:var(--muted)}
.hero{background:linear-gradient(135deg,var(--brand) 0%,var(--brand2) 100%);color:#fff;border-radius:20px;padding:40px 40px 34px;margin:2px 0 10px;box-shadow:0 10px 30px rgba(15,23,42,.18)}
.hero h1{color:#fff;font-size:34px;max-width:860px;letter-spacing:-.6px}.hero .lead{color:#dbe4ff;max-width:800px}
.kicker{display:inline-block;background:var(--chip);color:var(--accent);padding:3px 10px;border-radius:999px;font-size:12.5px;font-weight:600;margin-bottom:10px}
.hero .kicker{background:rgba(255,255,255,.16);color:#fff;letter-spacing:.3px}
.byline{display:flex;align-items:center;gap:12px;margin:18px 0 20px;color:#e0e7ff;font-size:14.5px}
.avatar{width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);display:grid;place-items:center;font-weight:700;color:#fff}
.byline b{color:#fff;display:block;line-height:1.2}.byline span{opacity:.8;font-size:13px}
.hero .btn{background:#fff;color:var(--brand)}.hero .btn.alt{background:rgba(255,255,255,.14);color:#fff;border:1px solid rgba(255,255,255,.35)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0;padding:0;list-style:none}.chips li{background:var(--chip);color:var(--accent);border-radius:999px;padding:4px 12px;font-size:13px;font-weight:600}
.about{display:grid;gap:20px;grid-template-columns:2fr 1fr}.about h3{font-size:18px}
.facts{margin:0;padding:0;list-style:none;display:grid;gap:10px}.facts li{border-left:3px solid var(--accent);padding:2px 0 2px 12px;font-size:14px}.facts b{display:block;font-size:20px;letter-spacing:-.3px}
@media (max-width:760px){.about{grid-template-columns:1fr}.hero{padding:26px 22px}.hero h1{font-size:26px}}
.grid{display:grid;gap:14px}.g4{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:12px 0;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.grid .card{transition:transform .15s,box-shadow .15s}.grid .card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(15,23,42,.1)}
.grid .card{margin:0}.card.flat{box-shadow:none}
.tile .big{font-size:34px;font-weight:700;letter-spacing:-.5px;line-height:1.1}.tile .big s{color:var(--muted);font-weight:500;font-size:20px;text-decoration-thickness:2px}
.tile .lbl{font-weight:600;margin-bottom:6px}.tile .sub{font-size:13px;color:var(--muted);margin-top:6px}
.pill,.tag{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;background:var(--chip);color:var(--accent)}
.tag{background:var(--warnbg);color:var(--warn)}.pill.ok{background:var(--okbg);color:var(--ok)}.pill.bad{background:var(--badbg);color:var(--bad)}.pill.skip{background:var(--code);color:var(--muted)}
.pass{color:var(--ok);font-weight:600}.fail{color:var(--bad);font-weight:600}.mixed{color:var(--warn);font-weight:600}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card);margin:10px 0}
.card .table-wrap{margin:8px 0 0}table{border-collapse:collapse;width:100%}
th{background:var(--code);font-weight:600;text-align:left;position:sticky;top:0}
td,th{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:13.5px}tr:last-child td{border-bottom:0}
tbody tr:hover td,table tr:hover td{background:rgba(148,163,184,.08)}
code{background:var(--code);padding:1px 6px;border-radius:5px;font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;word-break:break-word}
pre{background:var(--code);padding:12px;border-radius:8px;overflow:auto}
form.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:end;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}
label{font-size:13px;color:var(--muted);display:flex;flex-direction:column;gap:3px}
select,input[type=text]{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
button,.btn{font:inherit;font-weight:600;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 16px;cursor:pointer;text-decoration:none;display:inline-block}
@media (prefers-color-scheme:dark){button,.btn{color:#0b1220}}
button.alt,.btn.alt{background:var(--chip);color:var(--accent)}
.steps{counter-reset:s;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));padding:0;list-style:none;margin:10px 0}
.steps li{counter-increment:s;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px 14px 52px;position:relative}
.steps li:before{content:counter(s);position:absolute;left:14px;top:14px;width:26px;height:26px;border-radius:50%;background:var(--brand);color:#fff;font-weight:700;display:grid;place-items:center;font-size:13px}
.hbar{background:var(--bar);border-radius:6px;height:18px;width:min(320px,100%)}.hbar>i{display:block;height:18px;border-radius:6px}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 16px;margin:10px 0}summary{cursor:pointer;font-weight:600}
.callout{border-left:4px solid var(--accent);background:var(--card);border-radius:0 12px 12px 0;padding:12px 16px;border-top:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.callout.honest{border-left-color:#d97706}
footer{max-width:1120px;margin:0 auto;padding:18px 20px 36px;color:var(--muted);font-size:13px;border-top:1px solid var(--line)}
div.chartwrap{overflow-x:auto}svg.chart text{font:12px system-ui,sans-serif;fill:var(--ink)}svg.chart .mut{fill:var(--muted)}svg.chart .trk{fill:var(--bar)}
@media (max-width:600px){h1{font-size:23px}nav.main{margin-left:0}.tile .big{font-size:26px}}
@media (prefers-reduced-motion:reduce){.grid .card{transition:none}.grid .card:hover{transform:none}}
@media print{header.top,.banner,footer,.skip,form.filters{display:none}body{background:#fff;color:#000}main{padding:0}.card{break-inside:avoid}}
/* v2 theme: richer colour, depth, hierarchy */
body{background:var(--bg);background-image:radial-gradient(900px 420px at 85% -80px,rgba(124,58,237,.16),transparent 70%),radial-gradient(700px 360px at -10% 120px,rgba(14,165,233,.12),transparent 70%);background-repeat:no-repeat}
header.top{background:linear-gradient(120deg,#312e81,#5b21b6 60%,#0e7490);box-shadow:0 2px 14px rgba(49,46,129,.35)}
.hero{position:relative;overflow:hidden;background:linear-gradient(125deg,#3730a3 0%,#6d28d9 55%,#0891b2 130%);box-shadow:0 18px 44px rgba(79,70,229,.30)}
.hero:before{content:'';position:absolute;right:-90px;top:-90px;width:340px;height:340px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.22),transparent 68%)}
.hero:after{content:'';position:absolute;left:38%;bottom:-140px;width:420px;height:300px;border-radius:50%;background:radial-gradient(circle,rgba(45,212,191,.28),transparent 70%)}
.hero>*{position:relative;z-index:1}
.hero h1{font-size:38px;line-height:1.15}
.hero .lead{color:#e6e9ff}
.hero .btn{background:#fff;color:#4338ca;box-shadow:0 4px 14px rgba(0,0,0,.18)}.hero .btn:hover{transform:translateY(-1px)}
.byline{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:14px;padding:10px 16px;width:fit-content;max-width:100%;backdrop-filter:blur(6px)}
.avatar{background:linear-gradient(135deg,#2dd4bf,#818cf8);border:0;color:#0f172a;box-shadow:0 2px 8px rgba(0,0,0,.25)}
h2{position:relative;padding-left:14px}h2:before{content:'';position:absolute;left:0;top:.2em;bottom:.2em;width:5px;border-radius:4px;background:linear-gradient(180deg,#6366f1,#14b8a6)}
.card{border-radius:16px;box-shadow:0 2px 10px rgba(79,70,229,.07)}
.grid .card{border-top:4px solid var(--accent)}
.grid.g4 .card:nth-child(1){border-top-color:#6366f1}.grid.g4 .card:nth-child(2){border-top-color:#a855f7}.grid.g4 .card:nth-child(3){border-top-color:#14b8a6}.grid.g4 .card:nth-child(4){border-top-color:#f59e0b}
.tile .big{background:linear-gradient(90deg,#6366f1,#14b8a6);-webkit-background-clip:text;background-clip:text;color:transparent;font-size:38px}
.tile .big s{-webkit-text-fill-color:var(--muted)}
.banner{background:linear-gradient(90deg,rgba(245,158,11,.16),rgba(245,158,11,.06))}
.chips li{background:linear-gradient(135deg,rgba(99,102,241,.16),rgba(20,184,166,.16));border:1px solid var(--line)}
.btn,button{background:linear-gradient(135deg,#4f46e5,#7c3aed)}button.alt,.btn.alt{background:var(--chip);color:var(--accent)}
.steps li:before{background:linear-gradient(135deg,#6366f1,#14b8a6)}
.facts li{border-left-color:#14b8a6}
.callout{border-left-color:#14b8a6}
footer{border-top:1px solid var(--line)}
"""

_NAV = [("/", "Overview"), ("/history", "History"), ("/results", "Reproducibility"), ("/lab", "Simulation lab"), ("/new", "Run investigation")]


def _nav(active: str) -> str:
    items = [(h, t) for h, t in _NAV if not (STATE["read_only"] and h == "/new")]
    return "".join(f"<a href='{h}'{' aria-current=page' if h == active else ''}>{e(t)}</a>" for h, t in items)


def page(title: str, body: str, active: str = "") -> bytes:
    """Wrap `body` in the shared shell. Tables are made horizontally scrollable on small screens."""
    body = body.replace("<table", "<div class='table-wrap'><table").replace("</table>", "</table></div>")
    banner = ("<div class='banner' role='note'><div><b>Read-only demo.</b> Starting new runs is disabled and no API key exists on this server; "
              "everything shown comes from run logs recorded earlier.</div></div>" if STATE["read_only"] else "")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<meta name='description' content='NetWing: an evidence-sufficiency controller for LLM network-diagnosis agents. A Computer Networks project by Tony Madhuri.'>"
            f"<meta name='color-scheme' content='light dark'><link rel='icon' href=\"{_FAVICON}\"><title>{e(title)} · NetWing</title>"
            f"<style>{CSS}</style></head><body><a class='skip' href='#content'>Skip to content</a>"
            f"<header class='top'><div class='bar'><a class='brand' href='/'>{_LOGO}<span>NetWing<small>evidence-sufficiency controller</small></span></a>"
            f"<nav class='main' aria-label='Main'>{_nav(active)}</nav></div></header>{banner}"
            f"<main id='content'>{body}</main>"
            f"<footer><b>NetWing</b> · research prototype for LLM network diagnosis · {e(AUTHOR_LINE)} · <a href='{REPO_URL}'>source and documentation on GitHub</a>"
            "<br>Simulated networks unless a record says otherwise. Every number on the Overview and Reproducibility pages is recomputed from the raw logs.</footer>"
            "</body></html>").encode()


# --- measuring the locked claims -------------------------------------------------------------------------------------------------------

_SUITES = [  # longest prefix first
    ("heldout.default", "Held-out suite · default controller"), ("heldout.autocite", "Held-out suite · auto-cite"),
    ("hard.rerun", "Hard suite · re-run"), ("realnet", "Real network lab (Linux namespaces)"), ("fresh2.original", "Fresh-2 · original controller"),
    ("fresh2.hybrid_hint", "Fresh-2 · hybrid healthy rule + retest hint"), ("fresh2.validate", "Fresh-2 · claim validation"),
    ("fresh3.original", "Fresh-3 · original controller"), ("fresh3.tier", "Fresh-3 · tiered claims"), ("fresh3.combined", "Fresh-3 · tiers + validation"),
    ("fresh", "Fresh suite"),
]
_METRICS = {"false_fault": "false alarms", "no_answer": "unanswered runs", "tests": "mean tests per run", "healthy_ok": "healthy called healthy",
            "extra": "extra faults claimed", "multi_exact": "multi-fault answers exact", "multi_exact_incl": "multi-fault exact (suspected counted)"}


def _label(c: dict) -> tuple[str, str, str]:
    suite = next((name for pre, name in _SUITES if c["id"] == pre or c["id"].startswith(pre + ".")), c["id"])
    return suite, c.get("mode", ""), _METRICS.get(c["metric"], c["metric"])


def measure(claim: dict, root: str) -> dict:
    """Recompute one locked claim from its raw log. Returns suite, mode, metric label, documented value, measured value, status."""
    suite, mode, metric = _label(claim)
    out: dict[str, Any] = {"id": claim["id"], "doc": claim.get("doc", ""), "suite": suite, "mode": mode, "metric": metric,
                           "k": None, "n": None, "mean": None, "documented": "", "measured": "n/a"}
    path = os.path.join(root, claim["file"])
    if "mean" in claim:
        out["documented"] = f"{claim['mean']} tests"
    else:
        out["documented"] = f"{claim['k']}/{claim['n']}"
    if not os.path.exists(path):
        out["status"] = "SKIP"
        return out
    try:
        rows = reproduce.select(path, claim.get("invocation"), claim.get("mode"))
        if "mean" in claim:
            got = reproduce.measure_mean(rows, claim["metric"])
            digits = claim.get("digits", 1)
            out.update(mean=got, measured=f"{round(got, digits)} tests", status="ok" if round(got, digits) == round(claim["mean"], digits) else "FAIL")
        else:
            k, n = reproduce.measure_count(rows, claim["metric"])
            out.update(k=k, n=n, measured=f"{k}/{n}", status="ok" if (k, n) == (claim["k"], claim["n"]) else "FAIL")
    except (IndexError, KeyError, ValueError, OSError):
        out["status"] = "FAIL"
    return out


_CACHE: dict[tuple[str, str], list[dict]] = {}
_LOCK = threading.Lock()


def results_data(root: str, claims_path: str | None = None) -> list[dict]:
    """All locked claims, recomputed once per process (the logs are frozen) and cached. Empty list when no claims file is shipped."""
    claims_path = claims_path or os.path.join(root, "docs", "research", "claims.json")
    key = (os.path.abspath(root), os.path.abspath(claims_path))
    with _LOCK:
        if key not in _CACHE:
            try:
                with open(claims_path, encoding="utf-8") as f:
                    claims = json.load(f)
            except (OSError, ValueError):
                claims = []
            _CACHE[key] = [measure(c, root) for c in claims]
        return _CACHE[key]


def _get(data: list[dict], cid: str) -> dict | None:
    return next((d for d in data if d["id"] == cid and d["k"] is not None), None)


def _pct(d: dict) -> int:
    return round(100 * d["k"] / d["n"]) if d["n"] else 0


# --- chart ------------------------------------------------------------------------------------------------------------------------------

_MODE_NAMES = {"plain": "plain agent", "healthy_ok": "plain + healthy rule", "netwing": "NetWing"}
_MODE_FILL = {"plain": "#64748b", "healthy_ok": "#d97706", "netwing": "#1d4ed8"}


def false_alarm_chart(data: list[dict]) -> str:
    """Inline-SVG grouped bars: share of runs ending in a false alarm, per suite and mode. Values are labelled, so colour is never the only cue."""
    groups = [("Held-out suite, default controller", "heldout.default"), ("Held-out suite, auto-cite", "heldout.autocite"),
              ("Hard suite, re-run", "hard.rerun")]
    rows: list[tuple[str, str, dict]] = []
    for gname, pre in groups:
        for mode in ("plain", "healthy_ok", "netwing"):
            d = _get(data, f"{pre}.{mode}.false_fault")
            if d:
                rows.append((gname, mode, d))
    if not rows:
        return ""
    w, left, right, rh, gap, top = 760, 210, 120, 20, 22, 8
    y = top
    parts: list[str] = []
    last = None
    track = w - left - right
    for gname, mode, d in rows:
        if gname != last:
            y += gap if last is not None else 0
            parts.append(f"<text x='0' y='{y + 14}' font-weight='600'>{e(gname)}</text>")
            y += 22
            last = gname
        pct = _pct(d)
        bw = max(2, round(track * d["k"] / d["n"])) if d["k"] else 0
        parts.append(f"<text x='14' y='{y + 14}' class='mut'>{e(_MODE_NAMES[mode])}</text>"
                     f"<rect class='trk' x='{left}' y='{y}' width='{track}' height='{rh}' rx='5'/>"
                     + (f"<rect x='{left}' y='{y}' width='{bw}' height='{rh}' rx='5' fill='{_MODE_FILL[mode]}'/>" if bw else "")
                     + f"<text x='{left + track + 10}' y='{y + 14}'>{d['k']}/{d['n']} · {pct}%</text>")
        y += rh + 6
    h = y + 6
    desc = "Share of runs that ended in a false alarm. " + "; ".join(f"{g}, {_MODE_NAMES[m]}: {d['k']} of {d['n']}" for g, m, d in rows)
    return (f"<div class='chartwrap'><svg class='chart' viewBox='0 0 {w} {h}' width='100%' role='img' aria-labelledby='fa-t fa-d' style='max-width:{w}px;min-width:600px'>"
            f"<title id='fa-t'>False alarms by suite and mode</title><desc id='fa-d'>{e(desc)}</desc>{''.join(parts)}</svg></div>")


# --- pages ------------------------------------------------------------------------------------------------------------------------------

def _tile(label: str, before: dict | None, after: dict | None, sub: str, better: str = "down") -> str:
    if not before or not after:
        return ""
    return (f"<div class='card tile'><div class='lbl'>{e(label)}</div><div class='big'><s>{before['k']}/{before['n']}</s> → {after['k']}/{after['n']}</div>"
            f"<div class='sub'>plain agent {_pct(before)}% → NetWing {_pct(after)}%. {e(sub)}</div></div>")


def overview_page(data: list[dict]) -> bytes:
    ok = sum(1 for d in data if d["status"] == "ok")
    bad = sum(1 for d in data if d["status"] == "FAIL")
    skip = sum(1 for d in data if d["status"] == "SKIP")
    tiles = "".join([
        _tile("False alarms · held-out suite", _get(data, "heldout.default.plain.false_fault"), _get(data, "heldout.default.netwing.false_fault"),
              "Scenarios the agent had not seen while the controller was built."),
        _tile("False alarms · hard suite", _get(data, "hard.rerun.plain.false_fault"), _get(data, "hard.rerun.netwing.false_fault"),
              "Misleading complaints and flaky faults."),
        _tile("Healthy network called healthy", _get(data, "fresh.plain.healthy_ok"), _get(data, "fresh.netwing.healthy_ok"),
              "Higher is better here: the share of healthy runs answered correctly."),
    ])
    if data:
        verdict = (f"<div class='card tile'><div class='lbl'>Documented numbers that reproduce</div><div class='big'>{ok}/{len(data)}</div>"
                   f"<div class='sub'>{'Recomputed from the raw logs just now. ' if bad == 0 else '<b>' + str(bad) + ' differ from the documents.</b> '}"
                   f"{str(skip) + ' not checkable here (log not shipped). ' if skip else ''}<a href='/results'>See every number</a>.</div></div>")
        tiles += verdict
    chart = false_alarm_chart(data)
    no_ans = _get(data, "heldout.default.netwing.no_answer")
    no_ans2 = _get(data, "heldout.autocite.netwing.no_answer")
    cost = (f" It also left {no_ans['k']} of {no_ans['n']} (default) and {no_ans2['k']} of {no_ans2['n']} (auto-cite) held-out runs without a final answer."
            if no_ans and no_ans2 else "")
    chart_card = (f"<h2>False alarms, plain agent against NetWing</h2><div class='card'>{chart}<p class='muted' style='margin-top:10px'>"
                  "A false alarm is a fault declared on a network that was healthy or had a different fault. Lower is better. "
                  "The three suites are separate recorded experiments; their raw logs are in the repository.</p></div>" if chart else "")
    body = (
        "<section class='hero'><span class='kicker'>Research prototype · LLM network diagnosis</span>"
        "<h1>Make an AI troubleshooting agent prove it has enough evidence before it answers.</h1>"
        "<p class='lead'>NetWing sits outside the language model. It writes every test the agent runs into a numbered evidence ledger and only accepts a "
        "“fault found” answer once a failure has been reproduced and the connectivity, DNS and port areas have all been checked.</p>"
        f"<div class='byline'><div class='avatar' aria-hidden='true'>TM</div><div><b>{e(AUTHOR)}</b><span>B.Tech 3rd year, AI&amp;DS · IIIT Raichur · Guide: {e(GUIDE)}</span></div></div>"
        "<p><a class='btn' href='/history'>Browse recorded investigations</a> <a class='btn alt' href='/results'>Check the numbers</a> "
        f"<a class='btn alt' href='{REPO_URL}'>Source on GitHub</a></p></section>"
        + (f"<h2>Headline results</h2><div class='grid g4'>{tiles}</div>" if tiles else
           "<div class='card'><b>No result logs found next to this server</b>, so headline numbers are not shown. "
           "Put the run logs in the results folder and reload.</div>")
        + chart_card +
        "<h2>About this project</h2><div class='card about'><div><h3>Why NetWing exists</h3>"
        "<p>LLM agents that troubleshoot networks tend to “find” a fault on a network that is actually healthy, and keep testing long after they have enough evidence. "
        "NetWing is a transparent rule engine placed between the agent and its conclusion. It numbers every test result, accepts a fault only when it is reproduced "
        "and the connectivity, DNS and port areas have all been checked, and stops the run when the evidence is sufficient or the 12-test budget is spent.</p>"
        "<p>It was built and tested as a Computer Networks project by " + e(AUTHOR) + " (B.Tech 3rd year, AI&amp;DS, IIIT Raichur) under the guidance of " + e(GUIDE) + ": a simulator for most experiments, real Linux network namespaces for the easy suite, "
        "frozen pre-registered test suites, and every documented number re-derived from the raw logs.</p>"
        "<ul class='chips'><li>Python</li><li>Claude Haiku 5.5</li><li>Linux network namespaces</li><li>Reproducible logs</li><li>Frozen suites</li></ul></div>"
        "<ul class='facts'><li><b>9 rules</b>decide when evidence is enough</li><li><b>12 tests</b>maximum per investigation</li>"
        "<li><b>No second model</b>the controller is auditable code</li></ul></div>"
        "<h2>How the controller decides</h2><ol class='steps'>"
        "<li><h3>Record</h3>Every test the agent runs becomes numbered evidence (E1, E2, …) in an append-only ledger.</li>"
        "<li><h3>Healthy?</h3>If the evidence shows no standing failure, the controller can stop with “healthy”. A failed test must be repeated before it is dismissed as a blip.</li>"
        "<li><h3>Fault?</h3>A fault is accepted only if a failure is reproduced, connectivity, DNS and port were all tried, and the answer cites real evidence ids.</li>"
        "<li><h3>Cap</h3>After 12 tests the controller stops the run instead of letting the agent loop.</li></ol>"
        "<h2>What this does and does not show</h2><div class='callout honest'>"
        "<p><b>The claim is about false alarms, not accuracy.</b> On the held-out suite NetWing is not more accurate than the plain agent (84–88% against 81–90%, "
        "ranges overlap); what it changes is that it does not declare faults it cannot back up." + e(cost) + "</p>"
        "<p>All networks are simulated unless a record is marked otherwise, one model was used (claude-haiku-5-5), and repeated runs of identical "
        "settings differ by roughly 9–20 percentage points. Treat the numbers as evidence from a prototype, not as a benchmark of production systems.</p></div>"
        "<h2>Explore</h2><div class='grid g3'>"
        "<div class='card'><h3>History</h3><p>Open any recorded run: ticket, evidence explorer, health score, downloadable report.</p><a href='/history'>Open history →</a></div>"
        "<div class='card'><h3>Simulation lab</h3><p>The scenarios, each with the ground-truth fault used for automatic scoring.</p><a href='/lab'>See scenarios →</a></div>"
        "<div class='card'><h3>Reproducibility</h3><p>Each documented number next to the value recomputed from the raw log.</p><a href='/results'>Check the numbers →</a></div></div>")
    return page("Overview", body, "/")


def results_page(data: list[dict]) -> bytes:
    if not data:
        return page("Reproducibility", "<h1>Reproducibility</h1><div class='card'>No claims file (<code>docs/research/claims.json</code>) is shipped with this server.</div>", "/results")
    ok = sum(1 for d in data if d["status"] == "ok")
    bad = sum(1 for d in data if d["status"] == "FAIL")
    skip = sum(1 for d in data if d["status"] == "SKIP")
    cls = "ok" if bad == 0 and skip == 0 else "bad" if bad else "skip"
    head = (f"<p class='lead'><span class='pill {cls}'>{ok} of {len(data)} reproduce</span> "
            "Each row is a number quoted in the project documents. This page re-measures it from the raw run log and compares it with the documented value; "
            "the same check runs on every code change (<code>python -m netwing.reproduce check --strict</code>).</p>")
    if bad:
        head += f"<div class='card'><b class='fail'>{bad} number(s) differ from the documents.</b> Do not quote them until this is resolved.</div>"
    rows = "".join(
        f"<tr><td>{e(d['suite'])}</td><td>{e(d['mode'])}</td><td>{e(d['metric'])}</td><td>{e(d['documented'])}</td><td>{e(d['measured'])}</td>"
        f"<td><span class='pill {'ok' if d['status'] == 'ok' else 'bad' if d['status'] == 'FAIL' else 'skip'}'>"
        f"{'reproduces' if d['status'] == 'ok' else 'differs' if d['status'] == 'FAIL' else 'log not shipped'}</span></td>"
        f"<td><code>{e(os.path.basename(d['doc']))}</code></td></tr>" for d in data)
    body = ("<h1>Reproducibility</h1>" + head +
            "<table><tr><th>Experiment</th><th>Mode</th><th>Measure</th><th>Documented</th><th>Recomputed from log</th><th>Result</th><th>Quoted in</th></tr>"
            f"{rows}</table><p class='muted'>Logs are append-only JSON lines; each experiment is selected by file, invocation and mode. "
            "Frozen suites and pre-registered criteria are never edited after results are seen.</p>")
    return page("Reproducibility", body, "/results")
