"""Opt-in masking v2: only a REPRODUCED route failure masks port claims (the first version also masked on a one-off blip)."""
from netwing.backend import ToolResult
from netwing.controller import Controller, Verdict


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


def blip_then_port_fault(**kw):
    """A single lost ping (not cleared, since only one pass followed), DNS fine, and a real port fault seen twice."""
    c = Controller(max_tests=12, **kw)
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))   # E1: the blip
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))    # E2: one pass only, so E1 still stands
    c.observe(R("dns_lookup", True, "dns", name="web.lab"))                # E3
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))  # E4
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))  # E5
    return c


def route_only(**kw):
    c = Controller(max_tests=12, **kw)
    c.observe(R("dns_lookup", True, "dns", name="web.lab"))
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    return c


def test_first_version_wrongly_masks_on_an_uncleared_blip():
    """Documents the defect found in the live run (fx3_campus_noisy_blip_port: 10 of 10 no-answers)."""
    c = blip_then_port_fault(mask_aware=True)
    assert not c.allow_claim("fault", "port_blocked", ["E4", "E5"])[0]


def test_reproduced_masking_does_not_mask_on_a_single_sighting():
    c = blip_then_port_fault(mask_reproduced=True)
    assert c.masked_faults() == set()
    assert c.allow_claim("fault", "port_blocked", ["E4", "E5"])[0]


def test_reproduced_masking_rejects_port_claim_when_the_route_failure_is_reproduced():
    c = route_only(mask_reproduced=True)
    ok, why = c.allow_claim("fault", "port_blocked", ["E4", "E5"])
    assert not ok and "route" in why
    assert c.allow_claim("fault", "route_failure", ["E2", "E3"])[0]


def test_defaults_unchanged_and_audit_view_is_independent_of_flags():
    c = route_only()
    assert c.allow_claim("fault", "port_blocked", ["E4", "E5"])[0]  # published false positive still present by default
    assert c.decide() == Verdict.STOP_FAULT


def test_drop_masked_secondary_removes_only_masked_claims():
    c = route_only(mask_reproduced=True)
    kept, dropped = c.drop_masked_secondary(["port_blocked", "dns_failure"])
    assert kept == ["dns_failure"] and dropped == ["port_blocked"]


def test_drop_masked_secondary_is_a_no_op_without_the_flag():
    c = route_only()
    assert c.drop_masked_secondary(["port_blocked"]) == (["port_blocked"], [])


def test_validation_path_marks_masked_secondary_unsupported():
    c = route_only(mask_reproduced=True, validate_claims=True)
    kept, report = c.validate_other_faults("route_failure", ["port_blocked"])
    assert kept == [] and report[1]["status"] == "unsupported"


def test_blip_secondary_port_claim_is_not_masked_under_v2():
    c = blip_then_port_fault(mask_reproduced=True, validate_claims=True)
    kept, report = c.validate_other_faults("dns_failure", ["port_blocked"])
    assert kept == ["port_blocked"] and report[1]["status"] == "confirmed"


def _route_run(**kw):
    from netwing.agent import run_diagnosis
    from netwing.scenarios import get_scenario
    from netwing.sim import SimNetwork
    from tests.fake_client import FakeClient, tool_use
    from tests.test_agent import guard
    s = get_scenario("route_failure")
    script = [
        [tool_use("a", "ping", src="h1", dst="web.lab")],
        [tool_use("b", "ping", src="h1", dst="web.lab")],
        [tool_use("c", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("d", "port_check", src="h1", dst="web.lab", port=80)],
        [tool_use("f", "final_answer", verdict="fault", fault_type="route_failure", evidence=["E1", "E2"],
                  other_faults=["port_blocked"])],
    ]
    return run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 12, **kw)


def test_agent_keeps_the_masked_secondary_claim_by_default():
    assert _route_run().answer["other_faults"] == ["port_blocked"]


def test_agent_drops_and_logs_the_masked_secondary_claim_with_mask_reproduced():
    log = _route_run(mask_reproduced=True)
    assert log.status == "answered" and log.answer["fault_type"] == "route_failure"
    assert log.answer["other_faults"] == [] and log.answer["dropped_masked"] == ["port_blocked"]
    assert log.answer["other_faults_raw"] == ["port_blocked"]
