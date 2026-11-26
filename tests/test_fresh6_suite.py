"""The sixth fresh suite is frozen before the layer-coverage-with-confirmation-scoring evaluation: these tests pin its definitions."""
from netwing.scenarios import CAMPUS, FRESH6_IDS, get_scenario
from netwing.scenarios import _SCENARIOS
from netwing.sim import SimNetwork

# id: (truth, faults, also, campus)
FROZEN = {
    "fx6_campus_noisy_port_dns": ("port_blocked", {"noise", "port", "dns"}, ("dns_failure",), True),
    "fx6_campus_noisy_route_dns": ("route_failure", {"noise", "route", "dns"}, ("dns_failure",), True),
    "fx6_flaky_campus_dns_port": ("dns_failure", {"dns", "port"}, ("port_blocked",), True),
    "fx6_blip_route_dns": ("route_failure", {"blip", "route", "dns"}, ("dns_failure",), False),
    "fx6_flaky_campus_noisy_port": ("port_blocked", {"noise", "port"}, (), True),
    "fx6_flaky_noisy_dns": ("dns_failure", {"dns", "noise"}, (), False),
    "fx6_flaky_campus_noisy_healthy": ("healthy", {"noise"}, (), True),
}


def _sig(s):
    return (s.ticket, s.truth, frozenset(s.faults), s.also, str(s.topology))


def test_frozen_definitions_do_not_drift():
    assert FRESH6_IDS == list(FROZEN)
    for sid, (truth, faults, also, campus) in FROZEN.items():
        s = get_scenario(sid)
        assert (s.truth, set(s.faults), s.also) == (truth, faults, also)
        assert (s.topology is CAMPUS or s.topology == CAMPUS) == campus


def test_no_definition_repeats_an_earlier_suite_and_ids_are_new():
    earlier = {i for i in _SCENARIOS if i not in FRESH6_IDS}
    assert not set(FRESH6_IDS) & earlier
    old = {_sig(_SCENARIOS[i]) for i in earlier}
    assert not [i for i in FRESH6_IDS if _sig(_SCENARIOS[i]) in old]
    assert len({_sig(_SCENARIOS[i]) for i in FRESH6_IDS}) == len(FRESH6_IDS)


def test_four_double_fault_scenarios_two_single_and_one_healthy():
    assert sum(1 for i in FRESH6_IDS if get_scenario(i).also) == 4
    assert sum(1 for i in FRESH6_IDS if get_scenario(i).truth == "healthy") == 1


def test_tickets_do_not_reveal_the_truth():
    for i in FRESH6_IDS:
        t = get_scenario(i).ticket.lower()
        assert not any(w in t for w in ("healthy", "no fault", "route failure", "port blocked", "misconfig"))


def test_simulator_has_both_faults_in_double_fault_scenarios():
    n = SimNetwork(get_scenario("fx6_campus_noisy_port_dns"))
    assert not n.dns_lookup("h1", "web.lab").ok
    assert not n.port_check("h1", "web.lab", 80).ok
