"""The fourth fresh suite is frozen before the masking-v2 evaluation: these tests pin its definitions."""
from netwing.scenarios import CAMPUS, FRESH4_IDS, get_scenario
from netwing.scenarios import _SCENARIOS
from netwing.sim import SimNetwork

FROZEN = {
    "fx4_blip_port": ("port_blocked", {"port", "blip"}, False),
    "fx4_noisy_blip_port": ("port_blocked", {"noise", "port", "blip"}, False),
    "fx4_campus_blip_port": ("port_blocked", {"port", "blip"}, True),
    "fx4_flaky_route": ("route_failure", {"route"}, False),
    "fx4_campus_flaky_route": ("route_failure", {"route"}, True),
    "fx4_noisy_blip_route": ("route_failure", {"noise", "route", "blip"}, False),
    "fx4_campus_noisy_blip_route": ("route_failure", {"noise", "route", "blip"}, True),
}


def _sig(s):
    return (s.ticket, s.truth, frozenset(s.faults), s.also, str(s.topology))


def test_frozen_definitions_do_not_drift():
    assert FRESH4_IDS == list(FROZEN)
    for sid, (truth, faults, campus) in FROZEN.items():
        s = get_scenario(sid)
        assert (s.truth, set(s.faults), s.also) == (truth, faults, ())
        assert (s.topology is CAMPUS or s.topology == CAMPUS) == campus


def test_no_definition_repeats_an_earlier_suite_and_ids_are_new():
    earlier = {i for i in _SCENARIOS if i not in FRESH4_IDS}
    assert not set(FRESH4_IDS) & earlier
    old = {_sig(_SCENARIOS[i]) for i in earlier}
    assert not [i for i in FRESH4_IDS if _sig(_SCENARIOS[i]) in old]
    assert len({_sig(_SCENARIOS[i]) for i in FRESH4_IDS}) == len(FRESH4_IDS)


def test_three_port_blip_probes_and_four_route_only_scenarios():
    assert sum(1 for i in FRESH4_IDS if get_scenario(i).truth == "port_blocked") == 3
    assert sum(1 for i in FRESH4_IDS if get_scenario(i).truth == "route_failure") == 4


def test_tickets_do_not_reveal_the_truth():
    for i in FRESH4_IDS:
        t = get_scenario(i).ticket.lower()
        assert not any(w in t for w in ("healthy", "no fault", "route failure", "port blocked", "misconfig"))


def test_simulator_behaviour_matches_the_definitions():
    n = SimNetwork(get_scenario("fx4_blip_port"))
    assert [n.ping("h1", "web.lab").ok for _ in range(3)] == [False, True, True]
    assert n.port_check("h1", "10.0.2.10", 80).ok is False
    n = SimNetwork(get_scenario("fx4_flaky_route"))
    assert [n.ping("h1", "10.0.2.10").ok for _ in range(3)] == [False, False, False]
