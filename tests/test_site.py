"""The read-only public demo: runs are refused, the pages render from real or missing logs, and the numbers shown are measured, not typed."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from netwing import site
from netwing.history import History
from netwing.webui import make_handler


def _row(mode, wrong=False, ts=0):
    """A run on a healthy scenario; `wrong` means the agent declared a fault there (a false alarm)."""
    return {"scenario_id": "fx_blip", "mode": mode, "tests": [{"ts": ts}], "tests_run": 3, "cost_usd": 0.0,
            "answer": {"verdict": "fault" if wrong else "healthy", "fault_type": "dns" if wrong else "none"},
            "score": {"no_answer": False, "false_alarm": wrong, "correct": not wrong}}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "results").mkdir()
    rows = [_row("plain", wrong=True), _row("plain"), _row("netwing"), _row("netwing")]
    (tmp_path / "results" / "log.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    claims = [{"id": "heldout.default.plain.false_fault", "doc": "docs/x.md", "file": "results/log.jsonl", "invocation": 0, "mode": "plain",
               "metric": "false_fault", "k": 1, "n": 2},
              {"id": "heldout.default.netwing.false_fault", "doc": "docs/x.md", "file": "results/log.jsonl", "invocation": 0, "mode": "netwing",
               "metric": "false_fault", "k": 1, "n": 2},  # deliberately wrong: the log has 0/2
              {"id": "fresh.netwing.tests", "doc": "docs/x.md", "file": "results/missing.jsonl", "invocation": 0, "mode": "netwing",
               "metric": "tests", "mean": 3.0}]
    (tmp_path / "docs" / "research" / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
    return tmp_path


def _serve(tmp_path, **kw):
    h = History(str(tmp_path / "results" / "h.db"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(h, str(tmp_path / "results"), root=str(tmp_path), **kw))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _get(url):
    return urllib.request.urlopen(url).read().decode()


def test_measure_recomputes_from_the_log_and_flags_differences_and_missing_logs(root):
    site._CACHE.clear()
    data = {d["id"]: d for d in site.results_data(str(root))}
    assert data["heldout.default.plain.false_fault"]["status"] == "ok" and data["heldout.default.plain.false_fault"]["measured"] == "1/2"
    bad = data["heldout.default.netwing.false_fault"]
    assert bad["status"] == "FAIL" and bad["documented"] == "1/2" and bad["measured"] == "0/2"
    assert data["fresh.netwing.tests"]["status"] == "SKIP"


def test_read_only_refuses_runs_hides_the_run_page_and_needs_no_key(root, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    srv, base = _serve(root, read_only=True)
    try:
        req = urllib.request.Request(base + "/new", data=b"scenario=dns_failure&dry=1&token=x", method="POST")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req)
        assert ei.value.code == 403 and "read-only" in ei.value.read().decode().lower()
        page = _get(base + "/new")
        assert "Runs are disabled" in page and "name='token'" not in page and "<form method='post'" not in page
        assert "Run investigation</a>" not in _get(base + "/")  # nav item hidden
        assert "Read-only demo" in _get(base + "/history")
    finally:
        srv.shutdown()


def test_default_mode_still_offers_runs(root):
    srv, base = _serve(root)
    try:
        assert "Run investigation</a>" in _get(base + "/") and "Read-only demo" not in _get(base + "/")
    finally:
        srv.shutdown()


def test_overview_results_and_health_endpoints_render_measured_numbers(root):
    srv, base = _serve(root, read_only=True)
    try:
        assert _get(base + "/healthz") == "ok"
        over = _get(base + "/")
        assert "<s>1/2</s>" in over and "role='img'" in over  # tile and chart come from the log
        assert "1 differ from the documents" in over  # the deliberately wrong claim is surfaced on the front page too
        res = _get(base + "/results")
        assert "differs" in res and "log not shipped" in res and "reproduces" in res and "Do not quote" in res
    finally:
        srv.shutdown()


def test_pages_degrade_gracefully_without_claims_or_logs(tmp_path):
    (tmp_path / "results").mkdir()
    srv, base = _serve(tmp_path, read_only=True)
    try:
        assert "No result logs found" in _get(base + "/")
        assert "No claims file" in _get(base + "/results")
    finally:
        srv.shutdown()


def test_chart_has_accessible_description_and_labels_every_value(root):
    site._CACHE.clear()
    svg = site.false_alarm_chart(site.results_data(str(root)))
    assert "role='img'" in svg and "<desc" in svg and "1/2" in svg and "plain agent" in svg
    assert site.false_alarm_chart([]) == ""


def test_pages_set_security_headers_and_escape_titles(root):
    srv, base = _serve(root, read_only=True)
    try:
        r = urllib.request.urlopen(base + "/")
        assert "default-src 'none'" in r.headers["Content-Security-Policy"] and "base-uri 'none'" in r.headers["Content-Security-Policy"]
        assert "<script" not in r.read().decode().lower()
    finally:
        srv.shutdown()
    assert b"<script>" not in site.page("<script>alert(1)</script>", "x")


def test_head_requests_work_for_uptime_monitors(root):
    srv, base = _serve(root, read_only=True)
    try:
        for path, code in [("/healthz", 200), ("/", 200), ("/nope", 404)]:
            try:
                r = urllib.request.urlopen(urllib.request.Request(base + path, method="HEAD"))
                got = r.status
            except urllib.error.HTTPError as ex:
                got = ex.code
            assert got == code, path
    finally:
        srv.shutdown()
