"""Opt-in healthy strategies (rules / hybrid / belief), the retest hint and the source-aware belief.

The default ("rules") must behave exactly as published; the other strategies may only ever add a healthy
verdict where the rules would refuse, never touch a fault verdict, and never turn STOP_CAP into healthy.
"""
import json

import pytest

from netwing.backend import ToolResult
from netwing.belief import Belief
from netwing.controller import Controller, Verdict
from netwing.demo import main
from netwing.scenarios import (ALL_IDS, CAMPUS_IDS, FLAKY_IDS, FRESH_IDS, HARD_IDS, HELDOUT_IDS, LAB_IDS, MULTI_IDS,
                               Subject, get_scenario)
from netwing.sim import SimNetwork

SUBJ = Subject()


def obs(c, tool, ok, category, **args):
    return c.observe(ToolResult(tool=tool, args=args, output="x", ok=ok, category=category))


def ping(c, ok, dst="web.lab"):
    return obs(c, "ping", ok, "connectivity", src="h1", dst=dst)


def dns(c, ok, name="web.lab", src="h1"):
    return obs(c, "dns_lookup", ok, "dns", src=src, name=name)


def port(c, ok, dst="web.lab", p=80):
    return obs(c, "port_check", ok, "port", src="h1", dst=dst, port=p)


def make(strategy="rules", max_tests=12, **kw):
    return Controller(max_tests=max_tests, subject=SUBJ, healthy_strategy=strategy, **kw)


def blip_once_retested(c):
    """E1 ping fails; the identical check passes only once; every other area passes (the 10 held-out blip cases)."""
    ping(c, False)
    dns(c, True)
    port(c, True)
    ping(c, True)
    ping(c, True, "10.0.2.10")


# ---- healthy networks ------------------------------------------------------
@pytest.mark.parametrize("strategy", ["rules", "hybrid", "belief"])
def test_all_relevant_checks_passing_is_healthy_in_every_strategy(strategy):
    c = make(strategy)
    ping(c, True), dns(c, True), port(c, True)
    assert c.decide() == Verdict.STOP_HEALTHY
    assert c.allow_claim("healthy", "none", ["E1"])[0]


def test_transient_failure_cleared_by_two_identical_passes_is_healthy_under_the_default_rule():
    c = make("rules")
    ping(c, False), dns(c, True), port(c, True), ping(c, True), ping(c, True)
    assert c.decide() == Verdict.STOP_HEALTHY
    assert c.allow_claim("healthy", "none", [])[0]
    assert c.healthy_basis.startswith("rules")


# ---- noisy / transient failures --------------------------------------------
def test_default_rule_refuses_a_blip_that_was_retested_only_once():
    c = make("rules")
    blip_once_retested(c)
    ok, why = c.allow_claim("healthy", "none", [])
    assert not ok and "exact same check" in why
    assert c.decide() == Verdict.CONTINUE


def test_hybrid_accepts_the_once_retested_blip_and_records_why():
    c = make("hybrid")
    blip_once_retested(c)
    assert c.decide() == Verdict.STOP_HEALTHY
    ok, _ = c.allow_claim("healthy", "none", [])
    assert ok and c.healthy_basis.startswith("hybrid: P(healthy)=")


def test_belief_strategy_is_experimental_and_labelled_so():
    c = make("belief")
    blip_once_retested(c)
    assert c.allow_claim("healthy", "none", [])[0]
    assert "experimental" in c.healthy_basis


def test_irrelevant_failures_never_block_or_support_healthy():
    c = make("rules")
    ping(c, True), dns(c, True), port(c, True)
    dns(c, False, name="printer.lab"), port(c, False, dst="h2", p=8080), ping(c, False, dst="10.0.3.10")
    assert c.decide() == Verdict.STOP_HEALTHY  # unrelated alerts are not evidence


# ---- what hybrid must refuse -----------------------------------------------
def test_hybrid_refuses_a_failure_that_was_never_retested():
    c = make("hybrid")
    ping(c, False), dns(c, True), port(c, True), ping(c, True, "10.0.2.10"), ping(c, True, "h2")
    assert not c.allow_claim("healthy", "none", [])[0]  # name vs address vs host are different checks


def test_hybrid_refuses_when_the_latest_identical_retest_failed():
    c = make("hybrid")
    ping(c, False), dns(c, True), port(c, True), ping(c, True), ping(c, False)
    assert not c.allow_claim("healthy", "none", [])[0]


def test_hybrid_never_overrules_a_reproduced_failure():
    c = make("hybrid")
    ping(c, False), ping(c, True), ping(c, False), dns(c, True), port(c, True), ping(c, True)
    assert c._reproduced(c._failures())
    assert not c.allow_claim("healthy", "none", [])[0]


