"""Security hardening: web UI request checks, Kathara argument validation, history thread safety.

None of these change what the controller decides; they close the input paths found in the audit.
"""
import http.client
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from netwing import webui
from netwing.history import History
from netwing.kathara import KatharaNetwork
from netwing.webui import make_handler


def _server(tmp_path, **kw):
    h = History(str(tmp_path / "h.db"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(h, str(tmp_path), **kw))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _req(srv, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    data = r.read().decode("utf-8", "replace")
    c.close()
    return r.status, data, dict(r.getheaders())


FORM = urllib.parse.urlencode({"scenario": "dns_failure", "repeats": "1", "dry": "1"})


def _no_job(monkeypatch):
    monkeypatch.setattr(webui, "_JOB", {})


# ---- web UI ---------------------------------------------------------------------------------------------------

def test_post_without_token_is_rejected_and_starts_nothing(tmp_path, monkeypatch):
    _no_job(monkeypatch)
    srv = _server(tmp_path)
    try:
        status, _, _ = _req(srv, "POST", "/new", FORM, {"Content-Type": "application/x-www-form-urlencoded"})
        assert status == 403
        assert "proc" not in webui._JOB
    finally:
        srv.shutdown()


def test_post_with_wrong_token_is_rejected(tmp_path, monkeypatch):
    _no_job(monkeypatch)
    srv = _server(tmp_path)
    try:
        status, _, _ = _req(srv, "POST", "/new", FORM + "&token=wrong", {"Content-Type": "application/x-www-form-urlencoded"})
        assert status == 403 and "proc" not in webui._JOB
    finally:
        srv.shutdown()


def test_post_from_foreign_origin_is_rejected_even_with_valid_token(tmp_path, monkeypatch):
    _no_job(monkeypatch)
    srv = _server(tmp_path, token="tok")
    try:
        status, _, _ = _req(srv, "POST", "/new", FORM + "&token=tok",
                            {"Content-Type": "application/x-www-form-urlencoded", "Origin": "http://evil.example"})
        assert status == 403 and "proc" not in webui._JOB
    finally:
        srv.shutdown()


def test_unknown_host_header_is_rejected_for_get_and_post(tmp_path):
    srv = _server(tmp_path, token="tok")  # DNS-rebinding defence
    try:
        assert _req(srv, "GET", "/", headers={"Host": "evil.example"})[0] == 403
        assert _req(srv, "POST", "/new", FORM + "&token=tok", {"Host": "evil.example"})[0] == 403
    finally:
        srv.shutdown()


def test_form_carries_the_token_and_valid_post_works(tmp_path, monkeypatch):
    _no_job(monkeypatch)
    srv = _server(tmp_path, token="tok123")
    try:
        status, page, _ = _req(srv, "GET", "/new")
        assert status == 200 and "name='token' value='tok123'" in page
        port = srv.server_address[1]
        status, page, _ = _req(srv, "POST", "/new", FORM + "&token=tok123",
                               {"Content-Type": "application/x-www-form-urlencoded", "Origin": f"http://127.0.0.1:{port}"})
        assert status == 200 and "Started" in page
        webui._JOB["proc"].wait(timeout=60)
    finally:
        srv.shutdown()


def test_malformed_content_length_is_a_400_not_a_crash(tmp_path):
    srv = _server(tmp_path, token="tok")
    try:
        status, _, _ = _req(srv, "POST", "/new", "x", {"Content-Length": "abc"})
        assert status == 400
    finally:
        srv.shutdown()


def test_responses_carry_hardening_headers(tmp_path):
    srv = _server(tmp_path)
    try:
        _, _, hdr = _req(srv, "GET", "/lab")
        low = {k.lower(): v for k, v in hdr.items()}
        assert low["x-content-type-options"] == "nosniff"
        assert low["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in low["content-security-policy"]
    finally:
        srv.shutdown()


# ---- Kathara argument validation ----------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["-x", "--version", "web.lab -t AXFR", "a b", "", "web.lab;id", "$(id)", "a" * 300, "web.lab\n"])
def test_dns_lookup_rejects_names_that_could_become_dig_options(name):
    seen = []
    n = KatharaNetwork("lab", lambda cmd, t: seen.append(cmd) or "")
    r = n.dns_lookup("h1", name)
    assert r.category == "invalid" and not r.ok
    assert seen == []  # nothing was executed


@pytest.mark.parametrize("name", [["web.lab"], None, 5])
def test_dns_lookup_rejects_non_string_names(name):
    n = KatharaNetwork("lab", lambda cmd, t: "")
    assert n.dns_lookup("h1", name).category == "invalid"


def test_dns_lookup_still_accepts_ordinary_names():
    seen = []
    n = KatharaNetwork("lab", lambda cmd, t: seen.append(cmd) or "status: NOERROR\nANSWER: 1")
    for name in ("web.lab", "db-1.example.com", "ghost"):
        assert n.dns_lookup("h1", name).category == "dns"
    assert seen[0][-1] == "web.lab"


def test_port_check_rejects_booleans():
    n = KatharaNetwork("lab", lambda cmd, t: "")
    assert n.port_check("h1", "h2", True).category == "invalid"


# ---- history thread safety -----------------------------------------------------------------------------------

def test_history_is_safe_under_concurrent_reads_and_imports(tmp_path):
    import json
    import os

    fix = os.path.join(os.path.dirname(__file__), "fixtures", "run-sample.jsonl")
    line = open(fix, encoding="utf-8").readline()
    (tmp_path / "run-20260101-000000.jsonl").write_text(line * 30, encoding="utf-8")
    h = History(str(tmp_path / "h.db"))
    errors = []

    def worker(i):
        try:
            for _ in range(20):
                if i % 2:
                    h.import_dir(str(tmp_path))
                else:
                    h.list()
                    h.stats()
        except Exception as e:  # noqa: BLE001 - the test collects any failure
            errors.append(repr(e))

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errors == []
    assert len(h.list(limit=1000)) == 30
    assert json.loads(line)  # fixture sanity
