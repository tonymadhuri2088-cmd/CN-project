"""Held-out suite: combinations of conditions that no controller rule was tuned on (simulator only)."""
import pytest

from netwing.controller import Controller
from netwing.demo import _scenario_ids, build_parser, main
from netwing.scenarios import (ALL_IDS, CAMPUS_IDS, FLAKY_IDS, HARD_IDS, HELDOUT_IDS, LAB_IDS, MULTI_IDS,
                               get_scenario)
from netwing.scoring import score
from netwing.sim import SimNetwork


def test_heldout_ids_are_new_and_distinct_from_every_tuning_suite():
    assert len(HELDOUT_IDS) == 8 and len(set(HELDOUT_IDS)) == 8
    tuned = set(ALL_IDS) | set(HARD_IDS) | set(FLAKY_IDS) | set(MULTI_IDS) | set(CAMPUS_IDS) | set(LAB_IDS)
    assert not tuned & set(HELDOUT_IDS)
    assert all(i.startswith("ho_") for i in HELDOUT_IDS)


def test_heldout_ground_truth_and_extra_faults():
    t = {i: (get_scenario(i).truth, get_scenario(i).also) for i in HELDOUT_IDS}
    assert t["ho_noisy_blip"] == ("healthy", ())
    assert t["ho_noisy_flaky_port"] == ("port_blocked", ())
    assert t["ho_noisy_multi_dns_port"] == ("dns_failure", ("port_blocked",))
    assert t["ho_noisy_multi_dns_route"] == ("dns_failure", ("route_failure",))
    assert t["ho_flaky_dns"] == ("dns_failure", ())
    assert t["ho_campus_noisy_healthy"] == ("healthy", ())
    assert t["ho_campus_noisy_route"] == ("route_failure", ())
    assert t["ho_campus_multi_dns_port"] == ("dns_failure", ("port_blocked",))
    assert sum(1 for v in t.values() if v[0] == "healthy") == 2


def test_tickets_never_reveal_the_truth():
    assert len({get_scenario(i).ticket for i in ["ho_noisy_blip", "ho_noisy_flaky_port", "ho_noisy_multi_dns_port"]}) == 1
    for i in HELDOUT_IDS:
        low = get_scenario(i).ticket.lower()
        assert "dns fail" not in low and "route" not in low and "blocked" not in low


def test_noisy_blip_has_alerts_and_a_single_lost_ping_on_a_healthy_network():
    s = get_scenario("ho_noisy_blip")
    assert "printer.lab" in s.ticket
    net = SimNetwork(s)
    first, second = net.ping("h1", "h2"), net.ping("h1", "h2")
    assert not first.ok and second.ok
    assert net.dns_lookup("h1", "web.lab").ok and net.port_check("h1", "h2", 80).ok
    assert not net.dns_lookup("h1", "printer.lab").ok  # red herring


def test_noisy_flaky_port_alternates():
    net = SimNetwork(get_scenario("ho_noisy_flaky_port"))
    assert [net.port_check("h1", "h2", 80).ok for _ in range(4)] == [False, True, False, True]


def test_noisy_multi_dns_port_has_both_faults_behind_noise():
    net = SimNetwork(get_scenario("ho_noisy_multi_dns_port"))
    assert not net.dns_lookup("h1", "web.lab").ok
    assert not net.port_check("h1", "h2", 80).ok and net.ping("h1", "h2").ok
    assert not net.port_check("h1", "h2", 8080).ok  # red herring still present


def test_noisy_multi_dns_route_has_both_faults():
    net = SimNetwork(get_scenario("ho_noisy_multi_dns_route"))
    assert not net.dns_lookup("h1", "web.lab").ok and not net.ping("h1", "h2").ok


def test_flaky_dns_uses_the_intermittent_ticket_but_a_persistent_fault():
    s = get_scenario("ho_flaky_dns")
    assert "intermittent" in s.ticket
    net = SimNetwork(s)
    assert not net.dns_lookup("h1", "web.lab").ok and not net.dns_lookup("h1", "web.lab").ok


def test_campus_heldout_scenarios_use_the_bigger_network():
    for i in ("ho_campus_noisy_healthy", "ho_campus_noisy_route", "ho_campus_multi_dns_port"):
        assert "h4" in get_scenario(i).topology["hosts"]
    net = SimNetwork(get_scenario("ho_campus_noisy_route"))
    assert not net.ping("h1", "h2").ok and net.ping("h1", "h3").ok
    healthy = SimNetwork(get_scenario("ho_campus_noisy_healthy"))
    assert healthy.ping("h1", "h2").ok and healthy.port_check("h1", "h3", 5432).ok


def test_scoring_counts_all_faults_found_for_heldout_multi():
    s = get_scenario("ho_noisy_multi_dns_port")
    full = score(s, {"verdict": "fault", "fault_type": "dns_failure", "other_faults": ["port_blocked"], "evidence": []})
    only = score(s, {"verdict": "fault", "fault_type": "dns_failure", "evidence": []})
    assert full.correct and full.complete and only.correct and not only.complete


def test_controller_still_rejects_unconfirmed_claim_in_heldout_blip():
    s = get_scenario("ho_noisy_blip")
    net = SimNetwork(s)
    c = Controller(max_tests=12, subject=s.subject)
    e1 = c.observe(net.ping("h1", "h2"))
    ok, why = c.allow_claim("fault", "route_failure", [e1])
    assert not ok


def test_heldout_suite_selection_and_all_excludes_heldout():
    assert _scenario_ids(build_parser().parse_args(["--suite", "heldout"])) == HELDOUT_IDS
    assert not set(HELDOUT_IDS) & set(_scenario_ids(build_parser().parse_args(["--suite", "all"])))


def test_heldout_scenarios_refuse_real_backends():
    with pytest.raises(SystemExit, match="only in the simulator"):
        main(["--suite", "heldout", "--backend", "netns"])


def test_heldout_runs_end_to_end_in_dry_run(tmp_path, capsys):
    assert main(["--dry-run", "--suite", "heldout", "--repeats", "1", "--out", str(tmp_path / "r.jsonl")]) == 0
    assert "SIMULATED" in capsys.readouterr().out
