import json
import os
import re
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from netwing.agent import TOOLS, _system_prompt, _tools_for
from netwing.backend import ToolResult
from netwing.controller import Controller
from netwing.history import History
from netwing.pdfexport import render_pdf
from netwing.records import build_record
from netwing.scenarios import get_scenario
from netwing.scoring import score
from netwing.webui import make_handler

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _r(tool, ok, cat, **args):
    return ToolResult(tool, args, "out", ok, cat)


def _ctrl(*results):
    c = Controller(max_tests=12)
    for r in results:
        c.observe(r)
    return c


DNS_FAIL = _r("dns_lookup", False, "dns", src="h1", name="web.lab")
PING_OK = _r("ping", True, "connectivity", src="h1", dst="h2")
PORT_OK = _r("port_check", True, "port", src="h1", dst="h2", port=80)


def test_fault_reproduced_with_all_areas_is_confirmed():
    c = _ctrl(DNS_FAIL, PING_OK, PORT_OK, DNS_FAIL)
    assert c.assess("fault", "dns_failure", ["E1", "E4"])[0] == "confirmed"


def test_fault_seen_once_is_only_suspected_with_reason():
    level, why = _ctrl(DNS_FAIL, PING_OK, PORT_OK).assess("fault", "dns_failure", ["E1"])
    assert level == "suspected" and "once" in why


def test_fault_with_untested_areas_is_suspected():
    level, why = _ctrl(DNS_FAIL, DNS_FAIL).assess("fault", "dns_failure", ["E1"])
    assert level == "suspected" and "never tested" in why


def test_fault_citing_nothing_failing_is_suspected():
    assert _ctrl(PING_OK).assess("fault", "dns_failure", ["E1"])[0] == "suspected"


def test_healthy_levels():
    assert _ctrl(PING_OK, PORT_OK, _r("dns_lookup", True, "dns", src="h1", name="web.lab")).assess("healthy")[0] == "confirmed"
    assert _ctrl(PING_OK).assess("healthy")[0] == "suspected"
    assert _ctrl(DNS_FAIL, PING_OK).assess("healthy")[0] == "inconclusive"


def test_no_answer_and_inconclusive_verdict_are_inconclusive():
    assert _ctrl(PING_OK).assess(None)[0] == "inconclusive"
    assert _ctrl(PING_OK).assess("inconclusive")[0] == "inconclusive"


def test_assess_never_changes_decisions():
    c = _ctrl(DNS_FAIL, PING_OK)
    before = (c.decide(), c.allow_claim("fault", "dns_failure", ["E1"]))
    c.assess("fault", "dns_failure", ["E1"])
    assert (c.decide(), c.allow_claim("fault", "dns_failure", ["E1"])) == before


def test_inconclusive_claim_is_gated():
    ok, why = _ctrl(PING_OK).allow_claim("inconclusive", "none", [])
    assert not ok and "three tests" in why
    # a confirmed failure must be reported as a fault
    c = _ctrl(DNS_FAIL, PING_OK, PORT_OK, DNS_FAIL)
    assert not c.allow_claim("inconclusive", "none", [])[0]
    # everything passes: must say healthy
    c = _ctrl(PING_OK, PORT_OK, _r("dns_lookup", True, "dns", src="h1", name="web.lab"))
    assert not c.allow_claim("inconclusive", "none", [])[0]
    # one unconfirmed failure and three tests: allowed
    assert _ctrl(DNS_FAIL, PING_OK, PORT_OK).allow_claim("inconclusive", "none", [])[0]


def test_default_tools_and_prompt_are_unchanged_without_the_flag():
    sc = get_scenario("healthy_false_alarm")
    assert _tools_for(sc) is TOOLS
    assert "inconclusive" not in TOOLS[-1]["input_schema"]["properties"]["verdict"]["enum"]
    assert "inconclusive" not in _system_prompt("netwing", sc, True)


