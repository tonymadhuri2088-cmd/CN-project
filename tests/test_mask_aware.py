"""Opt-in masking rule: a standing route/connectivity failure makes port checks fail on their own, so a port_blocked claim is not
accepted on that evidence. Default behaviour (published) is unchanged and pinned here too."""
from netwing.backend import ToolResult
from netwing.controller import Controller, Verdict


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


def route_only(**kw):
    """Route fault only: ping fails twice, DNS passes, the port check times out twice as a consequence of the route."""
    c = Controller(max_tests=12, **kw)
    c.observe(R("dns_lookup", True, "dns", name="web.lab"))                       # E1
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))           # E2
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))           # E3
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))    # E4 (masked by the route fault)
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))    # E5
    return c


def test_default_still_accepts_port_blocked_on_a_route_only_network():
    """Pins the known, published false positive: the default controller is unchanged."""
    c = route_only()
    assert c.decide() == Verdict.STOP_FAULT
    assert c.allow_claim("fault", "port_blocked", ["E4", "E5"])[0]


def test_mask_aware_rejects_port_blocked_while_a_route_failure_stands():
    c = route_only(mask_aware=True)
    ok, why = c.allow_claim("fault", "port_blocked", ["E4", "E5"])
    assert not ok and "route" in why and "port" in why


def test_mask_aware_still_accepts_the_route_failure_itself():
    c = route_only(mask_aware=True)
    assert c.allow_claim("fault", "route_failure", ["E2", "E3"])[0]


def test_mask_aware_accepts_a_real_port_fault_when_ping_passes():
    c = Controller(max_tests=12, mask_aware=True)
    c.observe(R("dns_lookup", True, "dns", name="web.lab"))
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    assert c.decide() == Verdict.STOP_FAULT
    assert c.allow_claim("fault", "port_blocked", ["E3", "E4"])[0]


def test_a_cleared_blip_does_not_mask():
    c = Controller(max_tests=12, mask_aware=True)
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))            # blip cleared
    c.observe(R("dns_lookup", True, "dns", name="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    assert c.allow_claim("fault", "port_blocked", ["E5", "E6"])[0]


def test_masked_faults_are_exposed_for_audit():
    assert route_only(mask_aware=True).masked_faults() == {"port_blocked"}
    assert route_only().masked_faults() == {"port_blocked"}  # the audit view is always available; only the gate is opt-in


def test_secondary_port_claim_is_unsupported_while_masked():
    c = route_only(mask_aware=True, validate_claims=True)
    kept, report = c.validate_other_faults("route_failure", ["port_blocked"])
    assert kept == [] and report[1]["status"] == "unsupported" and "mask" in report[1]["reason"].lower()


def test_secondary_port_claim_unchanged_by_default():
    c = route_only(validate_claims=True)
    kept, _ = c.validate_other_faults("route_failure", ["port_blocked"])
    assert kept == ["port_blocked"]
