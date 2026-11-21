"""A DNS failure masks ping/port checks that use the name; they must be redone without DNS before a fault is reported."""
from netwing.backend import ToolResult
from netwing.agent import run_diagnosis
from netwing.controller import Controller, Verdict
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, tool_use
from tests.test_agent import guard


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


def dns_fault_with_masked_checks():
    c = Controller()
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))
    c.observe(R("ping", False, "dns", src="h1", dst="web.lab"))          # masked: name resolution failed
    c.observe(R("port_check", False, "dns", src="h1", dst="web.lab", port=80))  # masked
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))   # DNS failure reproduced
    return c


def test_checks_blocked_by_dns_do_not_count_as_trying_ping_and_port():
    assert dns_fault_with_masked_checks().decide() == Verdict.CONTINUE


def test_dns_fault_claim_is_rejected_until_ping_and_port_are_tested_without_the_name():
    c = dns_fault_with_masked_checks()
    ok, why = c.allow_claim("fault", "dns_failure", ["E1", "E4"])
    assert not ok and "ping" in why and "port" in why and "IP" in why and "node name" in why


def test_after_unmasked_ping_and_port_checks_the_fault_is_allowed_and_stops():
    c = dns_fault_with_masked_checks()
    c.observe(R("ping", True, "connectivity", src="h1", dst="h2"))
    c.observe(R("port_check", False, "port", src="h1", dst="h2", port=80))
    assert c.decide() == Verdict.STOP_FAULT
    assert c.allow_claim("fault", "dns_failure", ["E1", "E4"])[0]


def test_multi_fault_flow_rejects_the_early_claim_then_finds_the_hidden_fault():
    s = get_scenario("multi_dns_port")
    script = [
        [tool_use("a", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("b", "ping", src="h1", dst="web.lab")],
        [tool_use("c", "port_check", src="h1", dst="web.lab", port=80)],
        [tool_use("d", "dns_lookup", src="h1", name="web.lab")],
        [final("f1", "fault", "dns_failure", ["E1", "E4"])],                    # rejected: ping/port masked
        [tool_use("e", "ping", src="h1", dst="h2")],
        [tool_use("g", "port_check", src="h1", dst="h2", port=80)],
        [tool_use("f2", "final_answer", verdict="fault", fault_type="dns_failure", evidence=["E1", "E4", "E6"],
                  other_faults=["port_blocked"])],
    ]
    log = run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 12)
    assert log.status == "answered" and log.rejected_claims == 1
    assert log.answer["other_faults"] == ["port_blocked"]


def test_when_the_test_budget_is_used_up_a_confirmed_fault_is_accepted_even_if_an_area_is_untried():
    c = Controller(max_tests=5)
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))   # confirmed
    c.observe(R("ping", False, "dns", src="h1", dst="web.lab"))          # masked
    c.observe(R("ping", False, "connectivity", src="h1", dst="10.0.2.10"))
    ok, why = c.allow_claim("fault", "dns_failure", ["E1"])
    assert not ok and "port_check" in why and "has not been run" in why  # budget left: keep checking
    c.observe(R("ping", False, "connectivity", src="r1", dst="10.0.2.10"))   # fifth test: budget used up
    assert c.allow_claim("fault", "dns_failure", ["E1"])[0]


def test_budget_exhaustion_never_accepts_an_unconfirmed_fault():
    c = Controller(max_tests=2)
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))
    ok, _ = c.allow_claim("fault", "dns_failure", ["E1"])
    assert not ok
