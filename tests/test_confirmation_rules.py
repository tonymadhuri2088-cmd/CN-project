"""A fault is only reported once it is confirmed (seen twice) and every check area has been tried."""
from netwing.backend import ToolResult
from netwing.agent import run_diagnosis
from netwing.controller import Controller, Verdict
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, tool_use
from tests.test_agent import guard


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


PING = dict(src="h1", dst="web.lab")
DNS = dict(src="h1", name="web.lab")
PORT = dict(src="h1", dst="web.lab", port=80)


def covered_with_one_failure():
    c = Controller()
    c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("dns_lookup", True, "dns", **DNS))
    c.observe(R("port_check", True, "port", **PORT))
    return c


def test_a_single_unreproduced_failure_never_stops_as_fault():
    c = covered_with_one_failure()
    assert c.decide() == Verdict.CONTINUE


def test_reproduced_failure_with_all_areas_tried_stops_as_fault():
    c = covered_with_one_failure()
    c.observe(R("ping", False, "connectivity", **PING))
    assert c.decide() == Verdict.STOP_FAULT


def test_confirmed_failure_but_an_area_untried_keeps_going():
    c = Controller()
    c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("dns_lookup", True, "dns", **DNS))
    assert c.decide() == Verdict.CONTINUE       # no port check yet


def test_fault_claim_on_one_unreproduced_failure_is_rejected_with_advice():
    c = covered_with_one_failure()
    ok, why = c.allow_claim("fault", "route_failure", ["E1"])
    assert not ok and "again" in why and "same check" in why


def test_fault_claim_on_a_reproduced_failure_is_allowed():
    c = covered_with_one_failure()
    c.observe(R("ping", False, "connectivity", **PING))
    assert c.allow_claim("fault", "route_failure", ["E1"])[0]


def test_healthy_claim_blocked_by_a_failure_tells_the_model_how_to_clear_it():
    c = covered_with_one_failure()
    ok, why = c.allow_claim("healthy", "none", [])
    assert not ok and "exact same check" in why and "twice" in why and "E1" in why


def test_transient_blip_flow_ends_healthy_without_a_false_alarm():
    s = get_scenario("transient_blip")
    script = [
        [tool_use("a", "ping", src="h1", dst="web.lab")],
        [tool_use("b", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("c", "port_check", src="h1", dst="web.lab", port=80)],
        [final("f1", "healthy", "none", ["E2", "E3"])],                      # rejected: E1 unresolved
        [tool_use("d", "ping", src="h1", dst="web.lab")],
        [tool_use("e", "ping", src="h1", dst="web.lab")],
        [final("f2", "healthy", "none", ["E2", "E3", "E4", "E5"])],
    ]
    log = run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 8)
    assert log.status == "answered" and log.answer["verdict"] == "healthy" and log.rejected_claims == 1


def test_real_single_failure_fault_is_found_after_one_repeat():
    s = get_scenario("port_blocked")
    script = [
        [tool_use("a", "ping", src="h1", dst="web.lab")],
        [tool_use("b", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("c", "port_check", src="h1", dst="web.lab", port=80)],
        [tool_use("d", "port_check", src="h1", dst="web.lab", port=80)],
        [final("f", "fault", "port_blocked", ["E3", "E4"])],
    ]
    log = run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 8)
    assert log.status == "answered" and log.answer["fault_type"] == "port_blocked" and log.rejected_claims == 0


def test_same_kind_of_failure_seen_from_two_different_checks_counts_as_confirmed():
    c = Controller()
    c.observe(R("dns_lookup", True, "dns", **DNS))
    c.observe(R("port_check", True, "port", **PORT))
    e = c.observe(R("ping", False, "connectivity", src="h1", dst="10.0.2.10"))
    assert c.decide() == Verdict.CONTINUE                                    # seen once
    c.observe(R("ping", False, "connectivity", src="r1", dst="10.0.2.10"))   # other vantage point
    assert c.decide() == Verdict.STOP_FAULT
    assert c.allow_claim("fault", "route_failure", [e])[0]


def test_traceroute_and_ping_failures_confirm_each_other():
    c = Controller()
    c.observe(R("dns_lookup", True, "dns", **DNS))
    c.observe(R("port_check", True, "port", **PORT))
    e = c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("traceroute", False, "routing", **PING))
    assert c.allow_claim("fault", "route_failure", [e])[0]


def test_failures_in_different_areas_do_not_confirm_each_other():
    c = Controller()
    c.observe(R("dns_lookup", True, "dns", **DNS))
    c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("port_check", False, "port", **PORT))
    assert c.decide() == Verdict.CONTINUE
