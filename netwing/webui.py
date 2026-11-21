"""NetWing web UI (stdlib only, no extra dependencies).

    python -m netwing.webui --results results --port 8765

Pages: history list with filters, investigation detail (Evidence Explorer, health, report download),
compare two investigations, simulation lab (scenario browser with ground truth).
"""
from __future__ import annotations

import argparse
import os
from html import escape as e
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

from .health import compute_health
from .history import History
from .report import render_report
from .scenarios import _SCENARIOS

CSS = ("body{font:15px/1.5 system-ui,sans-serif;margin:0;color:#222;background:#f6f7f9}"
       "nav{background:#1f2a44;padding:10px 24px}nav a{color:#fff;margin-right:18px;text-decoration:none}"
       "main{max-width:1000px;margin:20px auto;padding:0 16px}table{border-collapse:collapse;width:100%;background:#fff}"
       "td,th{border:1px solid #d8dbe0;padding:5px 9px;text-align:left;vertical-align:top;font-size:13px}"
       ".pass{color:#0a6b2d;font-weight:600}.fail{color:#b00020;font-weight:600}.mixed{color:#9a6700;font-weight:600}"
       ".nm{color:#666}.tag{background:#fff3cd;padding:2px 8px;border-radius:4px;font-size:12px}"
       ".card{background:#fff;border:1px solid #d8dbe0;border-radius:6px;padding:12px 16px;margin:12px 0}"
       "code{background:#eef0f3;padding:0 4px}a{color:#1a56c4}")


def page(title: str, body: str) -> bytes:
    return (f"<!doctype html><meta charset='utf-8'><title>{e(title)}</title><style>{CSS}</style>"
            f"<nav><a href='/'>History</a><a href='/lab'>Simulation lab</a></nav><main>{body}</main>").encode()


def _sim(r) -> str:
    return "<span class='tag'>SIMULATED</span>" if r else "real"


def history_page(h: History, q: dict) -> bytes:
    sc, mode = q.get("scenario", [""])[0], q.get("mode", [""])[0]
    rows, total = h.list_page(sc, mode)
    opts = "<option value=''>All</option>" + "".join(f"<option{' selected' if s == sc else ''}>{e(s)}</option>" for s in h.scenarios())
    modes = "<option value=''>All</option>" + "".join(f"<option{' selected' if m == mode else ''}>{m}</option>" for m in ["plain", "healthy_ok", "netwing"])
    body = (f"<h1>Investigation history</h1><form>Scenario <select name='scenario'>{opts}</select> "
            f"Mode <select name='mode'>{modes}</select> <button>Filter</button></form><p>Showing {len(rows)} of {total} (newest first; filter to narrow)</p>"
            "<form action='/compare'><table><tr><th>A</th><th>B</th><th>Record</th><th>Scenario</th><th>Mode</th>"
            "<th>Verdict</th><th>Correct</th><th>Tests</th><th>Cost</th><th>Network</th></tr>")
    for r in rows:
        rid = e(r["id"])
        body += (f"<tr><td><input type='radio' name='a' value='{rid}'></td><td><input type='radio' name='b' value='{rid}'></td>"
                 f"<td><a href='/run/{quote(r['id'])}'>{rid}</a></td><td>{e(r['scenario'])}</td><td>{e(r['mode'])}</td>"
                 f"<td>{e(str(r['verdict']))}</td><td>{'yes' if r['correct'] else 'no'}</td><td>{r['tests_run']}</td>"
                 f"<td>${r['cost']:.4f}</td><td>{_sim(r['simulated'])}</td></tr>")
    body += "</table><p><button>Compare selected A and B</button></p></form>"
    return page("History", body)


