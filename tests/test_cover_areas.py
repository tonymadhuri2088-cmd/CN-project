"""Opt-in layer-coverage stopping rule (`cover_areas`): do not stop on a fault while another area still has an unconfirmed
(single-sighting, standing) failure. Default behaviour is untouched."""
from netwing.backend import ToolResult
from netwing.controller import Controller, Verdict


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


def double_fault(**kw):
    """DNS fails twice (reproduced); a port check failed once (one sighting, standing); connectivity fine."""
    c = Controller(max_tests=12, **kw)
    c.observe(R("ping", True, "connectivity", src="h1", dst="10.0.0.2"))
    c.observe(R("dns_lookup", False, "dns", name="web.lab"))
    c.observe(R("dns_lookup", False, "dns", name="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="10.0.0.2", port=80))
    return c


def test_default_stops_on_primary_fault_even_with_an_unconfirmed_second_area():
    assert double_fault().decide() == Verdict.STOP_FAULT


def test_cover_areas_continues_while_a_second_area_has_one_sighting():
    c = double_fault(cover_areas=True)
    assert c.decide() == Verdict.CONTINUE
    assert c.pending_areas() == {"port"}


def test_cover_areas_stops_once_the_second_area_is_reproduced():
    c = double_fault(cover_areas=True)
    c.observe(R("port_check", False, "port", src="h1", dst="10.0.0.2", port=80))
    assert c.pending_areas() == set()
    assert c.decide() == Verdict.STOP_FAULT


def test_cover_areas_stops_once_the_single_sighting_clears():
    c = double_fault(cover_areas=True)
    c.observe(R("port_check", True, "port", src="h1", dst="10.0.0.2", port=80))
    c.observe(R("port_check", True, "port", src="h1", dst="10.0.0.2", port=80))
    assert c.decide() == Verdict.STOP_FAULT


def test_cover_areas_ignores_port_failures_masked_by_a_reproduced_route_failure():
    c = Controller(max_tests=12, cover_areas=True)
    c.observe(R("dns_lookup", True, "dns", name="web.lab"))
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("ping", False, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))  # one sighting, but masked by the route
    assert c.pending_areas() == set()
    assert c.decide() == Verdict.STOP_FAULT


def test_cover_areas_still_ends_at_the_cap():
    c = Controller(max_tests=5, cover_areas=True)
    c.observe(R("ping", True, "connectivity", src="h1", dst="10.0.0.2"))
    c.observe(R("dns_lookup", False, "dns", name="web.lab"))
    c.observe(R("dns_lookup", False, "dns", name="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="10.0.0.2", port=80))
    c.observe(R("ping", True, "connectivity", src="h1", dst="10.0.0.2"))
    assert c.decide() == Verdict.STOP_CAP


def test_cover_areas_hint_names_the_area_to_retest():
    c = double_fault(cover_areas=True)
    assert "port" in c.cover_hint()
    assert double_fault().cover_hint() == ""


def test_cover_areas_does_not_change_healthy_decisions():
    base, cov = Controller(max_tests=12), Controller(max_tests=12, cover_areas=True)
    for c in (base, cov):
        c.observe(R("ping", True, "connectivity", src="h1", dst="10.0.0.2"))
        c.observe(R("dns_lookup", True, "dns", name="web.lab"))
        c.observe(R("port_check", True, "port", src="h1", dst="10.0.0.2", port=80))
    assert base.decide() == cov.decide()
