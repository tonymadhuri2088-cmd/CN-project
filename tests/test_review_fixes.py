"""Tests added after the whole-branch review (findings C1, I1-I6)."""
import json
import os
import shutil
import subprocess
from types import SimpleNamespace as NS

import pytest

from netwing.agent import RunLog, run_diagnosis
from netwing.backend import ToolResult
from netwing.budget import CostGuard
from netwing.controller import Controller, Verdict
from netwing.runner import run_matrix, summarize
from netwing.scenarios import ALL_IDS, get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, tool_use

ROOT = os.path.join(os.path.dirname(__file__), "..")
PRICES = {"m": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}


def guard():
    return CostGuard(total_cap_usd=10.0, per_run_cap_usd=5.0, prices=PRICES)


def run(sid, mode, script, max_tests=8):
    client = FakeClient(script)
    s = get_scenario(sid)
    return run_diagnosis(s, SimNetwork(s), mode, client, guard(), "m", max_tests), client


# ---- C1: never send an empty assistant turn; no trailing text after tool_results ----
def test_empty_assistant_turn_is_never_sent_back():
    log, client = run("healthy_false_alarm", "plain", [[], [final("f", "healthy", "none", [])]])
    for call in client.calls:
        for m in call["messages"]:
            assert not (m["role"] == "assistant" and m["content"] == [])
    assert log.status == "answered"


def test_force_text_rides_inside_last_tool_result_not_as_trailing_text():
    _, client = run("healthy_false_alarm", "netwing", [
        [tool_use("a", "ping", src="h1", dst="h2"),
         tool_use("b", "dns_lookup", src="h1", name="web.lab"),
         tool_use("c", "port_check", src="h1", dst="h2", port=80)],
        [final("f", "healthy", "none", ["E1", "E2", "E3"])],
    ])
    blocks = client.calls[1]["messages"][-1]["content"]
    assert all(b["type"] == "tool_result" for b in blocks)
    assert "final answer now" in blocks[-1]["content"]


# ---- I2: the test cap forces a final answer in every mode ----
def test_cap_forces_final_answer_in_every_mode():
    for mode in ("plain", "healthy_ok"):
        _, client = run("healthy_false_alarm", mode, [
            [tool_use("a", "ping", src="h1", dst="h2")],
            [final("f", "healthy", "none", ["E1"])],
        ], max_tests=1)
        assert client.calls[1]["tool_choice"] == {"type": "tool", "name": "final_answer"}


# ---- I1: refused ports / unasked-for NXDOMAIN are not fault evidence; forcing is released after a rejection ----
def test_refused_port_is_not_fault_evidence_in_controller():
    c = Controller()
    refused = ToolResult("port_check", {}, "refused", False, "port", evidence=False)
    c.observe(refused)
    assert c.decide() == Verdict.CONTINUE
    for cat, tool in (("connectivity", "ping"), ("dns", "dns_lookup"), ("port", "port_check")):
        c.observe(ToolResult(tool, {}, "ok", True, cat))
    assert c.decide() == Verdict.STOP_HEALTHY
    assert c.allow_claim("healthy", "none", ["E2", "E3", "E4"])[0]
    assert not c.allow_claim("fault", "port_blocked", ["E1"])[0]


def test_sim_closed_port_and_unknown_name_are_not_evidence():
    n = SimNetwork(get_scenario("healthy_false_alarm"))
    p = n.port_check("h1", "h2", 443)
    assert not p.ok and p.evidence is False
    d = n.dns_lookup("h1", "other.lab")
    assert not d.ok and d.evidence is False
    f = SimNetwork(get_scenario("dns_failure")).dns_lookup("h1", "web.lab")
    assert not f.ok and f.evidence is True


def test_healthy_network_with_a_closed_port_probe_still_gets_answered():
    log, _ = run("healthy_false_alarm", "netwing", [
        [tool_use("a", "ping", src="h1", dst="h2"),
         tool_use("b", "dns_lookup", src="h1", name="web.lab"),
         tool_use("c", "port_check", src="h1", dst="h2", port=443),
         tool_use("d", "port_check", src="h1", dst="h2", port=80)],
        [final("f", "healthy", "none", ["E1", "E2", "E4"])],
    ])
    assert log.status == "answered" and log.answer["verdict"] == "healthy"
    assert log.rejected_claims == 0


def test_forcing_is_released_after_a_rejected_claim():
    _, client = run("healthy_false_alarm", "netwing", [
        [tool_use("a", "ping", src="h1", dst="h2"),
         tool_use("b", "dns_lookup", src="h1", name="web.lab"),
         tool_use("c", "port_check", src="h1", dst="h2", port=80)],
        [final("f1", "fault", "route_failure", ["E1"])],   # rejected
        [final("f2", "healthy", "none", ["E1", "E2", "E3"])],
    ])
    assert "tool_choice" in client.calls[1]
    assert "tool_choice" not in client.calls[2]


# ---- I3: tickets must not leak the ground truth ----
def test_tickets_do_not_leak_ground_truth():
    tickets = {get_scenario(i).ticket for i in ALL_IDS}
    assert len(tickets) == 1
    assert "mistaken" not in tickets.pop().lower()


# ---- I4: any exception ends the run as status=error and the matrix stops cleanly ----
class ExplodingClient(FakeClient):
    def _create(self, **kw):
        if len(self.calls) >= 1:
            self.calls.append(kw)
            raise RuntimeError("boom: connection reset")
        return super()._create(**kw)


def explode_script():
    return [[tool_use("a", "ping", src="h1", dst="h2")]]


