import json
import os
import shutil
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from netwing.health import compute_health
from netwing.history import History
from netwing.records import build_record
from netwing.report import render_report
from netwing.webui import make_handler

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _runs():
    return [json.loads(l) for l in open(os.path.join(FIX, "run-sample.jsonl"), encoding="utf-8") if l.strip()]


def test_record_from_old_log_rebuilds_tests_from_transcript():
    rec = build_record(_runs()[0], "x#1")
    assert rec["parsed_from_text"] is True
    assert len(rec["tests"]) == rec["tests_run"] > 0
    assert rec["tests"][0]["id"] == "E1" and rec["tests"][0]["tool"]
    assert rec["ticket"].startswith("Users on")


def test_record_prefers_structured_tests_when_present():
    run = _runs()[0]
    run["tests"] = [{"id": "E1", "tool": "ping", "args": {"src": "h1", "dst": "h2"}, "output": "ok", "ok": True,
                     "category": "connectivity", "evidence": True, "ts": 1.0}]
    rec = build_record(run, "x#1")
    assert rec["parsed_from_text"] is False and len(rec["tests"]) == 1


def test_health_uses_measured_only_and_never_assumes_healthy():
    tests = [{"tool": "dns_lookup", "args": {}, "ok": False}, {"tool": "ping", "args": {"dst": "h2"}, "ok": True}]
    h = compute_health(tests)
    states = {i["key"]: i["state"] for i in h["indicators"]}
    assert states["dns_resolution"] == "fail" and states["reachability"] == "ok"
    assert states["port_availability"] == "not_measured" and states["gateway_reachability"] == "not_measured"
    assert h["measured"] == 2 and h["score"] == 50  # unmeasured indicators do not count as healthy


def test_health_with_nothing_measured_has_no_score():
    assert compute_health([])["score"] is None


def test_health_ignores_non_evidence_results():
    t = [{"tool": "port_check", "args": {}, "ok": False, "evidence": False}]
    assert compute_health(t)["indicators"][2]["state"] == "not_measured"


def test_report_has_required_sections_and_escapes_html():
    rec = build_record(_runs()[0], "x#1")
    rec["ticket"] = "<script>alert(1)</script>"
    html = render_report(rec)
    for s in ("Problem", "Root cause", "Tests performed", "Supporting evidence", "Limitations", "Recommendations", "SIMULATED"):
        assert s in html
    assert "<script>alert(1)</script>" not in html


def test_history_import_is_idempotent_and_compare_works(tmp_path):
    shutil.copy(os.path.join(FIX, "run-sample.jsonl"), tmp_path / "run-20260101-000000.jsonl")
    h = History(str(tmp_path / "h.db"))
    assert h.import_dir(str(tmp_path)) == 3
    assert h.import_dir(str(tmp_path)) == 0
    ids = [r["id"] for r in h.list()]
    assert len(ids) == 3 and h.get(ids[0])["tests"]
    c = h.compare(ids[0], ids[1])
    assert c and "shared" in c and h.compare(ids[0], "nope") is None
    assert h.list(mode="nomode") == []


def test_web_ui_pages_respond(tmp_path):
    shutil.copy(os.path.join(FIX, "run-sample.jsonl"), tmp_path / "run-20260101-000000.jsonl")
    h = History(str(tmp_path / "h.db"))
    h.import_dir(str(tmp_path))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(h))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    rid = h.list()[0]["id"].replace("#", "%23")
    try:
        for path, needle in [("/", "Investigation history"), ("/lab", "Ground truth"), (f"/run/{rid}", "Evidence explorer"),
                             (f"/report/{rid}", "Recommendations")]:
            body = urllib.request.urlopen(base + path).read().decode()
            assert needle in body, path
        try:
            urllib.request.urlopen(base + "/run/missing")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        srv.shutdown()


def test_history_orders_newest_file_first_and_numeric_run_order(tmp_path):
    line = open(os.path.join(FIX, "run-sample.jsonl"), encoding="utf-8").readline()
    for name in ("run-20260101-000000", "run-20260202-000000"):
        (tmp_path / f"{name}.jsonl").write_text(line * 12, encoding="utf-8")
    h = History(str(tmp_path / "h.db"))
    h.import_dir(str(tmp_path))
    rows, total = h.list_page(limit=5)
    assert total == 24
    assert [r["id"] for r in rows] == [f"run-20260202-000000#{n}" for n in (1, 2, 3, 4, 5)]
    assert h.list_page(limit=24)[0][12]["id"] == "run-20260101-000000#1"


def test_stats_exclude_dry_run_records(tmp_path):
    lines = [json.loads(l) for l in open(os.path.join(FIX, "run-sample.jsonl"), encoding="utf-8") if l.strip()]
    lines[0]["model"] = "dry-run"
    (tmp_path / "run-20260101-000000.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    h = History(str(tmp_path / "h.db"))
    h.import_dir(str(tmp_path))
    assert sum(r["runs"] for r in h.stats()) == 2
    assert sum(r["runs"] for r in h.stats(real_only=False)) == 3
    assert any(r.get("model") == "dry-run" for r in h.list())


def test_run_from_ui_dry_run_adds_history_and_is_flagged(tmp_path):
    import time
    import urllib.parse

    h = History(str(tmp_path / "h.db"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(h, str(tmp_path)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        form = urllib.request.urlopen(base + "/new").read().decode()
        assert "Run an investigation" in form
        import re

        token = re.search(r"name='token' value='([^']+)'", form).group(1)  # the form carries the per-process token
        data = urllib.parse.urlencode({"scenario": "dns_failure", "repeats": "1", "dry": "1", "token": token}).encode()
        assert "Started" in urllib.request.urlopen(base + "/new", data).read().decode()
        from netwing import webui

        for _ in range(60):
            if webui._JOB["proc"].poll() is not None:
                break
            time.sleep(0.5)
        assert webui._JOB["proc"].returncode == 0
        urllib.request.urlopen(base + "/new").read()  # triggers the import
        rows = h.list()
        assert len(rows) == 3 and all(r["model"] == "dry-run" for r in rows)
        assert "DRY RUN stub" in urllib.request.urlopen(base + "/").read().decode()
    finally:
        srv.shutdown()


def test_run_from_ui_rejects_unknown_scenario(tmp_path):
    from netwing.webui import start_job

    assert "Unknown scenario" in start_job(str(tmp_path), "../../etc/passwd", 1, True)
