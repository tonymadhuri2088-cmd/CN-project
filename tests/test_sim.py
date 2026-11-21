from netwing.scenarios import ALL_IDS, get_scenario
from netwing.sim import SimNetwork


def net(scenario_id):
    return SimNetwork(get_scenario(scenario_id))


def test_all_four_scenarios_exist():
    assert set(ALL_IDS) == {"dns_failure", "route_failure", "port_blocked", "healthy_false_alarm"}


def test_healthy_all_tests_pass():
    n = net("healthy_false_alarm")
    assert n.ping("h1", "h2").ok
    assert n.dns_lookup("h1", "web.lab").ok
    assert n.port_check("h1", "h2", 80).ok


def test_dns_failure_only_dns_fails():
    n = net("dns_failure")
    r = n.dns_lookup("h1", "web.lab")
    assert not r.ok and r.category == "dns"
    assert n.ping("h1", "h2").ok


def test_route_failure_ping_and_traceroute_fail():
    n = net("route_failure")
    p = n.ping("h1", "h2")
    assert not p.ok and p.category == "connectivity"
    assert not n.traceroute("h1", "h2").ok
    assert "10.0.2.0/24" not in n.show_routes("r1").output


def test_port_blocked_only_port_fails():
    n = net("port_blocked")
    assert n.ping("h1", "h2").ok
    r = n.port_check("h1", "h2", 80)
    assert not r.ok and r.category == "port"


def test_unknown_host_is_invalid():
    r = net("healthy_false_alarm").ping("h1", "nope")
    assert not r.ok and r.category == "invalid"


def test_bad_port_is_invalid():
    r = net("healthy_false_alarm").port_check("h1", "h2", 99999)
    assert not r.ok and r.category == "invalid"


def test_sim_outputs_marked_simulated():
    n = net("route_failure")
    results = [
        n.ping("h1", "h2"),
        n.traceroute("h1", "h2"),
        n.dns_lookup("h1", "web.lab"),
        n.port_check("h1", "h2", 80),
        n.show_routes("r1"),
        n.ping("h1", "nope"),
    ]
    for r in results:
        assert r.output.rstrip().endswith("[SIMULATED]")


def test_healthy_ticket_wrongly_claims_outage():
    s = get_scenario("healthy_false_alarm")
    assert s.truth == "healthy"
    assert "web.lab" in s.ticket
