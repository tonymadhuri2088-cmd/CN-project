from netwing.agent import run_diagnosis
from netwing.backend import ToolResult
from netwing.controller import Controller, Verdict
from netwing.scenarios import ALL_IDS, HARD_IDS, TICKET, get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, tool_use
from tests.test_agent import guard


def test_hard_suite_has_four_noisy_scenarios_with_one_shared_ticket():
    assert set(HARD_IDS) == {"noisy_healthy", "noisy_dns_failure", "noisy_route_failure", "noisy_port_blocked"}
    tickets = {get_scenario(i).ticket for i in HARD_IDS}
    assert len(tickets) == 1  # the ticket must not reveal the truth
    t = tickets.pop()
    assert t != TICKET and "printer.lab" in t and "8080" in t and "10.0.3.10" in t
    assert get_scenario("noisy_healthy").truth == "healthy"
    assert not set(HARD_IDS) & set(ALL_IDS)  # default suite stays the easy four


def test_noise_failures_are_real_evidence_in_noisy_scenarios_only():
    n = SimNetwork(get_scenario("noisy_healthy"))
    p = n.port_check("h1", "h2", 8080)
    assert not p.ok and p.category == "port" and p.evidence
    d = n.dns_lookup("h1", "printer.lab")
    assert not d.ok and d.category == "dns" and d.evidence
    g = n.ping("h1", "10.0.3.10")
    assert not g.ok and g.category == "connectivity" and g.evidence
    easy = SimNetwork(get_scenario("healthy_false_alarm"))
    assert easy.port_check("h1", "h2", 8080).evidence is False
    assert easy.ping("h1", "10.0.3.10").category == "invalid"


def test_noisy_healthy_main_path_really_is_healthy():
    n = SimNetwork(get_scenario("noisy_healthy"))
    assert n.ping("h1", "web.lab").ok and n.port_check("h1", "web.lab", 80).ok
    assert n.dns_lookup("h1", "web.lab").ok


def R(tool, args, ok, cat):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


def subject_ctrl():
    return Controller(subject=get_scenario("noisy_healthy").subject)


def test_unrelated_failures_do_not_block_a_healthy_claim():
    c = subject_ctrl()
    c.observe(R("ping", {"src": "h1", "dst": "web.lab"}, True, "connectivity"))
    c.observe(R("dns_lookup", {"src": "h1", "name": "web.lab"}, True, "dns"))
    c.observe(R("port_check", {"src": "h1", "dst": "web.lab", "port": 80}, True, "port"))
    bad = c.observe(R("port_check", {"src": "h1", "dst": "h2", "port": 8080}, False, "port"))
    c.observe(R("dns_lookup", {"src": "h1", "name": "printer.lab"}, False, "dns"))
    c.observe(R("ping", {"src": "h1", "dst": "10.0.3.10"}, False, "connectivity"))
    assert c.decide() == Verdict.STOP_HEALTHY
    ok, why = c.allow_claim("healthy", "none", [])
    assert ok, why
    ok, _ = c.allow_claim("fault", "port_blocked", [bad])
    assert not ok


def test_failure_on_the_ticket_target_still_counts():
    c = subject_ctrl()
    e = c.observe(R("port_check", {"src": "h1", "dst": "web.lab", "port": 80}, False, "port"))
    c.observe(R("port_check", {"src": "h1", "dst": "web.lab", "port": 80}, False, "port"))
    c.observe(R("ping", {"src": "h1", "dst": "web.lab"}, True, "connectivity"))
    c.observe(R("dns_lookup", {"src": "h1", "name": "web.lab"}, True, "dns"))
    ok, _ = c.allow_claim("healthy", "none", [])
    assert not ok
    ok, why = c.allow_claim("fault", "port_blocked", [e])
    assert ok, why


def test_no_subject_means_everything_is_relevant_as_before():
    c = Controller()
    e = c.observe(R("port_check", {"src": "h1", "dst": "h2", "port": 8080}, False, "port"))
    c.observe(R("port_check", {"src": "h1", "dst": "h2", "port": 8080}, False, "port"))
    c.observe(R("ping", {"src": "h1", "dst": "h2"}, True, "connectivity"))
    c.observe(R("dns_lookup", {"src": "h1", "name": "web.lab"}, True, "dns"))
    assert c.allow_claim("fault", "port_blocked", [e])[0]


def test_agent_netwing_accepts_healthy_despite_red_herrings():
    s = get_scenario("noisy_healthy")
    script = [
        [tool_use("a", "ping", src="h1", dst="web.lab")],
        [tool_use("b", "dns_lookup", src="h1", name="web.lab")],
        [tool_use("c", "port_check", src="h1", dst="web.lab", port=80)],
        [tool_use("d", "port_check", src="h1", dst="h2", port=8080)],
        [final("f", "healthy", "none", ["E1", "E2", "E3"])],
    ]
    log = run_diagnosis(s, SimNetwork(s), "netwing", FakeClient(script), guard(), "m", 8)
    assert log.status == "answered" and log.answer["verdict"] == "healthy" and log.rejected_claims == 0


def test_demo_suite_flag_selects_hard_scenarios_in_dry_run(tmp_path, capsys):
    from netwing.demo import main
    rc = main(["--dry-run", "--suite", "hard", "--repeats", "1", "--out", str(tmp_path / "r.jsonl")])
    assert rc == 0
    ids = {__import__("json").loads(l)["scenario_id"] for l in open(tmp_path / "r.jsonl")}
    assert ids == set(HARD_IDS)


def test_demo_default_suite_is_still_the_easy_four(tmp_path):
    from netwing.demo import main
    main(["--dry-run", "--repeats", "1", "--out", str(tmp_path / "r.jsonl")])
    ids = {__import__("json").loads(l)["scenario_id"] for l in open(tmp_path / "r.jsonl")}
    assert ids == set(ALL_IDS)


def test_fault_claim_built_on_unrelated_alerts_is_told_why_and_pointed_to_healthy():
    from netwing.backend import ToolResult
    from netwing.controller import Controller
    from netwing.scenarios import Subject
    c = Controller(subject=Subject(names=frozenset({"web.lab", "10.0.2.10", "h2"}), ports=frozenset({80})))
    c.observe(ToolResult(tool="ping", args={"src": "h1", "dst": "web.lab"}, output="x", ok=True, category="connectivity"))
    c.observe(ToolResult(tool="dns_lookup", args={"src": "h1", "name": "web.lab"}, output="x", ok=True, category="dns"))
    c.observe(ToolResult(tool="port_check", args={"src": "h1", "dst": "web.lab", "port": 80}, output="x", ok=True, category="port"))
    c.observe(ToolResult(tool="dns_lookup", args={"src": "h1", "name": "printer.lab"}, output="x", ok=False, category="dns"))
    c.observe(ToolResult(tool="port_check", args={"src": "h1", "dst": "h2", "port": 8080}, output="x", ok=False, category="port"))
    ok, why = c.allow_claim("fault", "dns_failure", ["E4", "E5"])
    assert not ok
    assert "E4" in why and "E5" in why and "not about the ticket" in why and "answer healthy" in why
