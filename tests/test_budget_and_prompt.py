from netwing.agent import _system_prompt
from netwing.backend import ToolResult
from netwing.controller import Controller
from netwing.runner import MAX_TESTS
from netwing.scenarios import get_scenario


def R(tool, ok, cat, **args):
    return ToolResult(tool=tool, args=args, output="x", ok=ok, category=cat)


def test_netwing_gets_the_same_test_budget_as_the_baselines():
    assert MAX_TESTS["netwing"] == MAX_TESTS["plain"] == MAX_TESTS["healthy_ok"]


def test_netwing_prompt_tells_the_model_to_confirm_failures_by_repeating_the_check():
    p = _system_prompt("netwing", get_scenario("transient_blip"))
    assert "same check" in p and "ping, DNS and port" in p
    assert "same check" not in _system_prompt("plain", get_scenario("transient_blip"))


def test_evidence_given_as_one_long_string_cites_every_id_in_it():
    c = Controller()
    c.observe(R("ping", True, "connectivity", src="h1", dst="web.lab"))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("port_check", False, "port", src="h1", dst="web.lab", port=80))
    c.observe(R("dns_lookup", True, "dns", src="h1", name="web.lab"))
    text = "[E1] ping fine. [E2] port 80 filtered from h1. [E3] filtered again."
    ok, why = c.allow_claim("fault", "port_blocked", [text])
    assert ok, why


def test_inventory_line_names_the_servers_other_names_in_every_mode_and_is_off_by_default():
    s = get_scenario("multi_dns_port")
    for mode in ("plain", "healthy_ok", "netwing"):
        p = _system_prompt(mode, s, inventory=True)
        assert "10.0.2.10" in p and "h2" in p and "same server" in p
        assert "10.0.2.10" not in _system_prompt(mode, s)


def test_inventory_flag_reaches_the_model_and_the_cli(tmp_path):
    from netwing.agent import run_diagnosis
    from netwing.demo import main
    from netwing.sim import SimNetwork
    from tests.fake_client import FakeClient, final
    from tests.test_agent import guard
    s = get_scenario("healthy_false_alarm")
    c = FakeClient([[final("f", "healthy", "none", [])]])
    run_diagnosis(s, SimNetwork(s), "plain", c, guard(), "m", 12, inventory=True)
    assert "same server" in c.calls[0]["system"]
    assert main(["--backend", "sim", "--dry-run", "--repeats", "1", "--inventory", "--out", str(tmp_path / "o.jsonl")]) == 0


def test_masked_area_rejection_does_not_point_at_unrelated_nodes():
    c = Controller()
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))
    c.observe(R("dns_lookup", False, "dns", src="h1", name="web.lab"))
    ok, why = c.allow_claim("fault", "dns_failure", ["E1"])
    assert not ok and "(h2, r1)" not in why and "server" in why


def test_inventory_is_on_by_default_in_the_cli_and_can_be_turned_off():
    from netwing.demo import build_parser
    assert build_parser().parse_args([]).inventory is True
    assert build_parser().parse_args(["--no-inventory"]).inventory is False
    assert build_parser().parse_args(["--inventory"]).inventory is True
