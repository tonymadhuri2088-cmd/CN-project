from netwing.scenarios import get_scenario
from netwing.scoring import score


def ans(verdict, fault_type, ev=None):
    return {"verdict": verdict, "fault_type": fault_type, "evidence": ev or []}


def test_correct_fault_identification():
    s = score(get_scenario("dns_failure"), ans("fault", "dns_failure", ["E1"]))
    assert s.correct and not s.false_alarm and not s.no_answer


def test_wrong_fault_type_incorrect():
    s = score(get_scenario("dns_failure"), ans("fault", "port_blocked"))
    assert not s.correct and not s.false_alarm


def test_healthy_called_on_real_fault_incorrect():
    s = score(get_scenario("route_failure"), ans("healthy", "none"))
    assert not s.correct and not s.false_alarm


def test_healthy_scenario_fault_claim_is_false_alarm_and_incorrect():
    s = score(get_scenario("healthy_false_alarm"), ans("fault", "route_failure"))
    assert s.false_alarm and not s.correct


def test_healthy_scenario_healthy_answer_correct():
    s = score(get_scenario("healthy_false_alarm"), ans("healthy", "none"))
    assert s.correct and not s.false_alarm


def test_none_answer_is_no_answer_incorrect_not_false_alarm():
    s = score(get_scenario("healthy_false_alarm"), None)
    assert s.no_answer and not s.correct and not s.false_alarm


def test_malformed_answer_treated_as_no_answer():
    s = score(get_scenario("dns_failure"), {"verdict": "banana"})
    assert s.no_answer and not s.correct
