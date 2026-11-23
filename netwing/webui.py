"""NetWing web UI (stdlib only, no extra dependencies).

    python -m netwing.webui --results results --port 8765

Pages: overview with headline results, history list with filters, investigation detail (Evidence Explorer, health, report download),
compare two investigations, reproducibility table, simulation lab (scenario browser with ground truth).

    python -m netwing.webui --results results --read-only      # public demo: no runs, no API key is ever read (also NETWING_READONLY=1)
"""
from __future__ import annotations

import argparse
import hmac
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from html import escape as e
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

from .health import compute_health
from .history import History
from .pdfexport import render_pdf
from .report import render_report
from . import site
from .scenarios import _SCENARIOS
from .site import page

_JOB: dict = {}  # the one running or last investigation started from the UI
_TOKEN = secrets.token_urlsafe(24)  # per-process secret; the Run form carries it, so a page on another site cannot start a run
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


def _host_only(value: str) -> str:
    """Host name without port from a Host header or an Origin netloc (handles [::1]:8765)."""
    v = (value or "").strip().lower()
    if v.startswith("["):
        return v[1:v.find("]")] if "]" in v else v
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v

def _sim(r, model: str = "") -> str:
    tag = "<span class='tag'>SIMULATED</span>" if r else "real"
    return tag + (" <span class='tag' style='background:#e0e0e0'>DRY RUN stub</span>" if model == "dry-run" else "")


def summary_html(h: History, scenario: str) -> str:
    st = h.stats(scenario)
    if not st:
        return ""
    rows = "".join(
        f"<tr><td>{e(r['mode'])}</td><td>{r['runs']}</td><td>{round(100 * r['correct'] / r['runs'])}%</td>"
        f"<td>{r['false_alarms']}</td><td>{r['mean_tests']:.1f}</td><td>${r['mean_cost']:.4f}</td></tr>" for r in st)
    return ("<div class='card'><b>Totals for this filter (real model runs only; dry-run stubs excluded)</b>"
            "<table><tr><th>Mode</th><th>Runs</th><th>Correct</th><th>False alarms</th><th>Mean tests</th><th>Mean cost</th></tr>"
            f"{rows}</table><p class='nm'>Counts only; for quotable numbers use the confidence-interval tables from the CLI.</p></div>")


def history_page(h: History, q: dict) -> bytes:
    sc, mode = q.get("scenario", [""])[0], q.get("mode", [""])[0]
    rows, total = h.list_page(sc, mode)
    opts = "<option value=''>All</option>" + "".join(f"<option{' selected' if s == sc else ''}>{e(s)}</option>" for s in h.scenarios())
    modes = "<option value=''>All</option>" + "".join(f"<option{' selected' if m == mode else ''}>{m}</option>" for m in ["plain", "healthy_ok", "netwing"])
    body = (f"<h1>Investigation history</h1><p class='lead'>Every recorded run: the ticket, the tests the agent ran, the verdict and whether it was right.</p>"
            f"<form class='filters'><label>Scenario <select name='scenario'>{opts}</select></label> "
            f"<label>Mode <select name='mode'>{modes}</select></label> <button>Filter</button></form>"
            f"<p class='muted'>Showing {len(rows)} of {total} (newest first; filter to narrow)</p>"
            + summary_html(h, sc) +
            "<form action='/compare'><table><tr><th>A</th><th>B</th><th>Record</th><th>Scenario</th><th>Mode</th>"
            "<th>Verdict</th><th>Correct</th><th>Tests</th><th>Cost</th><th>Network</th></tr>")
    for r in rows:
        rid = e(r["id"])
        body += (f"<tr><td><input type='radio' name='a' value='{rid}' aria-label='Compare {rid} as A'></td>"
                 f"<td><input type='radio' name='b' value='{rid}' aria-label='Compare {rid} as B'></td>"
                 f"<td><a href='/run/{quote(r['id'])}'>{rid}</a></td><td>{e(r['scenario'])}</td><td>{e(r['mode'])}</td>"
                 f"<td>{e(str(r['verdict']))}</td><td class='{'pass' if r['correct'] else 'fail'}'>{'yes' if r['correct'] else 'no'}</td><td>{r['tests_run']}</td>"
                 f"<td>${r['cost']:.4f}</td><td>{_sim(r['simulated'], r.get('model') or '')}</td></tr>")
    body += "</table><p><button>Compare selected A and B</button></p></form>"
    return page("History", body, "/history")


