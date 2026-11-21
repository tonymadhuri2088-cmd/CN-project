"""Block shapes the real Anthropic API returns that the first fake client did not."""
from types import SimpleNamespace as NS

from netwing.agent import run_diagnosis
from netwing.budget import CostGuard
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, tool_use

PRICES = {"m": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}


def thinking(sig="sig123"):
    return NS(type="thinking", thinking="let me check connectivity first", signature=sig)


def run(script, mode="plain"):
    client = FakeClient(script)
    s = get_scenario("healthy_false_alarm")
    g = CostGuard(10.0, 5.0, PRICES)
    return run_diagnosis(s, SimNetwork(s), mode, client, g, "m", 8), client


def test_thinking_block_does_not_crash_and_is_passed_back_unchanged():
    log, client = run([
        [thinking(), tool_use("a", "ping", src="h1", dst="h2")],
        [final("f", "healthy", "none", ["E1"])],
    ])
    assert log.status == "answered"
    sent = client.calls[1]["messages"][1]["content"]
    assert sent[0] == {"type": "thinking", "thinking": "let me check connectivity first", "signature": "sig123"}
    assert sent[1]["type"] == "tool_use"


def test_redacted_thinking_block_is_passed_back():
    red = NS(type="redacted_thinking", data="opaque")
    log, client = run([[red, tool_use("a", "ping", src="h1", dst="h2")], [final("f", "healthy", "none", ["E1"])]])
    assert log.status == "answered"
    assert client.calls[1]["messages"][1]["content"][0] == {"type": "redacted_thinking", "data": "opaque"}


def test_unknown_block_types_are_ignored_not_fatal():
    log, _ = run([[NS(type="mystery_future_block"), final("f", "healthy", "none", [])]])
    assert log.status == "answered"


def test_max_tokens_leaves_room_for_thinking():
    _, client = run([[final("f", "healthy", "none", [])]])
    assert client.calls[0]["max_tokens"] >= 4096
