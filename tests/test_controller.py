from netwing.backend import ToolResult
from netwing.controller import Controller, Verdict


def r(category, ok, tool="ping"):
    return ToolResult(tool=tool, args={}, output="x", ok=ok, category=category)


def passing_three(c):
    ids = [c.observe(r("connectivity", True)), c.observe(r("dns", True, "dns_lookup")),
           c.observe(r("port", True, "port_check"))]
    return ids


def test_observe_returns_sequential_evidence_ids():
    c = Controller()
    assert c.observe(r("dns", True)) == "E1"
    assert c.observe(r("dns", True)) == "E2"
    assert c.tests_run == 2


def test_stop_healthy_after_three_passing_categories():
    c = Controller()
    passing_three(c)
    assert c.decide() == Verdict.STOP_HEALTHY


def test_continue_with_only_one_passing_category():
    c = Controller()
    c.observe(r("connectivity", True))
    assert c.decide() == Verdict.CONTINUE


def test_stop_fault_after_reproduced_failure_with_all_areas_tried():
    c = Controller()
    c.observe(r("dns", False, "dns_lookup"))
    c.observe(r("connectivity", True))
    c.observe(r("port", True, "port_check"))
    assert c.decide() == Verdict.CONTINUE        # failure not yet reproduced
    c.observe(r("dns", False, "dns_lookup"))
    assert c.decide() == Verdict.STOP_FAULT


def test_stop_cap_at_max_tests():
    c = Controller(max_tests=2)
    c.observe(r("connectivity", True))
    c.observe(r("connectivity", True))
    assert c.decide() == Verdict.STOP_CAP


def test_invalid_result_never_counts_as_evidence():
    c = Controller()
    c.observe(r("invalid", False))
    c.observe(r("invalid", False))
    assert c.decide() == Verdict.CONTINUE
    ok, _ = c.allow_claim("fault", "dns_failure", ["E1"])
    assert not ok


def test_invalid_results_still_count_against_cap():
    c = Controller(max_tests=2)
    c.observe(r("invalid", False))
    c.observe(r("invalid", False))
    assert c.decide() == Verdict.STOP_CAP


def test_fault_claim_without_failing_evidence_rejected():
    c = Controller()
    e = c.observe(r("connectivity", True))
    ok, msg = c.allow_claim("fault", "route_failure", [e])
    assert not ok
    assert "failing" in msg and "healthy" in msg


def test_fault_claim_wrong_category_rejected():
    c = Controller()
    e = c.observe(r("dns", False, "dns_lookup"))
    ok, _ = c.allow_claim("fault", "port_blocked", [e])
    assert not ok


def test_fault_claim_with_matching_failing_evidence_allowed():
    c = Controller()
    e = c.observe(r("dns", False, "dns_lookup"))
    c.observe(r("dns", False, "dns_lookup"))
    passing_three(c)
    ok, _ = c.allow_claim("fault", "dns_failure", [e])
    assert ok


def test_route_failure_accepts_connectivity_or_routing_evidence():
    c = Controller()
    e = c.observe(r("connectivity", False))
    c.observe(r("connectivity", False))
    passing_three(c)
    assert c.allow_claim("fault", "route_failure", [e])[0]


def test_healthy_claim_rejected_when_failure_exists():
    c = Controller()
    c.observe(r("port", False, "port_check"))
    c.observe(r("connectivity", True))
    ok, _ = c.allow_claim("healthy", "none", ["E2"])
    assert not ok


def test_healthy_claim_rejected_with_no_passing_tests():
    c = Controller()
    ok, msg = c.allow_claim("healthy", "none", [])
    assert not ok and "test" in msg


def test_healthy_claim_allowed_after_passing_tests():
    c = Controller()
    ids = passing_three(c)
    assert c.allow_claim("healthy", "none", ids)[0]


def test_unknown_evidence_id_rejected():
    c = Controller()
    c.observe(r("dns", False, "dns_lookup"))
    ok, msg = c.allow_claim("fault", "dns_failure", ["E99"])
    assert not ok and "E99" in msg


def test_fault_verdict_with_fault_type_none_rejected():
    c = Controller()
    e = c.observe(r("dns", False, "dns_lookup"))
    assert not c.allow_claim("fault", "none", [e])[0]