def test_flag_adds_inconclusive_to_schema_and_prompt_without_mutating_defaults():
    sc = get_scenario("healthy_false_alarm")
    tools = _tools_for(sc, allow_inconclusive=True)
    assert "inconclusive" in tools[-1]["input_schema"]["properties"]["verdict"]["enum"]
    assert "inconclusive" not in TOOLS[-1]["input_schema"]["properties"]["verdict"]["enum"]
    assert "inconclusive" in _system_prompt("netwing", sc, True, allow_inconclusive=True)


def test_scoring_counts_inconclusive_as_no_answer_not_false_alarm():
    s = score(get_scenario("healthy_false_alarm"), {"verdict": "inconclusive", "fault_type": "none", "evidence": []})
    assert s.inconclusive and s.no_answer and not s.correct and not s.false_alarm


def _run(tests, answer):
    return {"scenario_id": "healthy_false_alarm", "mode": "netwing", "model": "m", "status": "answered", "tests_run": len(tests),
            "answer": answer, "tests": tests, "transcript": [{"role": "user", "content": "ticket text"}]}


def _t(i, tool, ok, cat, **args):
    return {"id": f"E{i}", "tool": tool, "args": args, "output": "o", "ok": ok, "category": cat, "evidence": True, "ts": 1.0}


def test_record_carries_assurance_for_structured_logs_only():
    tests = [_t(1, "ping", True, "connectivity", src="h1", dst="web.lab"),
             _t(2, "dns_lookup", True, "dns", src="h1", name="web.lab"),
             _t(3, "port_check", True, "port", src="h1", dst="web.lab", port=80)]
    rec = build_record(_run(tests, {"verdict": "healthy", "fault_type": "none", "evidence": ["E1"]}), "x#1")
    assert rec["assurance"]["level"] == "confirmed"
    old = json.loads(open(os.path.join(FIX, "run-sample.jsonl"), encoding="utf-8").readline())
    assert build_record(old, "x#2")["assurance"] is None


def _rec(n_tests=3, text="o"):
    tests = [_t(i + 1, "ping", i % 2 == 0, "connectivity", src="h1", dst="web.lab") for i in range(n_tests)]
    for t in tests:
        t["output"] = text
    return build_record(_run(tests, {"verdict": "fault", "fault_type": "route_failure", "evidence": ["E2"]}), "x#1")


def test_pdf_is_structurally_valid_and_xref_offsets_are_exact():
    pdf = render_pdf(_rec())
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    xref_at = int(re.search(rb"startxref\n(\d+)\n", pdf).group(1))
    assert pdf[xref_at:xref_at + 4] == b"xref"
    entries = re.findall(rb"(\d{10}) 00000 n ", pdf)
    assert entries
    for i, off in enumerate(entries, 1):
        assert pdf[int(off):].startswith(b"%d 0 obj" % i)
    assert b"Network investigation report" in pdf and b"Evidence assurance" in pdf


def test_pdf_paginates_long_reports_and_escapes_special_characters():
    pdf = render_pdf(_rec(n_tests=60, text="odd (paren) \\ back ✓ tick é"))
    pages = len(re.findall(rb"/Type /Page /Parent", pdf))
    assert pages >= 2
    assert b"page 2 of %d" % pages in pdf
    assert b"\\(paren\\)" in pdf and b"\\\\ back" in pdf


def test_report_route_serves_pdf(tmp_path):
    with open(os.path.join(FIX, "run-sample.jsonl"), encoding="utf-8") as f, open(tmp_path / "run-1.jsonl", "w") as out:
        out.write(f.readline())
    h = History(str(tmp_path / "h.db"))
    h.import_dir(str(tmp_path))
    rid = h.list()[0]["id"]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(h))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        from urllib.parse import quote
        resp = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/report/{quote(rid)}?format=pdf")
        assert resp.headers["Content-Type"] == "application/pdf"
        assert "attachment" in resp.headers["Content-Disposition"]
        assert resp.read().startswith(b"%PDF-1.4")
        page = urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/run/{quote(rid)}").read().decode()
        assert "Evidence assurance" in page and "format=pdf" in page
    finally:
        srv.shutdown()
