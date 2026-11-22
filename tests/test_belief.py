import json
import math

import pytest

from netwing.belief import Belief, answer_set, truth_set
from netwing.belief_report import main, replay_run, summarise
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork


def test_prior_is_a_distribution_and_healthy_is_most_likely_alone():
    b = Belief()
    assert abs(sum(b.w.values()) - 1) < 1e-12 and b.n == 0
    assert b.diagnosis() == frozenset() and b.p_healthy() == pytest.approx(0.75 ** 3)


def test_rejects_silly_parameters():
    with pytest.raises(ValueError):
        Belief(prior=0)
    with pytest.raises(ValueError):
        Belief(false_fail=0.6)


def test_a_dns_failure_points_at_dns_and_a_pass_points_away():
    b = Belief()
    b.update("dns", False)
    assert b.marginals()["dns"] > 0.7 and b.marginals()["route"] == pytest.approx(0.25)
    c = Belief()
    c.update("dns", True)
    assert c.marginals()["dns"] < 0.1


def test_repeating_a_failure_raises_confidence_and_a_blip_is_outvoted():
    b = Belief()
    seen = []
    for ok in (False, False, False):
        b.update("connectivity", ok)
        seen.append(b.marginals()["route"])
    assert seen[0] < seen[1] < seen[2]
    blip = Belief()
    for ok in (False, True, True):
        blip.update("connectivity", ok)
    assert blip.marginals()["route"] < 0.2  # one failure then two passes: probably a blip


def test_port_check_failure_is_explained_by_route_or_port():
    b = Belief()
    b.update("port", False)
    m = b.marginals()
    assert m["port"] > 0.25 and m["route"] > 0.25
    b.update("connectivity", True)  # connectivity fine: it must be the port
    assert b.marginals()["port"] > b.marginals()["route"] and b.marginals()["route"] < 0.2  # one pass cannot fully rule a route fault out (miss rate)


def test_two_faults_at_once_are_found_together():
    b = Belief()
    for cat, ok in [("dns", False), ("dns", False), ("port", False), ("connectivity", True), ("port", False)]:
        b.update(cat, ok)
    assert b.diagnosis() == frozenset({"dns", "port"})


def test_uninformative_categories_change_nothing():
    b = Belief()
    before = dict(b.w)
    assert b.update("routing", True) is False and b.update("invalid", False) is False
    assert b.w == before and b.n == 0 and b.expected_info_gain("routing") == 0


def test_information_gain_is_positive_and_shrinks_with_repetition():
    b = Belief()
    g0 = b.expected_info_gain("dns")
    assert 0 < g0 <= 1
    for _ in range(4):
        b.update("dns", True)
    assert b.expected_info_gain("dns") < g0


def test_next_best_test_prefers_an_untried_area_over_a_settled_one():
    b = Belief()
    for _ in range(4):
        b.update("dns", True)
    cat, gain = b.next_best_test()
    assert cat in ("connectivity", "port") and gain > 0


def test_entropy_falls_as_evidence_comes_in():
    b = Belief()
    h0 = b.entropy()
    b.update("dns", False)
    b.update("dns", False)
    assert b.entropy() < h0 and b.entropy() >= 0 and math.isfinite(b.entropy())


def test_truth_and_answer_sets():
    assert truth_set(get_scenario("healthy_false_alarm")) == frozenset()
    assert truth_set(get_scenario("multi_dns_port")) == frozenset({"dns", "port"})
    assert truth_set(get_scenario("route_failure")) == frozenset({"route"})
    assert answer_set({"verdict": "healthy"}) == frozenset()
    assert answer_set({"verdict": "fault", "fault_type": "dns_failure", "other_faults": ["port_blocked"]}) == frozenset({"dns", "port"})
    assert answer_set({"verdict": "inconclusive"}) is None and answer_set(None) is None


def _run(scenario_id, checks, mode="netwing", correct=True):
    s = get_scenario(scenario_id)
    net = SimNetwork(s)
    tests = []
    for i, (tool, args) in enumerate(checks, 1):
        r = getattr(net, tool)(**args)
        tests.append({"id": f"E{i}", "tool": r.tool, "args": r.args, "output": r.output, "ok": r.ok,
                      "category": r.category, "evidence": r.evidence})
    return {"scenario_id": scenario_id, "mode": mode, "tests": tests, "score": {"correct": correct},
            "answer": {"verdict": "fault", "fault_type": "dns_failure", "evidence": []}}


_DNS_CHECKS = [("dns_lookup", {"src": "h1", "name": "web.lab"})] * 3 + [
    ("ping", {"src": "h1", "dst": "10.0.2.10"}), ("port_check", {"src": "h1", "dst": "10.0.2.10", "port": 80})]


def test_replay_finds_the_dns_fault_but_only_stops_once_every_area_was_checked():
    res = replay_run(_run("dns_failure", _DNS_CHECKS), tau=0.9)
    # confidence is about the whole joint state: it needs the route and port checked too, not just repeated DNS failures
    assert res["stop_at"] == 5 and res["stop_correct"] is True
    early = replay_run(_run("dns_failure", _DNS_CHECKS[:3]), tau=0.9)
    assert early["stop_at"] is None and early["final_correct"] is True
    assert res["final_correct"] and res["agent_tests"] == 5 and res["agent_answer_matches_truth"] is True


def test_replay_ignores_results_about_unrelated_alerts():
    checks = [("dns_lookup", {"src": "h1", "name": "printer.lab"})] * 4
    res = replay_run(_run("noisy_healthy", checks), tau=0.9)
    assert res["readings_used"] == 0 and res["stop_at"] is None  # nothing about the ticket was measured
    assert res["final_confidence"] == pytest.approx(0.75 ** 3)


def test_replay_skips_logs_without_structured_tests_or_known_scenarios():
    assert replay_run({"scenario_id": "dns_failure", "tests": []}) is None
    bad = _run("dns_failure", _DNS_CHECKS)
    bad["tests"][0]["category"] = None
    assert replay_run(bad) is None
    unknown = _run("dns_failure", _DNS_CHECKS)
    unknown["scenario_id"] = "no_such_scenario"
    assert replay_run(unknown) is None


def test_summary_counts_confident_but_wrong_stops():
    healthy_checks = [("dns_lookup", {"src": "h1", "name": "web.lab"}), ("ping", {"src": "h1", "dst": "10.0.2.10"}),
                      ("port_check", {"src": "h1", "dst": "10.0.2.10", "port": 80})] * 2
    rows = [replay_run(_run("healthy_false_alarm", healthy_checks), 0.9), replay_run(_run("dns_failure", _DNS_CHECKS), 0.9)]
    s = summarise(rows)
    assert s["runs"] == 2 and s["reached"] == 1.0 and s["confidently_wrong"] == 0
    assert s["belief_tests"] <= s["agent_tests"]


def test_command_line_report_prints_a_table_and_is_deterministic(tmp_path, capsys):
    f = tmp_path / "run-x.jsonl"
    f.write_text("\n".join(json.dumps(_run(sid, _DNS_CHECKS if sid == "dns_failure" else [])) for sid in ("dns_failure", "dns_failure")),
                 encoding="utf-8")
    assert main([str(f), "--tau", "0.9", "0.99"]) == 0
    out = capsys.readouterr().out
    assert "### tau = 0.9" in out and "### tau = 0.99" in out and "run-x.jsonl" in out and "netwing" in out
    assert main([str(f), "--tau", "0.9"]) == 0