def test_client_exception_marks_error_and_keeps_cost():
    client = ExplodingClient(explode_script())
    client.messages = NS(create=client._create)
    s = get_scenario("healthy_false_alarm")
    log = run_diagnosis(s, SimNetwork(s), "plain", client, guard(), "m", 8)
    assert log.status == "error" and "boom" in log.error
    assert log.cost_usd > 0 and log.tests_run == 1 and log.answer is None


def test_matrix_stops_on_error_and_summary_says_incomplete(tmp_path):
    client = ExplodingClient(explode_script())
    client.messages = NS(create=client._create)
    out = tmp_path / "r.jsonl"
    logs = run_matrix(["healthy_false_alarm", "dns_failure"], ["plain"], 1, SimNetwork, client, guard(), "m", str(out))
    assert len(logs) == 1 and logs[0].status == "error"
    assert json.loads(out.read_text().splitlines()[0])["status"] == "error"
    assert "INCOMPLETE" in summarize(logs, True)


# ---- I5: summary must not hide abstentions or mix in stopped runs ----
def mk(sid, mode, answer, status="answered", tests=2, cost=0.1):
    return RunLog(sid, mode, "m", tests_run=tests, answer=answer, status=status, cost_usd=cost)


def table_row(text, mode):
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 5 and cells[1] == mode:
            return cells
    raise AssertionError(f"no row for {mode}")


def test_summary_excludes_stopped_runs_from_averages_and_flags_them():
    ok = {"verdict": "healthy", "fault_type": "none", "evidence": []}
    logs = [mk("healthy_false_alarm", "netwing", ok), mk("healthy_false_alarm", "netwing", None, "budget", 12, 5.0)]
    text = summarize(logs, True)
    row = table_row(text, "netwing")
    assert row[2] == "1"                      # Runs: completed only
    assert "INCOMPLETE" in text
    assert any("2.0" in c for c in row)       # mean tests from the completed run only


def test_healthy_no_answer_is_not_counted_as_a_good_result():
    logs = [mk("healthy_false_alarm", "netwing", None, "no_answer")]
    row = table_row(summarize(logs, True), "netwing")
    # cells: ['', mode, runs, correct, false alarms, healthy correct, ...]
    assert row[4].split(" ")[0] == "0%" and row[5] == "0%"


# ---- I6: simulator and Kathara lab describe the same route_failure ----
def test_route_failure_dns_still_works_in_sim():
    assert SimNetwork(get_scenario("route_failure")).dns_lookup("h1", "web.lab").ok


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash (Linux/macOS/WSL/Git Bash)")
def test_route_failure_lab_removes_the_route_and_keeps_forwarding_on():
    subprocess.run(["bash", os.path.join(ROOT, "labs", "inject.sh"), "route_failure"], check=True, capture_output=True)
    r1 = open(os.path.join(ROOT, "labs", "route_failure", "r1.startup")).read()
    assert "ip route del 10.0.2.0/24" in r1 and "ip_forward=0" not in r1


def test_dns_server_is_on_the_h1_side_so_route_failure_does_not_break_dns():
    conf = open(os.path.join(ROOT, "labs", "base", "lab.conf")).read()
    h1 = open(os.path.join(ROOT, "labs", "base", "h1.startup")).read()
    assert "dns[0]=A" in conf and "nameserver 10.0.1.53" in h1


# ---- I1 on the real-lab backend: refused port / NXDOMAIN for an unasked-for name are not evidence ----
def test_kathara_refused_port_and_unasked_nxdomain_are_not_evidence():
    from netwing.kathara import KatharaNetwork

    refused = "nc: connect to 10.0.2.10 port 443 (tcp) failed: Connection refused\nrc=1"
    r = KatharaNetwork("/x", runner=lambda c, t: refused).port_check("h1", "h2", 443)
    assert not r.ok and r.evidence is False
    timeout = "nc: connect to 10.0.2.10 port 80 (tcp) timed out\nrc=1"
    assert KatharaNetwork("/x", runner=lambda c, t: timeout).port_check("h1", "h2", 80).evidence is True
    nx = ";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 3"
    assert KatharaNetwork("/x", runner=lambda c, t: nx).dns_lookup("h1", "other.lab").evidence is False
    assert KatharaNetwork("/x", runner=lambda c, t: nx).dns_lookup("h1", "web.lab").evidence is True


# ---- error taxonomy: a programming bug must be distinguishable from an API/network failure in the log ----

class _RaisingClient(ExplodingClient):
    exc: Exception = RuntimeError("x")

    def _create(self, **kw):
        raise self.exc


def _run_with(exc):
    client = _RaisingClient([])
    client.exc = exc
    client.messages = NS(create=client._create)
    s = get_scenario("healthy_false_alarm")
    return run_diagnosis(s, SimNetwork(s), "plain", client, guard(), "m", 8)


def test_error_kind_separates_network_failures_from_programming_bugs():
    assert _run_with(ConnectionError("reset")).error_kind == "api"
    assert _run_with(TimeoutError("slow")).error_kind == "api"
    bug = _run_with(AttributeError("'NoneType' object has no attribute 'x'"))
    assert bug.status == "error" and bug.error_kind == "internal" and bug.error_where
    assert _run_with(RuntimeError("boom")).error_kind == "other"


def test_error_fields_are_empty_on_a_clean_run():
    s = get_scenario("healthy_false_alarm")
    from netwing.agent import RunLog

    assert RunLog(s.id, "plain", "m").error_kind == ""
