import pytest

from netwing.agent import run_diagnosis
from netwing.budget import CostGuard
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, text, tool_use

PRICES = {"m": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}


def guard(total=10.0):
    return CostGuard(total_cap_usd=total, per_run_cap_usd=5.0, prices=PRICES)


def run(sid, mode, script, max_tests=8, usage=(100, 50), g=None):
    client = FakeClient(script, usage=usage)
    s = get_scenario(sid)
    log = run_diagnosis(s, SimNetwork(s), mode, client, g or guard(), "m", max_tests)
    return log, client


def last_user_blocks(client, call_index):
    return client.calls[call_index]["messages"][-1]["content"]


def test_plain_mode_returns_answer_and_counts_tests():
    log, _ = run("healthy_false_alarm", "plain", [
        [tool_use("t1", "ping", src="h1", dst="h2")],
        [final("f1", "healthy", "none", ["E1"])],
    ])
    assert log.status == "answered" and log.tests_run == 1
    assert log.answer["verdict"] == "healthy"
    assert log.cost_usd > 0


def test_plain_mode_accepts_unsupported_fault_claim():
    log, _ = run("healthy_false_alarm", "plain", [[final("f1", "fault", "route_failure", [])]])
    assert log.status == "answered" and log.answer["verdict"] == "fault"


def test_netwing_rejects_fault_claim_without_evidence_then_accepts_healthy():
    log, client = run("healthy_false_alarm", "netwing", [
        [tool_use("t1", "ping", src="h1", dst="h2")],
        [final("f1", "fault", "route_failure", [])],
        [final("f2", "healthy", "none", ["E1"])],
    ])
    assert log.rejected_claims == 1
    assert log.status == "answered" and log.answer["verdict"] == "healthy"
    rejection = last_user_blocks(client, 2)[0]
    assert rejection["type"] == "tool_result" and rejection["is_error"] is True


def test_netwing_forces_final_answer_after_stop_healthy():
    log, client = run("healthy_false_alarm", "netwing", [
        [tool_use("t1", "ping", src="h1", dst="h2"),
         tool_use("t2", "dns_lookup", src="h1", name="web.lab"),
         tool_use("t3", "port_check", src="h1", dst="h2", port=80)],
        [final("f1", "healthy", "none", ["E1", "E2", "E3"])],
    ])
    assert log.status == "answered" and log.tests_run == 3
    blocks = last_user_blocks(client, 1)
    assert any(b["type"] == "tool_result" and "final answer now" in b["content"] for b in blocks)
    assert client.calls[1]["tool_choice"] == {"type": "tool", "name": "final_answer"}


def test_netwing_real_fault_is_still_found():
    log, _ = run("dns_failure", "netwing", [
        [tool_use("t1", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("t2", "ping", src="h1", dst="h2")],
        [tool_use("t3", "port_check", src="h1", dst="h2", port=80)],
        [tool_use("t4", "dns_lookup", src="h1", name="web.lab")],
        [final("f1", "fault", "dns_failure", ["E1", "E4"])],
    ])
    assert log.status == "answered" and log.answer["fault_type"] == "dns_failure"
    assert log.rejected_claims == 0


def test_no_final_answer_within_cap_gives_no_answer_status():
    script = [[tool_use(f"t{i}", "ping", src="h1", dst="h2")] for i in range(30)]
    log, _ = run("healthy_false_alarm", "plain", script, max_tests=2)
    assert log.status == "no_answer" and log.answer is None
    assert log.tests_run == 2


def test_multiple_tool_use_blocks_in_one_turn_all_get_results_and_count():
    log, client = run("healthy_false_alarm", "netwing", [
        [tool_use("a", "ping", src="h1", dst="h2"),
         tool_use("b", "ping", src="h1", dst="r1"),
         tool_use("c", "ping", src="h2", dst="r1")],
        [final("f1", "healthy", "none", ["E1"])],
    ])
    results = [b for b in last_user_blocks(client, 1) if b["type"] == "tool_result"]
    assert [b["tool_use_id"] for b in results] == ["a", "b", "c"]
    assert log.tests_run == 3


def test_tool_calls_past_cap_are_refused_not_executed():
    log, client = run("healthy_false_alarm", "plain", [
        [tool_use("a", "ping", src="h1", dst="h2"), tool_use("b", "ping", src="h1", dst="r1")],
        [final("f1", "healthy", "none", ["E1"])],
    ], max_tests=1)
    results = [b for b in last_user_blocks(client, 1) if b["type"] == "tool_result"]
    assert results[1]["is_error"] is True
    assert log.tests_run == 1


def test_budget_exceeded_marks_status_budget_and_stops():
    g = CostGuard(total_cap_usd=0.0000001, per_run_cap_usd=5.0, prices=PRICES)
    log, _ = run("healthy_false_alarm", "plain", [[tool_use("t1", "ping", src="h1", dst="h2")]], g=g)
    assert log.status == "budget" and log.answer is None


def test_unknown_tool_name_is_invalid_and_counts_but_never_evidence():
    log, client = run("healthy_false_alarm", "netwing", [
        [tool_use("t1", "reboot_router", node="r1")],
        [final("f1", "fault", "route_failure", ["E1"])],
        [final("f2", "fault", "route_failure", ["E1"])],
        [final("f3", "fault", "route_failure", ["E1"])],
        [final("f4", "fault", "route_failure", ["E1"])],
        [final("f5", "fault", "route_failure", ["E1"])],
        [final("f6", "fault", "route_failure", ["E1"])],
        [final("f7", "fault", "route_failure", ["E1"])],
        [final("f8", "fault", "route_failure", ["E1"])],
        [final("f9", "fault", "route_failure", ["E1"])],
        [final("f10", "fault", "route_failure", ["E1"])],
    ])
    assert log.tests_run == 1
    assert log.status == "no_answer" and log.rejected_claims >= 1


def test_bad_tool_arguments_do_not_crash():
    log, client = run("healthy_false_alarm", "plain", [
        [tool_use("t1", "ping", src="h1")],
        [final("f1", "healthy", "none", [])],
    ])
    assert log.status == "answered"
    result = last_user_blocks(client, 1)[0]
    assert "invalid" in result["content"].lower() or "error" in result["content"].lower()


def test_missing_usage_still_counts_cost():
    log, _ = run("healthy_false_alarm", "plain", [[final("f1", "healthy", "none", [])]], usage=None)
    assert log.cost_usd > 0


def test_model_replies_with_text_only_is_nudged_then_gives_up():
    script = [[text("I think it is fine.")] for _ in range(10)]
    log, client = run("healthy_false_alarm", "plain", script)
    assert log.status == "no_answer"
    assert len(client.calls) < 10


def test_mode_prompts_differ():
    _, c1 = run("healthy_false_alarm", "plain", [[final("f", "healthy", "none")]])
    _, c2 = run("healthy_false_alarm", "healthy_ok", [[final("f", "healthy", "none")]])
    assert "healthy" in c2.calls[0]["system"].lower()
    assert c1.calls[0]["system"] != c2.calls[0]["system"]


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        run("healthy_false_alarm", "bogus", [[final("f", "healthy", "none")]])