def run_page(rec: dict) -> bytes:
    health = compute_health(rec["tests"])
    hrows = "".join(
        f"<tr><td>{e(i['label'])}</td><td class='{i['state'] if i['state'] != 'not_measured' else 'nm'}'>"
        f"{e(i['state'].replace('_', ' '))}</td><td>{i['measurements']}</td></tr>" for i in health["indicators"])
    score = "not enough measurements" if health["score"] is None else f"{health['score']}/100 from {health['measured']} of {health['total']} indicators"
    bar = ""
    if health["score"] is not None:
        col = "#0a6b2d" if health["score"] >= 80 else "#9a6700" if health["score"] >= 50 else "#b00020"
        bar = (f"<div style='background:#e4e6ea;border-radius:6px;width:320px;height:18px'><div style='background:{col};"
               f"width:{health['score']}%;height:18px;border-radius:6px'></div></div>")
    trows = "".join(
        f"<tr><td>{e(t['id'])}</td><td>{e(t['tool'])}</td><td><code>{e(str(t['args']))}</code></td>"
        f"<td>{e(t['output']).replace(chr(10), '<br>')}</td><td class='{'pass' if t['ok'] else 'fail'}'>{'pass' if t['ok'] else 'fail'}</td></tr>"
        for t in rec["tests"])
    note = "<p class='nm'>Pass/fail was parsed from tool output text (older log).</p>" if rec["parsed_from_text"] else ""
    sc = rec["score"]
    asr = rec.get("assurance")
    asr_html = (f"<br><b>Evidence assurance:</b> <span class='tag'>{e(asr['label'])}</span> {e(asr['reason'])}"
                if asr else "<br><b>Evidence assurance:</b> not assessed (older log without recorded test categories)")
    truth = _SCENARIOS.get(rec["scenario"])
    gt = f"<p>Ground truth: <code>{e(truth.truth)}</code>{' + ' + ', '.join(truth.also) if truth.also else ''}</p>" if truth else ""
    body = (f"<h1>{e(rec['id'])} {_sim(rec['simulated'], rec.get('model') or '')}</h1>"
            f"<div class='card'><b>Ticket:</b> {e(rec['ticket'])}<br><b>Scenario:</b> {e(str(rec['scenario']))} · "
            f"<b>Mode:</b> {e(str(rec['mode']))} · <b>Status:</b> {e(str(rec['status']))}<br>"
            f"<b>Verdict:</b> {e(str(rec['verdict']))} / {e(str(rec['fault_type']))}"
            f"{' (also ' + e(', '.join(rec['other_faults'])) + ')' if rec['other_faults'] else ''}<br>"
            f"<b>Tests:</b> {rec['tests_run']} · <b>Rejected claims:</b> {rec['rejected_claims']} · "
            f"<b>Cost:</b> ${rec['cost_usd']:.4f}{asr_html}<br><b>Evaluation:</b> correct={sc.get('correct')} false_alarm={sc.get('false_alarm')}</div>{gt}"
            f"<p><a href='/report/{quote(rec['id'])}'>Open report</a> · <a href='/report/{quote(rec['id'])}?download=1'>Download report (.html)</a> · <a href='/report/{quote(rec['id'])}?format=pdf'>Download report (.pdf)</a></p>"
            f"<h2>Network health</h2><p>{e(score)}. Indicators not measured are shown as such, never assumed healthy.</p>{bar}"
            f"<table><tr><th>Indicator</th><th>State</th><th>Measurements</th></tr>{hrows}</table>"
            f"<h2>Evidence explorer</h2>{note}<table><tr><th>Id</th><th>Tool</th><th>Arguments</th><th>Observation</th><th>Result</th></tr>{trows}</table>"
            "<h2>Evidence cited in the answer</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in rec["claimed_evidence"]) + "</ul>")
    return page(rec["id"], body, "/history")


def compare_page(c: dict | None) -> bytes:
    if not c:
        return page("Compare", "<p>Pick two records on the <a href='/history'>history page</a>.</p>", "/history")
    a, b = c["a"], c["b"]

    def col(r):
        return (f"<td><a href='/run/{quote(r['id'])}'>{e(r['id'])}</a><br>{e(r['scenario'])} · {e(r['mode'])}<br>"
                f"verdict: {e(str(r['verdict']))} / {e(str(r['fault_type']))}<br>tests: {r['tests_run']} · cost ${r['cost_usd']:.4f}</td>")
    def fmt(pairs):
        return "".join(f"<li>{e(t)} <code>{e(a_)}</code></li>" for t, a_ in pairs) or "<li>none</li>"

    body = (f"<h1>Compare</h1><table><tr><th>A</th><th>B</th></tr><tr>{col(a)}{col(b)}</tr></table>"
            f"<p>{c['shared']} identical test(s) in both.</p><h2>Only in A</h2><ul>{fmt(c['only_a'])}</ul>"
            f"<h2>Only in B</h2><ul>{fmt(c['only_b'])}</ul>")
    return page("Compare", body, "/history")


def lab_page() -> bytes:
    rows = ""
    for sid, s in _SCENARIOS.items():
        rows += (f"<tr><td><code>{e(sid)}</code></td><td>{e(s.truth)}{' + ' + e(', '.join(s.also)) if s.also else ''}</td>"
                 f"<td>{e(s.ticket)}</td><td><code>python -m netwing.demo --backend sim --scenarios {e(sid)} --repeats 1 --cap 1</code></td></tr>")
    note = ("<p>Every scenario has a ground-truth label used for automatic scoring. Observations from these scenarios are "
            "<span class='tag'>SIMULATED</span> unless you run the Kathara or Linux-namespace backend (see SETUP_LINUX.md). "
            "The <code>lab_*</code> scenarios (high latency, packet loss, misleading complaint) exist only in the simulator.</p>")
    return page("Simulation lab", f"<h1>Simulation lab</h1>{note}<table><tr><th>Scenario</th><th>Ground truth</th><th>Ticket</th><th>Run it</th></tr>{rows}</table>", "/lab")


def new_page(msg: str = "", token: str = "") -> bytes:
    if site.STATE["read_only"]:
        return page("Run investigation", "<h1>Runs are disabled</h1><div class='card'>This is a read-only public demo: it cannot start investigations "
                    "and holds no API key. Browse the <a href='/history'>recorded runs</a>, or run NetWing yourself from the "
                    f"<a href='{site.REPO_URL}'>repository</a> (the simulator and a no-cost dry-run mode need no key).</div>", "/new")
    opts = "".join(f"<option>{e(sid)}</option>" for sid in _SCENARIOS)
    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    key_note = ("<p>An API key is set in this window: real model runs are possible (cost about $0.002 per run, capped at $0.50 total here).</p>"
                if have_key else "<p class='nm'>No API key in this window, so only the dry-run stub is available.</p>")
    dry = "" if have_key else " checked disabled"
    body = (f"<h1>Run an investigation</h1>{msg}{key_note}"
            "<p>Runs the scenario in the simulator with all three modes (plain, healthy_ok, netwing). Results appear in History.</p>"
            f"<form method='post' action='/new'><input type='hidden' name='token' value='{e(token)}'>Scenario <select name='scenario'>{opts}</select> "
            "Repeats <select name='repeats'><option>1</option><option>2</option><option>3</option></select> "
            f"<label><input type='checkbox' name='dry' value='1'{dry}> dry run (scripted stub, no API, not a real diagnosis)</label> "
            "<button>Start</button></form>")
    j = _JOB.get("proc")
    if j is not None:
        done = j.poll() is not None
        try:
            tail = open(_JOB["log"], encoding="utf-8", errors="replace").read()[-1500:]
        except OSError:
            tail = ""
        link = "<p><a href='/'>Open History</a></p>" if done else "<p>Refresh this page in a few seconds.</p>"
        state = "finished" if done else "running..."
        body += (f"<div class='card'><b>Last run:</b> {state} (exit {j.returncode})"
                 f"<pre style='white-space:pre-wrap'>{e(tail)}</pre>{link}</div>")
    return page("Run investigation", body, "/new")


def start_job(results_dir: str, scenario: str, repeats: int, dry: bool) -> str:
    if scenario not in _SCENARIOS:
        return "<p class='fail'>Unknown scenario.</p>"
    if _JOB.get("proc") is not None and _JOB["proc"].poll() is None:
        return "<p class='fail'>A run is already in progress.</p>"
    if not dry and not os.environ.get("ANTHROPIC_API_KEY"):
        return "<p class='fail'>No API key in this window; tick dry run or set the key and restart the UI.</p>"
    repeats = max(1, min(3, repeats))
    out = os.path.join(results_dir, f"run-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    cmd = [sys.executable, "-m", "netwing.demo", "--backend", "sim", "--scenarios", scenario,
           "--repeats", str(repeats), "--cap", "0.5", "--out", out] + (["--dry-run"] if dry else [])
    log = tempfile.NamedTemporaryFile("w", delete=False, suffix=".log")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")  # Windows consoles default to cp1252, which garbles the ± in the table
    _JOB.update(proc=subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env), log=log.name, out=out)
    return "<p>Started.</p>"


