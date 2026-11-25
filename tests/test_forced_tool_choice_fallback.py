from netwing.agent import run_diagnosis
from netwing.budget import CostGuard
from netwing.scenarios import get_scenario
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final, tool_use

PRICES = {"m": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}


class RejectForced(FakeClient):
    """Behaves like a model that rejects a forced tool_choice."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rejected = 0
        inner = self.messages.create

        def create(**kw):
            if kw.get("tool_choice") is not None:
                self.rejected += 1
                raise RuntimeError("tool_choice: type \"tool\" and \"any\" are not supported for this model")
            return inner(**kw)
        self.messages.create = create


def test_unsupported_forced_tool_choice_falls_back_and_run_completes():
    s = get_scenario("healthy_false_alarm")
    client = RejectForced([
        [tool_use("t1", "ping", src="h1", dst="h2")],
        [final("f1", "healthy", "none", ["E1"])],
    ])
    g = CostGuard(total_cap_usd=10.0, per_run_cap_usd=5.0, prices=PRICES)
    log = run_diagnosis(s, SimNetwork(s), "plain", client, g, "m", 1)
    assert log.status == "answered"
    assert client.rejected == 1
