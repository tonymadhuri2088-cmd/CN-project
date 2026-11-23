"""Claim-level evidence validation (opt-in): every secondary fault claim needs its own reproduced, relevant evidence.

Off by default
the primary-claim gate is untouched. Unsupported or merely suspected secondary claims are dropped
from the accepted answer and recorded with the reason, never silently."""
import pytest

from netwing.backend import ToolResult
from netwing.controller import Controller
from netwing.scenarios import Subject

SUBJ = Subject()


def obs(c, tool, ok, category, **args):
    return c.observe(ToolResult(tool=tool, args=args, output="x", ok=ok, category=category))


def dns(c, ok, name="web.lab"):
    return obs(c, "dns_lookup", ok, "dns", src="h1", name=name)


def port(c, ok):
    return obs(c, "port_check", ok, "port", src="h1", dst="web.lab", port=80)


def ping(c, ok):
    return obs(c, "ping", ok, "connectivity", src="h1", dst="web.lab")


def mk(**kw):
    return Controller(max_tests=12, subject=SUBJ, validate_claims=True, **kw)


def dns_fault_run(c):
    dns(c, False)
    dns(c, False)
    ping(c, True)
    port(c, True)


def test_default_is_off_and_validation_requires_the_flag():
    assert Controller(subject=SUBJ).validate_claims is False
    with pytest.raises(RuntimeError):
        Controller(subject=SUBJ).validate_other_faults("dns_failure", ["port_blocked"])


def test_unrelated_secondary_claim_is_dropped_with_a_reason():
    c = mk()
    dns_fault_run(c)
    kept, rep = c.validate_other_faults("dns_failure", ["port_blocked"])
    assert kept == []
    r = {x["fault_type"]: x for x in rep}
    assert r["dns_failure"]["status"] == "confirmed" and r["dns_failure"]["role"] == "primary"
    assert r["port_blocked"]["status"] == "unsupported" and r["port_blocked"]["accepted"] is False
    assert "no failing" in r["port_blocked"]["reason"].lower()


def test_legitimate_multi_fault_is_preserved():
    c = mk()
    dns_fault_run(c)
    port(c, False)
    port(c, False)
    kept, rep = c.validate_other_faults("dns_failure", ["port_blocked"])
    assert kept == ["port_blocked"]
    assert [x["status"] for x in rep if x["role"] == "secondary"] == ["confirmed"]


def test_secondary_seen_once_is_only_suspected_and_not_accepted():
    c = mk()
    dns_fault_run(c)
    port(c, False)
    kept, rep = c.validate_other_faults("dns_failure", ["port_blocked"])
    assert kept == []
    assert rep[-1]["status"] == "suspected" and "once" in rep[-1]["reason"]


def test_cleared_transient_failure_does_not_support_a_secondary_claim():
    c = mk()
    dns_fault_run(c)
    port(c, False)
    port(c, True)
    port(c, True)
    kept, rep = c.validate_other_faults("dns_failure", ["port_blocked"])
    assert kept == [] and rep[-1]["status"] == "unsupported"


def test_missing_and_unknown_claims_are_unsupported_and_duplicates_collapse():
    c = mk()
    dns_fault_run(c)
    kept, rep = c.validate_other_faults("dns_failure", ["dns_failure", "made_up", "route_failure", "route_failure"])
    assert kept == []
    sec = [x for x in rep if x["role"] == "secondary"]
    assert [x["fault_type"] for x in sec] == ["made_up", "route_failure"]
    assert all(x["status"] == "unsupported" for x in sec)


def test_failures_about_unrelated_targets_do_not_support_a_claim():
    c = mk()
    dns_fault_run(c)
    for _ in range(2):
        obs(c, "port_check", False, "port", src="h1", dst="h2", port=8080)
    kept, _ = c.validate_other_faults("dns_failure", ["port_blocked"])
    assert kept == []


# -- end to end through the agent loop ------------------------------------------------------------
from netwing.agent import run_diagnosis  # noqa: E402
from netwing.scenarios import get_scenario  # noqa: E402
from netwing.scoring import score  # noqa: E402
from netwing.sim import SimNetwork  # noqa: E402
from tests.fake_client import FakeClient, tool_use  # noqa: E402
from tests.test_confirmation_rules import guard  # noqa: E402


def _answer(id_, fault, others, ev):
    return tool_use(id_, "final_answer", verdict="fault", fault_type=fault, evidence=ev, other_faults=others)


def _dns_script(others):
    return [
        [tool_use("a", "ping", src="h1", dst="10.0.2.10")],
        [tool_use("b", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("c", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("d", "port_check", src="h1", dst="10.0.2.10", port=80)],
        [_answer("f", "dns_failure", others, ["E2", "E3"])],
    ]


def _run(sid, script, **kw):
    s = get_scenario(sid)
    return s, run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 8, **kw)


def test_off_by_default_the_unsupported_extra_claim_survives_unchanged():
    s, log = _run("dns_failure", _dns_script(["port_blocked"]))
    assert log.answer["other_faults"] == ["port_blocked"] and log.claim_report == []
    assert score(s, log.answer).complete is False


def test_on_the_unsupported_extra_claim_is_dropped_logged_and_scored_complete():
    s, log = _run("dns_failure", _dns_script(["port_blocked"]), validate_claims=True)
    assert log.status == "answered" and log.rejected_claims == 0
    assert log.answer["other_faults"] == [] and log.answer["other_faults_raw"] == ["port_blocked"]
    assert {x["fault_type"]: x["status"] for x in log.claim_report} == {"dns_failure": "confirmed", "port_blocked": "unsupported"}
    sc = score(s, log.answer)
    assert sc.correct and sc.complete


def test_on_a_real_second_fault_is_kept_and_primary_decision_is_unchanged():
    s = get_scenario("fx2_campus_noisy_multi_dns_port")
    script = [
        [tool_use("a", "ping", src="h1", dst="10.0.2.10")],
        [tool_use("b", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("c", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("d", "port_check", src="h1", dst="10.0.2.10", port=80)],
        [tool_use("e", "port_check", src="h1", dst="10.0.2.10", port=80)],
        [_answer("f", "dns_failure", ["port_blocked"], ["E2", "E3"])],
    ]
    log = run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 8, validate_claims=True)
    assert log.answer["other_faults"] == ["port_blocked"]
    assert score(s, log.answer).complete