def make_handler(h: History, results_dir: str = "results", token: str | None = None,
                 allowed_hosts: frozenset[str] | None = None, read_only: bool = False, root: str | None = None):
    """Request handler. Requests whose Host header is not in `allowed_hosts` (default: loopback names) are refused, which
    defeats DNS rebinding; POSTs also need the per-process token and, when the browser sends one, a same-origin Origin.
    Pass allowed_hosts=frozenset({"*"}) only when deliberately serving beyond loopback (for example in a container).
    With read_only=True every POST is refused, the Run page explains why, and no API key is ever consulted: this is the public-demo mode.
    `root` is the project root holding docs/research/claims.json and the logs the claims name (default: the parent of the results folder)."""
    tok = _TOKEN if token is None else token
    site.STATE["read_only"] = read_only
    base = os.path.abspath(root or os.path.join(results_dir, os.pardir))
    hosts = _LOOPBACK if allowed_hosts is None else allowed_hosts

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, body: bytes, ctype="text/html; charset=utf-8", code=200, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            for k, v in {**_SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            return "*" in hosts or _host_only(self.headers.get("Host", "")) in hosts

        def _forbidden(self, why: str):
            return self._send(page("Forbidden", f"<p class='fail'>{e(why)}</p>"), code=403)

        def do_POST(self):
            u = urlparse(self.path)
            if not self._host_ok():
                return self._forbidden("Unrecognised Host header.")
            if u.path != "/new":
                return self._send(page("Not found", "<p>Not found.</p>"), code=404)
            if read_only:
                return self._forbidden("This demo is read-only: starting runs is disabled.")
            origin = self.headers.get("Origin")
            if origin is not None and origin.split("://", 1)[-1] != self.headers.get("Host", ""):
                return self._forbidden("Cross-origin request refused.")
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(page("Bad request", "<p>Bad Content-Length.</p>"), code=400)
            f = parse_qs(self.rfile.read(max(0, min(n, 4096))).decode("utf-8", "replace"))
            if not hmac.compare_digest(f.get("token", [""])[0].encode(), tok.encode()):
                return self._forbidden("Missing or wrong form token; reload the page and try again.")
            try:
                reps = int(f.get("repeats", ["1"])[0])
            except ValueError:
                reps = 1
            _JOB.pop("imported", None)
            msg = start_job(results_dir, f.get("scenario", [""])[0], reps, "dry" in f)
            return self._send(new_page(msg, tok))

        def do_HEAD(self):  # uptime monitors and some health checks probe with HEAD; answer with headers only
            ok = self._host_ok() and urlparse(self.path).path in ("/", "/healthz", "/history", "/results", "/lab", "/new")
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", "0")
            for k, v in _SECURITY_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()

        def do_GET(self):
            if not self._host_ok():
                return self._forbidden("Unrecognised Host header.")
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/":
                return self._send(site.overview_page(site.results_data(base)))
            if u.path == "/healthz":
                return self._send(b"ok", ctype="text/plain; charset=utf-8")
            if u.path == "/results":
                return self._send(site.results_page(site.results_data(base)))
            if u.path == "/history":
                return self._send(history_page(h, q))
            if u.path == "/lab":
                return self._send(lab_page())
            if u.path == "/new":
                p = None if read_only else _JOB.get("proc")
                if p is not None and p.poll() is not None and not _JOB.get("imported"):
                    h.import_dir(results_dir)
                    _JOB["imported"] = True
                return self._send(new_page(token=tok))
            if u.path.startswith("/run/"):
                rec = h.get(unquote(u.path[5:]))
                return self._send(run_page(rec) if rec else page("Not found", "<p>No such record.</p>"), code=200 if rec else 404)
            if u.path.startswith("/report/"):
                rid = unquote(u.path[8:])
                rec = h.get(rid)
                if not rec:
                    return self._send(page("Not found", "<p>No such record.</p>"), code=404)
                if q.get("format", [""])[0] == "pdf":
                    fn = f"report-{rid.replace('#', '-')}.pdf"
                    return self._send(render_pdf(rec), ctype="application/pdf",
                                      extra={"Content-Disposition": f'attachment; filename="{fn}"'})
                extra = {"Content-Disposition": f'attachment; filename="report-{rid.replace("#", "-")}.html"'} if "download" in q else None
                return self._send(render_report(rec).encode(), extra=extra)
            if u.path == "/compare":
                return self._send(compare_page(h.compare(q.get("a", [""])[0], q.get("b", [""])[0])))
            self._send(page("Not found", "<p>Not found.</p>"), code=404)

    return H


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="NetWing web UI")
    ap.add_argument("--results", default="results")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="bind address; keep 127.0.0.1 unless running in a container")
    ap.add_argument("--read-only", action="store_true", default=os.environ.get("NETWING_READONLY") == "1",
                    help="public-demo mode: never start runs or read an API key (also NETWING_READONLY=1)")
    ap.add_argument("--root", default=None, help="project root holding docs/research/claims.json and the logs it names (default: parent of --results)")
    a = ap.parse_args(argv)
    os.makedirs(a.results, exist_ok=True)
    h = History(os.path.join(a.results, "history.db"))
    print(f"imported {h.import_dir(a.results)} new run(s)")
    hosts = _LOOPBACK | {a.host.lower()} if a.host not in ("0.0.0.0", "::") else frozenset({"*"})
    base = os.path.abspath(a.root or os.path.join(a.results, os.pardir))
    threading.Thread(target=site.results_data, args=(base,), daemon=True).start()  # measure the locked numbers once, before the first visitor asks
    print(f"NetWing UI on http://{a.host}:{a.port}{' (read-only)' if a.read_only else ''}  (Ctrl+C to stop)")
    ThreadingHTTPServer((a.host, a.port), make_handler(h, a.results, allowed_hosts=frozenset(hosts), read_only=a.read_only, root=a.root)).serve_forever()


if __name__ == "__main__":
    main()
