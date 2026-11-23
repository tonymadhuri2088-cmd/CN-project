"""The third fresh suite is frozen: these tests pin its definitions so they cannot drift after results exist."""
from netwing.scenarios import CAMPUS, FRESH3_IDS, get_scenario
from netwing.scenarios import _SCENARIOS
from netwing.sim import SimNetwork

FROZEN = {
    "fx3_campus_multi_dns_route": ("dns_failure", {"dns", "route"}, ("route_failure",), True),
    "fx3_campus_noisy_multi_dns_route": ("dns_failure", {"noise", "dns", "route"}, ("route_failure",), True),
    "fx3_campus_blip_multi_dns_port": ("dns_failure", {"dns", "port", "blip"}, ("port_blocked",), True),
    "fx3_campus_noisy_flaky_multi_dns_port": ("dns_failure", {"noise", "dns", "flaky_port"}, ("port_blocked",), True),
    "fx3_campus_noisy_blip_port": ("port_blocked", {"noise", "port", "blip"}, (), True),
    "fx3_blip_route": ("route_failure", {"route", "blip"}, (), False),
    "fx3_campus_blip": ("healthy", {"blip"}, (), True),
}


def _sig(s):
    return (s.ticket, s.truth, frozenset(s.faults), s.also, str(s.topology))


def test_frozen_definitions_do_not_drift():
    assert FRESH3_IDS == list(FROZEN)
    for sid, (truth, faults, also, campus) in FROZEN.items():
        s = get_scenario(sid)
        assert (s.truth, set(s.faults), s.also) == (truth, faults, also)
        assert (s.topology is CAMPUS or s.topology == CAMPUS) == campus


def test_no_definition_repeats_an_earlier_suite_and_ids_are_new():
    earlier = {i for i in _SCENARIOS if i not in FRESH3_IDS}
    assert not set(FRESH3_IDS) & earlier
    old = {_sig(_SCENARIOS[i]) for i in earlier}
    assert not [i for i in FRESH3_IDS if _sig(_SCENARIOS[i]) in old]


def test_multi_fault_heavy_with_one_healthy_network():
    assert sum(1 for i in FRESH3_IDS if get_scenario(i).also) == 4
    assert [i for i in FRESH3_IDS if get_scenario(i).truth == "healthy"] == ["fx3_campus_blip"]


def test_tickets_do_not_reveal_the_truth():
    for i in FRESH3_IDS:
        t = get_scenario(i).ticket.lower()
        assert not any(w in t for w in ("healthy", "no fault", "route failure", "misconfig"))


def test_simulator_behaviour_matches_the_definitions():
    n = SimNetwork(get_scenario("fx3_campus_blip"))
    assert [n.ping("h1", "web.lab").ok for _ in range(3)] == [False, True, True]
    n = SimNetwork(get_scenario("fx3_campus_noisy_flaky_multi_dns_port"))
    assert n.dns_lookup("h1", "web.lab").ok is False
    assert [n.port_check("h1", "10.0.2.10", 80).ok for _ in range(4)] == [False, True, False, True]
    n = SimNetwork(get_scenario("fx3_campus_multi_dns_route"))
    assert n.dns_lookup("h1", "web.lab").ok is False and n.ping("h1", "10.0.2.10").ok is False