def test_hybrid_refuses_when_an_area_never_passed():
    c = make("hybrid")
    ping(c, False), ping(c, True), dns(c, True)  # port never checked
    assert not c.allow_claim("healthy", "none", [])[0]


def test_flaky_port_that_fails_then_passes_is_not_called_healthy():
    c = make("hybrid")
    ping(c, True), dns(c, True), port(c, False), port(c, True)
    ok, _ = c.allow_claim("healthy", "none", [])
    assert not ok  # P(healthy) stays below the threshold: an intermittent fault passes sometimes
    assert c._belief().p_healthy() < c.belief_tau


# ---- genuine faults stay faults --------------------------------------------
@pytest.mark.parametrize("strategy", ["rules", "hybrid"])
def test_genuine_dns_failure_is_still_a_fault(strategy):
    c = make(strategy)
    dns(c, False), dns(c, False), ping(c, True), port(c, True)
    assert c.decide() == Verdict.STOP_FAULT
    assert not c.allow_claim("healthy", "none", ["E1"])[0]
    assert c.allow_claim("fault", "dns_failure", ["E1", "E2"])[0]


@pytest.mark.parametrize("strategy", ["rules", "hybrid"])
def test_genuine_routing_failure_is_still_a_fault(strategy):
    c = make(strategy)
    ping(c, False), ping(c, False), dns(c, True), port(c, False)
    assert c.decide() == Verdict.STOP_FAULT
    assert not c.allow_claim("healthy", "none", [])[0]


@pytest.mark.parametrize("strategy", ["rules", "hybrid", "belief"])
def test_simultaneous_faults_are_never_called_healthy(strategy):
    c = make(strategy)
    dns(c, False), dns(c, False), port(c, False), port(c, False), ping(c, True)
    assert not c.allow_claim("healthy", "none", [])[0]
    assert c.decide() != Verdict.STOP_HEALTHY


# ---- budget and insufficient evidence --------------------------------------
@pytest.mark.parametrize("strategy", ["rules", "hybrid", "belief"])
def test_budget_exhaustion_stays_stop_cap_not_healthy(strategy):
    c = make(strategy, max_tests=3)
    ping(c, False), dns(c, True), port(c, True)
    assert c.decide() == Verdict.STOP_CAP


def test_insufficient_evidence_is_not_healthy():
    c = make("hybrid")
    ping(c, False)
    assert not c.allow_claim("healthy", "none", [])[0]
    assert c.decide() == Verdict.CONTINUE


def test_no_test_at_all_is_not_healthy():
    assert not make("hybrid").allow_claim("healthy", "none", [])[0]


# ---- calibration ------------------------------------------------------------
def test_a_stricter_threshold_makes_hybrid_more_conservative():
    c = make("hybrid", belief_tau=0.99)
    blip_once_retested(c)
    assert not c.allow_claim("healthy", "none", [])[0]


@pytest.mark.parametrize("tau", [0.5, 0.4, 1.0, 1.2])
def test_belief_tau_must_lie_strictly_between_half_and_one(tau):
    with pytest.raises(ValueError):
        Controller(healthy_strategy="hybrid", belief_tau=tau)


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError):
        Controller(healthy_strategy="optimistic")


def test_miscalibrated_noise_parameters_swing_the_belief_but_not_the_rule_checks():
    """Calibration matters: the same blip pattern reads as healthy (~0.88) under the default noise, as a real fault
    (~0.41) if blips are assumed almost impossible, and as near-certainly healthy if intermittent faults are assumed
    never to pass. The hybrid's rule checks (retested, latest passed, not reproduced) do not
    depend on the noise values, so a bad calibration can only make hybrid refuse more or less, never skip them."""
    def p_healthy(**kw):
        b = Belief(**kw)
        for cat, ok in (("connectivity", False), ("dns", True), ("port", True), ("connectivity", True), ("connectivity", True)):
            b.update(cat, ok)
        return b.p_healthy()

    assert p_healthy(false_fail=0.001) < 0.85 < p_healthy() < p_healthy(miss=0.001)
    c = make("hybrid")
    ping(c, False), dns(c, True), port(c, True)  # failure never retested
    assert not c.allow_claim("healthy", "none", [])[0]


# ---- source awareness -------------------------------------------------------
def test_dns_failure_from_a_host_without_a_resolver_is_ignored_by_the_belief():
    b = Belief()
    before = b.p_healthy()
    assert b.update("dns", False, source="h2", resolver_hosts={"h1"}) is False
    assert b.p_healthy() == before
    assert b.update("dns", False, source="h1", resolver_hosts={"h1"}) is True
    assert b.p_healthy() < before


def test_default_belief_counts_every_host():
    b = Belief()
    assert b.update("dns", False, source="h2") is True


