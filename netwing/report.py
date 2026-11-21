"""Investigation report (standalone HTML; open in a browser and print to PDF for a PDF copy)."""
from __future__ import annotations

from html import escape as e

from .health import compute_health

_RECOMMEND = {
    "dns_failure": ["Check that the DNS resolver is running and reachable from the affected hosts.",
                    "Verify the zone contains the record for the failing name.",
                    "Until fixed, test with the server's IP address to confirm the rest of the path works."],
    "route_failure": ["Inspect the routing table on the router and the affected hosts for the missing or wrong route.",
                      "Confirm the next hop is reachable and the interface is up.",
                      "Compare traceroute from several hosts to see where the path stops."],
    "port_blocked": ["Review firewall rules on the server and on devices along the path for the affected port.",
                     "Confirm the service is listening on that port on the server itself.",
                     "Re-test the port from a second host to separate a path block from a server problem."],
    "healthy": ["No fault was found in the tests performed; check the original complaint for details the tests did not cover.",
                "If the problem recurs, repeat the tests while it is happening (it may be intermittent)."],
}
_CSS = ("body{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;color:#222}"
        "h1{font-size:1.5rem}h2{font-size:1.1rem;border-bottom:1px solid #ccc;padding-bottom:.2rem;margin-top:1.6rem}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:4px 8px;text-align:left;"
        "vertical-align:top;font-size:13px}.pass{color:#0a6b2d}.fail{color:#b00020}.tag{background:#fff3cd;"
        "padding:2px 8px;border-radius:4px;font-size:12px}code{background:#f2f2f2;padding:0 3px}")


def _limitations(rec: dict) -> list[str]:
    out = []
    if rec["simulated"]:
        out.append("These observations come from a SIMULATED network, not from real measurements.")
    if rec["parsed_from_text"]:
        out.append("Pass/fail for each test was parsed from the tool output text, not recorded by the tool.")
    if rec["status"] != "answered":
        out.append(f"The investigation ended with status '{rec['status']}', so no accepted conclusion exists.")
    if rec["rejected_claims"]:
        out.append(f"{rec['rejected_claims']} conclusion(s) were rejected by the evidence rules before this one.")
    out.append("Only the tests listed here were run; faults outside their reach would not appear.")
    return out


def render_report(rec: dict) -> str:
    health = compute_health(rec["tests"])
    rows = "".join(
        f"<tr><td>{e(t['id'])}</td><td>{e(t['tool'])}</td><td><code>{e(str(t['args']))}</code></td>"
        f"<td>{e(t['output']).replace(chr(10), '<br>')}</td>"
        f"<td class='{'pass' if t['ok'] else 'fail'}'>{'pass' if t['ok'] else 'fail'}</td></tr>"
        for t in rec["tests"]
    )
    hrows = "".join(
        f"<tr><td>{e(i['label'])}</td><td>{e(i['state'].replace('_', ' '))}</td><td>{i['measurements']}</td></tr>"
        for i in health["indicators"]
    )
    cause = rec["fault_type"] or ("none found" if rec["verdict"] == "healthy" else "no conclusion")
    if rec["other_faults"]:
        cause += " (also: " + ", ".join(rec["other_faults"]) + ")"
    recs = "".join(f"<li>{e(x)}</li>" for x in _RECOMMEND.get(rec["fault_type"] or "healthy", _RECOMMEND["healthy"]))
    ev = "".join(f"<li>{e(x)}</li>" for x in rec["claimed_evidence"]) or "<li>none</li>"
    lim = "".join(f"<li>{e(x)}</li>" for x in _limitations(rec))
    score = "n/a" if health["score"] is None else f"{health['score']}/100 ({health['measured']} of {health['total']} indicators measured)"
    sim = "<span class='tag'>SIMULATED</span> " if rec["simulated"] else ""
    return (f"<!doctype html><meta charset='utf-8'><title>Report {e(rec['id'])}</title><style>{_CSS}</style>"
            f"<h1>{sim}Network investigation report</h1><p>Record <code>{e(rec['id'])}</code> · scenario "
            f"<code>{e(str(rec['scenario']))}</code> · mode <code>{e(str(rec['mode']))}</code> · model "
            f"<code>{e(str(rec['model']))}</code></p>"
            f"<h2>Problem</h2><p>{e(rec['ticket'])}</p>"
            f"<h2>Root cause (diagnosis)</h2><p><b>{e(str(rec['verdict']))}</b>: {e(cause)}</p>"
            f"<h2>Supporting evidence cited</h2><ul>{ev}</ul>"
            f"<h2>Tests performed and observations ({len(rec['tests'])})</h2>"
            f"<table><tr><th>Id</th><th>Tool</th><th>Arguments</th><th>Observation</th><th>Result</th></tr>{rows}</table>"
            f"<h2>Network health (measured values only)</h2><p>Score: {e(score)}. Unmeasured indicators are not assumed healthy.</p>"
            f"<table><tr><th>Indicator</th><th>State</th><th>Measurements</th></tr>{hrows}</table>"
            f"<h2>Limitations</h2><ul>{lim}</ul>"
            f"<h2>Recommendations (general guidance)</h2><ul>{recs}</ul>")
