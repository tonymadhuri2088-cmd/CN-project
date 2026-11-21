import pytest

from netwing.agent import TOOLS, _system_prompt, _tools_for
from netwing.controller import Controller
from netwing.demo import _scenario_ids, build_parser, main
from netwing.scenarios import ALL_IDS, LAB_IDS, get_scenario
from netwing.scoring import score
from netwing.sim import SimNetwork


def test_lab_scenarios_have_ground_truth_and_are_extended():
    truths = {i: get_scenario(i).truth for i in LAB_IDS}
    assert truths == {"lab_high_latency": "high_latency", "lab_packet_loss": "packet_loss",
                      "lab_misleading_dns": "dns_failure", "lab_misleading_healthy": "healthy"}
    assert all(get_scenario(i).extended for i in LAB_IDS)


def test_existing_suites_are_unchanged_by_the_lab():
    assert not any(get_scenario(i).extended for i in ALL_IDS)
    assert _tools_for(get_scenario("dns_failure")) is TOOLS  # same object: no schema change for experiments
    assert "high_latency" not in str(_tools_for(get_scenario("noisy_healthy")))
    assert "high_latency" not in _system_prompt("netwing", get_scenario("noisy_healthy"), True)


def test_lab_tools_and_prompt_offer_new_fault_types_only_there():
    t = _tools_for(get_scenario("lab_high_latency"))
    props = t[-1]["input_schema"]["properties"]
    assert "high_latency" in props["fault_type"]["enum"] and "packet_loss" in props["other_faults"]["items"]["enum"]
    assert "high_latency" not in str(TOOLS)  # the shared list was not mutated
    assert "packet_loss" in _system_prompt("plain", get_scenario("lab_packet_loss"))


def test_sim_packet_loss_and_latency_are_measured_numbers():
    loss = SimNetwork(get_scenario("lab_packet_loss")).ping("h1", "h2")
    assert not loss.ok and "67% loss" in loss.output and "[SIMULATED]" in loss.output
    lat = SimNetwork(get_scenario("lab_high_latency")).ping("h1", "h2")
    assert not lat.ok and "480 ms" in lat.output
    tr = SimNetwork(get_scenario("lab_high_latency")).traceroute("h1", "h2")
    assert "ms" in tr.output and tr.ok
    healthy = SimNetwork(get_scenario("lab_misleading_healthy")).ping("h1", "h2")
    assert healthy.ok


def test_misleading_dns_scenario_has_dns_failure_behind_a_ticket_blaming_the_server():
    s = get_scenario("lab_misleading_dns")
    assert "down" in s.ticket and "dns" not in s.ticket.lower()
    assert not SimNetwork(s).dns_lookup("h1", "web.lab").ok
    assert SimNetwork(s).ping("h1", "h2").ok  # the server itself is up


def test_scoring_accepts_new_fault_types():
    s = get_scenario("lab_packet_loss")
    assert score(s, {"verdict": "fault", "fault_type": "packet_loss", "evidence": []}).correct
    assert not score(s, {"verdict": "fault", "fault_type": "route_failure", "evidence": []}).correct
    assert score(get_scenario("lab_misleading_healthy"), {"verdict": "fault", "fault_type": "dns_failure", "evidence": []}).false_alarm


def test_controller_gates_packet_loss_claim_on_confirmed_failure():
    net = SimNetwork(get_scenario("lab_packet_loss"))
    c = Controller(max_tests=12, subject=get_scenario("lab_packet_loss").subject)
    e1 = c.observe(net.ping("h1", "h2"))
    ok, why = c.allow_claim("fault", "packet_loss", [e1])
    assert not ok and "only been seen once" in why
    e2 = c.observe(net.ping("h1", "h2"))
    c.observe(net.dns_lookup("h1", "web.lab"))
    c.observe(net.port_check("h1", "h2", 80))
    assert c.allow_claim("fault", "packet_loss", [e1, e2])[0]


def test_lab_suite_selection_and_all_excludes_lab():
    a = build_parser().parse_args(["--suite", "lab"])
    assert _scenario_ids(a) == LAB_IDS
    assert not set(LAB_IDS) & set(_scenario_ids(build_parser().parse_args(["--suite", "all"])))


def test_lab_scenarios_refuse_real_backends():
    with pytest.raises(SystemExit, match="only in the simulator"):
        main(["--suite", "lab", "--backend", "netns"])
