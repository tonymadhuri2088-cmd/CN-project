"""The fifth fresh suite is frozen before the layer-coverage (`--cover-areas`) evaluation: these tests pin its definitions."""
from netwing.scenarios import CAMPUS, FRESH5_IDS, get_scenario
from netwing.scenarios import _SCENARIOS
from netwing.sim import SimNetwork

# id: (truth, faults, also, campus)
FROZEN = {
    "fx5_route_dns": ("route_failure", {"route", "dns"}, ("dns_failure",), False),
    "fx5_campus_port_dns": ("port_blocked", {"port", "dns"}, ("dns_failure",), True),
    "fx5_noisy_port_dns": ("port_blocked", {"noise", "port", "dns"}, ("dns_failure",), False),
    "fx5_flaky_dns_port": ("dns_failure", {"dns", "port"}, ("port_blocked",), False),
    "fx5_flaky_campus_dns": ("dns_failure", {"dns"}, (), True),
    "fx5_flaky_campus_port": ("port_blocked", {"port"}, (), True),
    "fx5_flaky_campus_healthy": ("healthy", set(), (), True),
}


def _sig(s):
    return (s.ticket, s.truth, frozenset(s.faults), s.also, str(s.topology))


def test_frozen_definitions_do_not_drift():
    assert FRESH5_IDS == list(FROZEN)
    for sid, (truth, faults, also, campus) in FROZEN.items():
        s = get_scenario(sid)
        assert (s.truth, set(s.faults), s.also) == (truth, faults, also)
        assert (s.topology is CAMPUS or s.topology == CAMPUS) == campus


def test_no_definition_repeats_an_earlier_suite_and_ids_are_new():
    earlier = {i for i in _SCENARIOS if i not in FRESH5_IDS}
    assert not set(FRESH5_IDS) & earlier
    old = {_sig(_SCENARIOS[i]) for i in earlier}
    assert not [i for i in FRESH5_IDS if _sig(_SCENARIOS[i]) in old]
    assert len({_sig(_SCENARIOS[i]) for i in FRESH5_IDS}) == len(FRESH5_IDS)


def test_four_double_fault_scenarios_two_single_and_one_healthy():
    assert sum(1 for i in FRESH5_IDS if get_scenario(i).also) == 4
    assert sum(1 for i in FRESH5_IDS if get_scenario(i).truth == "healthy") == 1


def test_tickets_do_not_reveal_the_truth():
    for i in FRESH5_IDS:
        t = get_scenario(i).ticket.lower()
        assert not any(w in t for w in ("healthy", "no fault", "route failure", "port blocked", "misconfig"))


def test_simulator_has_both_faults_in_double_fault_scenarios():
    n = SimNetwork(get_scenario("fx5_noisy_port_dns"))
    assert not n.dns_lookup("h1", "web.lab").ok
    assert not n.port_check("h1", "web.lab", 80).ok
