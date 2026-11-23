"""The second fresh suite is frozen: these tests pin its definitions so they cannot drift after results exist."""
from netwing.scenarios import (ALL_IDS, CAMPUS, CAMPUS_IDS, FLAKY_IDS, FRESH2_IDS, FRESH_IDS, HARD_IDS, HELDOUT_IDS,
                               LAB_IDS, MULTI_IDS, get_scenario)
from netwing.sim import SimNetwork

FROZEN = {
    "fx2_noisy_blip": ("healthy", {"noise", "blip"}, (), False),
    "fx2_campus_noisy_blip": ("healthy", {"noise", "blip"}, (), True),
    "fx2_campus_noisy_flaky_port": ("port_blocked", {"noise", "flaky_port"}, (), True),
    "fx2_campus_noisy_dns": ("dns_failure", {"noise", "dns"}, (), True),
    "fx2_campus_noisy_port": ("port_blocked", {"noise", "port"}, (), True),
    "fx2_campus_noisy_route": ("route_failure", {"noise", "route"}, (), True),
    "fx2_campus_noisy_multi_dns_port": ("dns_failure", {"noise", "dns", "port"}, ("port_blocked",), True),
}


def test_frozen_definitions_do_not_drift():
    assert FRESH2_IDS == list(FROZEN)
    for sid, (truth, faults, also, campus) in FROZEN.items():
        s = get_scenario(sid)
        assert (s.truth, set(s.faults), s.also) == (truth, faults, also)
        assert (s.topology is CAMPUS or s.topology == CAMPUS) == campus


def test_ids_are_distinct_from_every_other_suite():
    others = set(ALL_IDS + HARD_IDS + FLAKY_IDS + MULTI_IDS + CAMPUS_IDS + LAB_IDS + HELDOUT_IDS + FRESH_IDS)
    assert len(set(FRESH2_IDS)) == 7 and not set(FRESH2_IDS) & others


def test_targets_the_failure_class_on_both_topologies_and_keeps_a_supported_double_fault():
    healthy = [i for i in FRESH2_IDS if get_scenario(i).truth == "healthy"]
    assert len(healthy) == 2 and {get_scenario(i).topology == CAMPUS for i in healthy} == {True, False}
    assert get_scenario("fx2_campus_noisy_multi_dns_port").also == ("port_blocked",)


def test_tickets_do_not_reveal_the_truth():
    for i in FRESH2_IDS:
        t = get_scenario(i).ticket.lower()
        assert not any(w in t for w in ("healthy", "no fault", "route failure", "misconfig"))


def test_simulator_behaviour_matches_the_definitions():
    n = SimNetwork(get_scenario("fx2_campus_noisy_blip"))
    assert [n.ping("h1", "web.lab").ok for _ in range(3)] == [False, True, True]
    assert n.dns_lookup("h1", "printer.lab").ok is False
    n = SimNetwork(get_scenario("fx2_campus_noisy_flaky_port"))
    assert [n.port_check("h1", "web.lab", 80).ok for _ in range(4)] == [False, True, False, True]
    n = SimNetwork(get_scenario("fx2_campus_noisy_multi_dns_port"))
    assert n.dns_lookup("h1", "web.lab").ok is False and n.port_check("h1", "10.0.2.10", 80).ok is False
