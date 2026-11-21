
from netwing.backend import ToolResult
from netwing.controller import Controller, Verdict
from netwing.scenarios import ALL_IDS, CAMPUS_IDS, FLAKY_IDS, HARD_IDS, MULTI_IDS, TICKET, get_scenario
from netwing.scoring import score
from netwing.sim import SimNetwork


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


PING = dict(src="h1", dst="web.lab")


# ---- controller: retesting a failure ---------------------------------------------------------
def test_one_passing_retest_neither_clears_nor_stops_as_fault():
    c = Controller()
    c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("ping", True, "connectivity", **PING))
    assert c.decide() == Verdict.CONTINUE
    assert not c.allow_claim("healthy", "none", [])[0]


def test_two_consecutive_passing_retests_clear_the_failure():
    c = Controller()
    c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("ping", True, "connectivity", **PING))
    c.observe(R("ping", True, "connectivity", **PING))
    c.observe(R("dns_lookup", True, "dns", src="h1", name="web.lab"))
    c.observe(R("port_check", True, "port", src="h1", dst="web.lab", port=80))
    assert c.decide() == Verdict.STOP_HEALTHY
    assert c.allow_claim("healthy", "none", [])[0]


def test_alternating_failure_is_confirmed_and_stops_as_fault():
    c = Controller()
    e = c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("port_check", True, "port", src="h1", dst="web.lab", port=80))
    assert c.decide() == Verdict.CONTINUE
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("dns_lookup", True, "dns", src="h1", name="web.lab"))
    assert c.decide() == Verdict.STOP_FAULT
    assert c.allow_claim("fault", "port_blocked", [e])[0]


def test_citing_a_cleared_failure_as_fault_evidence_is_rejected():
    c = Controller()
    e = c.observe(R("ping", False, "connectivity", **PING))
    c.observe(R("ping", True, "connectivity", **PING))
    c.observe(R("ping", True, "connectivity", **PING))
    assert not c.allow_claim("fault", "route_failure", [e])[0]


# ---- scenarios ------------------------------------------------------------------------------
def test_suites_are_disjoint_and_share_tickets_within_a_suite():
    suites = [ALL_IDS, HARD_IDS, FLAKY_IDS, MULTI_IDS, CAMPUS_IDS]
    flat = [i for s in suites for i in s]
    assert len(flat) == len(set(flat))
    for ids in (FLAKY_IDS, CAMPUS_IDS):
        assert len({get_scenario(i).ticket for i in ids}) == 1
    assert {get_scenario(i).ticket for i in MULTI_IDS} == {TICKET}


def test_truth_sets():
    assert get_scenario("transient_blip").truth == "healthy"
    assert get_scenario("intermittent_port").truth == "port_blocked"
    s = get_scenario("multi_dns_port")
    assert {s.truth, *s.also} == {"dns_failure", "port_blocked"}


# ---- sim: flaky -----------------------------------------------------------------------------
def test_transient_blip_fails_once_then_always_passes():
    n = SimNetwork(get_scenario("transient_blip"))
    assert not n.ping("h1", "web.lab").ok
    assert all(n.ping("h1", "web.lab").ok for _ in range(4))
    assert n.port_check("h1", "web.lab", 80).ok and n.dns_lookup("h1", "web.lab").ok


def test_intermittent_port_alternates_fail_pass():
    n = SimNetwork(get_scenario("intermittent_port"))
    seq = [n.port_check("h1", "web.lab", 80).ok for _ in range(4)]
    assert seq == [False, True, False, True]
    r = n.port_check("h1", "web.lab", 80)
    assert r.category == "port"


# ---- sim: multi -------------------------------------------------------------------------------
def test_multi_dns_port_breaks_name_resolution_and_the_port_but_not_the_path():
    n = SimNetwork(get_scenario("multi_dns_port"))
    assert not n.dns_lookup("h1", "web.lab").ok
    assert n.ping("h1", "10.0.2.10").ok
    assert not n.port_check("h1", "10.0.2.10", 80).ok


def test_multi_dns_route():
    n = SimNetwork(get_scenario("multi_dns_route"))
    assert not n.dns_lookup("h1", "web.lab").ok and not n.ping("h1", "10.0.2.10").ok


# ---- scoring: multi ---------------------------------------------------------------------------
def test_multi_scoring_correct_vs_complete():
    s = get_scenario("multi_dns_port")
    one = score(s, {"verdict": "fault", "fault_type": "dns_failure", "evidence": []})
    assert one.correct and not one.complete
    both = score(s, {"verdict": "fault", "fault_type": "dns_failure", "evidence": [], "other_faults": ["port_blocked"]})
    assert both.correct and both.complete
    wrong = score(s, {"verdict": "fault", "fault_type": "route_failure", "evidence": []})
    assert not wrong.correct and not wrong.complete
    extra = score(s, {"verdict": "fault", "fault_type": "dns_failure", "evidence": [], "other_faults": ["route_failure"]})
    assert not extra.complete


def test_single_fault_complete_equals_correct():
    s = get_scenario("route_failure")
    assert score(s, {"verdict": "fault", "fault_type": "route_failure", "evidence": []}).complete


# ---- campus (bigger network) --------------------------------------------------------------------
def test_campus_has_more_nodes_and_two_router_hops():
    n = SimNetwork(get_scenario("campus_healthy"))
    assert n.ping("h1", "db.lab").ok and n.ping("h1", "10.0.7.10").ok
    assert n.port_check("h1", "db.lab", 5432).ok and n.port_check("h1", "h4", 445).ok
    t = n.traceroute("h1", "web.lab")
    assert t.ok and "r1" in t.output and "r2" in t.output
    assert n.show_routes("r2").ok


def test_campus_faults_hit_only_the_ticket_target():
    r = SimNetwork(get_scenario("campus_route_failure"))
    assert not r.ping("h1", "web.lab").ok and r.ping("h1", "db.lab").ok
    t = r.traceroute("h1", "web.lab")
    assert not t.ok and "r1" in t.output
    p = SimNetwork(get_scenario("campus_port_blocked"))
    assert not p.port_check("h1", "web.lab", 80).ok and p.port_check("h1", "db.lab", 5432).ok
    d = SimNetwork(get_scenario("campus_dns_failure"))
    assert not d.dns_lookup("h1", "web.lab").ok and d.ping("h1", "10.0.2.10").ok


def test_campus_prompt_names_the_bigger_network_and_small_prompt_is_unchanged():
    from netwing.agent import _system_prompt
    assert "h3 (database db.lab)" in _system_prompt("plain", get_scenario("campus_healthy"))
    assert "hosts h1 and h2 and a router r1" in _system_prompt("plain", get_scenario("route_failure"))


def test_final_answer_schema_offers_other_faults_in_every_mode():
    from netwing.agent import TOOLS, _system_prompt
    fa = [t for t in TOOLS if t["name"] == "final_answer"][0]["input_schema"]["properties"]
    assert "other_faults" in fa
    for m in ("plain", "healthy_ok", "netwing"):
        assert "other_faults" in _system_prompt(m, get_scenario("route_failure"))