def test_controller_ignores_dns_readings_from_hosts_without_a_resolver():
    c = make("rules", resolver_hosts={"h1"})
    ping(c, True), dns(c, True), port(c, True)
    dns(c, False, src="h2"), dns(c, False, src="h2")
    assert c._failures() == []
    assert c.decide() == Verdict.STOP_HEALTHY


def test_without_resolver_hosts_a_repeated_dns_failure_from_h2_still_counts():
    c = make("rules")
    dns(c, False, src="h2"), dns(c, False, src="h2")
    assert len(c._failures()) == 2  # default behaviour unchanged


def test_a_genuine_dns_failure_from_a_resolver_host_still_counts():
    c = make("rules", resolver_hosts={"h1"})
    dns(c, False), dns(c, False), ping(c, True), port(c, True)
    assert c.decide() == Verdict.STOP_FAULT


# ---- retest hint ------------------------------------------------------------
def test_hint_flags_irrelevant_results_and_changes_no_verdict():
    c = make("rules")
    res = ToolResult("dns_lookup", {"src": "h1", "name": "printer.lab"}, "x", False, "dns")
    eid = c.observe(res)
    assert "does not count" in c.hint(res, eid)
    assert c.decide() == Verdict.CONTINUE


def test_hint_names_the_standing_failure_and_what_clears_it():
    c = make("rules", max_tests=12)
    res = ToolResult("ping", {"src": "h1", "dst": "web.lab"}, "x", False, "connectivity")
    eid = c.observe(res)
    h = c.hint(res, eid)
    assert "E1" in h and "identical check" in h and "2 more" in h and "11 test(s) left" in h
    r2 = ToolResult("ping", {"src": "h1", "dst": "web.lab"}, "x", True, "connectivity")
    assert "1 more" in c.hint(r2, c.observe(r2))


def test_hint_is_empty_when_nothing_stands_or_is_irrelevant():
    c = make("rules")
    res = ToolResult("ping", {"src": "h1", "dst": "web.lab"}, "x", True, "connectivity")
    assert c.hint(res, c.observe(res)) == ""


def test_hint_names_a_host_without_a_resolver():
    c = make("rules", resolver_hosts={"h1"})
    res = ToolResult("dns_lookup", {"src": "h2", "name": "web.lab"}, "x", False, "dns")
    assert "no DNS resolver" in c.hint(res, c.observe(res))


# ---- the fresh validation suite and the CLI --------------------------------
def test_fresh_ids_are_new_and_distinct_from_every_other_suite():
    others = set(ALL_IDS + HARD_IDS + FLAKY_IDS + MULTI_IDS + CAMPUS_IDS + LAB_IDS + HELDOUT_IDS)
    assert len(FRESH_IDS) == 8 and len(set(FRESH_IDS)) == 8 and not set(FRESH_IDS) & others


def test_fresh_ground_truth_and_tickets_do_not_reveal_it():
    truths = {i: get_scenario(i).truth for i in FRESH_IDS}
    assert sum(t == "healthy" for t in truths.values()) == 3
    assert {"dns_failure", "route_failure", "port_blocked"} <= set(truths.values())
    for i in FRESH_IDS:
        t = get_scenario(i).ticket.lower()
        assert not any(w in t for w in ("blocked", "route failure", "misconfig", "healthy", "no fault"))


def test_fresh_simulator_behaviours():
    n = SimNetwork(get_scenario("fx_blip"))
    assert [n.ping("h1", "web.lab").ok for _ in range(3)] == [False, True, True]
    n = SimNetwork(get_scenario("fx_flaky_port"))
    assert [n.port_check("h1", "web.lab", 80).ok for _ in range(4)] == [False, True, False, True]
    n = SimNetwork(get_scenario("fx_noisy_dns"))
    assert n.dns_lookup("h1", "web.lab").ok is False
    n = SimNetwork(get_scenario("fx_campus_blip"))
    assert [n.ping("h1", "web.lab").ok for _ in range(2)] == [False, True]


def test_fresh_suite_is_not_in_all_and_refuses_real_backends():
    with pytest.raises(SystemExit):
        main(["--backend", "netns", "--suite", "fresh", "--dry-run"])


def test_dry_run_accepts_the_new_flags_and_records_the_basis(tmp_path):
    out = tmp_path / "r.jsonl"
    rc = main(["--dry-run", "--backend", "sim", "--suite", "fresh", "--repeats", "1", "--modes", "netwing",
               "--healthy-strategy", "hybrid", "--belief-tau", "0.9", "--retest-hint", "--out", str(out)])
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == len(FRESH_IDS) and all("healthy_basis" in r for r in rows)


def test_default_strategy_is_rules():
    assert Controller().healthy_strategy == "rules"