def run_page(rec: dict) -> bytes:
    health = compute_health(rec["tests"])
    hrows = "".join(
        f"<tr><td>{e(i['label'])}</td><td class='{i['state'] if i['state'] != 'not_measured' else 'nm'}'>"
        f"{e(i['state'].replace('_', ' '))}</td><td>{i['measurements']}</td></tr>" for i in health["indicators"])
    score = "not enough measurements" if health["score"] is None else f"{health['score']}/100 from {health['measured']} of {health['total']} indicators"
    trows = "".join(
        f"<tr><td>{e(t['id'])}</td><td>{e(t['tool'])}</td><td><code>{e(str(t['args']))}</code></td>"
        f"<td>{e(t['output']).replace(chr(10), '<br>')}</td><td class='{'pass' if t['ok'] else 'fail'}'>{'pass' if t['ok'] else 'fail'}</td></tr>"
        for t in rec["tests"])
    note = "<p class='nm'>Pass/fail was parsed from tool output text (older log).</p>" if rec["parsed_from_text"] else ""
    sc = rec["score"]
    truth = _SCENARIOS.get(rec["scenario"])
    gt = f"<p>Ground truth: <code>{e(truth.truth)}</code>{' + ' + ', '.join(truth.also) if truth.also else ''}</p>" if truth else ""
    body = (f"<h1>{e(rec['id'])} {_sim(rec['simulated'])}</h1>"
            f"<div class='card'><b>Ticket:</b> {e(rec['ticket'])}<br><b>Scenario:</b> {e(str(rec['scenario']))} · "
            f"<b>Mode:</b> {e(str(rec['mode']))} · <b>Status:</b> {e(str(rec['status']))}<br>"
            f"<b>Verdict:</b> {e(str(rec['verdict']))} / {e(str(rec['fault_type']))}"
            f"{' (also ' + e(', '.join(rec['other_faults'])) + ')' if rec['other_faults'] else ''}<br>"
            f"<b>Tests:</b> {rec['tests_run']} · <b>Rejected claims:</b> {rec['rejected_claims']} · "
            f"<b>Cost:</b> ${rec['cost_usd']:.4f}<br><b>Evaluation:</b> correct={sc.get('correct')} false_alarm={sc.get('false_alarm')}</div>{gt}"
            f"<p><a href='/report/{quote(rec['id'])}'>Open report</a> · <a href='/report/{quote(rec['id'])}?download=1'>Download report (.html)</a></p>"
            f"<h2>Network health</h2><p>{e(score)}. Indicators not measured are shown as such, never assumed healthy.</p>"
            f"<table><tr><th>Indicator</th><th>State</th><th>Measurements</th></tr>{hrows}</table>"
            f"<h2>Evidence explorer</h2>{note}<table><tr><th>Id</th><th>Tool</th><th>Arguments</th><th>Observation</th><th>Result</th></tr>{trows}</table>"
            "<h2>Evidence cited in the answer</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in rec["claimed_evidence"]) + "</ul>")
    return page(rec["id"], body)


def compare_page(c: dict | None) -> bytes:
    if not c:
        return page("Compare", "<p>Pick two records on the history page.</p>")
    a, b = c["a"], c["b"]

    def col(r):
        return (f"<td><a href='/run/{quote(r['id'])}'>{e(r['id'])}</a><br>{e(r['scenario'])} · {e(r['mode'])}<br>"
                f"verdict: {e(str(r['verdict']))} / {e(str(r['fault_type']))}<br>tests: {r['tests_run']} · cost ${r['cost_usd']:.4f}</td>")
    fmt = lambda s: "".join(f"<li>{e(t)} <code>{e(a_)}</code></li>" for t, a_ in s) or "<li>none</li>"
    body = (f"<h1>Compare</h1><table><tr><th>A</th><th>B</th></tr><tr>{col(a)}{col(b)}</tr></table>"
            f"<p>{c['shared']} identical test(s) in both.</p><h2>Only in A</h2><ul>{fmt(c['only_a'])}</ul>"
            f"<h2>Only in B</h2><ul>{fmt(c['only_b'])}</ul>")
    return page("Compare", body)


def lab_page() -> bytes:
    rows = ""
    for sid, s in _SCENARIOS.items():
        rows += (f"<tr><td><code>{e(sid)}</code></td><td>{e(s.truth)}{' + ' + e(', '.join(s.also)) if s.also else ''}</td>"
                 f"<td>{e(s.ticket)}</td><td><code>python -m netwing.demo --backend sim --scenarios {e(sid)} --repeats 1 --cap 1</code></td></tr>")
    note = ("<p>Every scenario has a ground-truth label used for automatic scoring. Observations from these scenarios are "
            "<span class='tag'>SIMULATED</span> unless you run the Kathara or Linux-namespace backend (see SETUP_LINUX.md). "
            "Not yet available: high-latency, packet-loss and misleading-complaint scenarios.</p>")
    return page("Simulation lab", f"<h1>Simulation lab</h1>{note}<table><tr><th>Scenario</th><th>Ground truth</th><th>Ticket</th><th>Run it</th></tr>{rows}</table>")


def make_handler(h: History):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, body: bytes, ctype="text/html; charset=utf-8", code=200, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/":
                return self._send(history_page(h, q))
            if u.path == "/lab":
                return self._send(lab_page())
            if u.path.startswith("/run/"):
                rec = h.get(unquote(u.path[5:]))
                return self._send(run_page(rec) if rec else page("Not found", "<p>No such record.</p>"), code=200 if rec else 404)
            if u.path.startswith("/report/"):
                rid = unquote(u.path[8:])
                rec = h.get(rid)
                if not rec:
                    return self._send(page("Not found", "<p>No such record.</p>"), code=404)
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
    a = ap.parse_args(argv)
    os.makedirs(a.results, exist_ok=True)
    h = History(os.path.join(a.results, "history.db"))
    print(f"imported {h.import_dir(a.results)} new run(s)")
    print(f"NetWing UI on http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(h)).serve_forever()


if __name__ == "__main__":
    main()
