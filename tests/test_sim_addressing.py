import pytest
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork


def net(sid):
    return SimNetwork(get_scenario(sid))


@pytest.mark.parametrize("dst", ["web.lab", "10.0.2.10", "h2"])
def test_healthy_network_reaches_server_by_name_ip_or_node(dst):
    n = net("healthy_false_alarm")
    assert n.ping("h1", dst).ok
    assert n.traceroute("h1", dst).ok
    assert n.port_check("h1", dst, 80).ok


@pytest.mark.parametrize("dst", ["web.lab", "10.0.2.10"])
def test_route_failure_breaks_name_and_ip_as_connectivity_evidence(dst):
    n = net("route_failure")
    p = n.ping("h1", dst)
    assert not p.ok and p.category == "connectivity" and p.evidence
    q = n.port_check("h1", dst, 80)
    assert not q.ok and q.category == "port"


def test_port_blocked_by_name_is_a_port_failure_with_evidence():
    q = net("port_blocked").port_check("h1", "web.lab", 80)
    assert not q.ok and q.category == "port" and q.evidence
    assert net("port_blocked").ping("h1", "web.lab").ok


def test_dns_failure_makes_name_targets_fail_as_dns_but_ip_still_works():
    n = net("dns_failure")
    p = n.ping("h1", "web.lab")
    assert not p.ok and p.category == "dns" and p.evidence
    assert n.ping("h1", "10.0.2.10").ok
    assert n.port_check("h1", "10.0.2.10", 80).ok


def test_truly_unknown_target_is_still_invalid():
    assert net("healthy_false_alarm").ping("h1", "nowhere").category == "invalid"
