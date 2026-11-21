"""Opt-in: the real Linux network must agree with the simulator on every tool, in every scenario.

Run (Linux, root, ~1.5 min):  sudo NETWING_REAL_LAB=1 python -m pytest tests/test_netns_parity.py -q
"""
import os

import pytest

from netwing import netns
from netwing.scenarios import ALL_IDS, get_scenario
from netwing.sim import SimNetwork

ok_, why = netns.available()
pytestmark = pytest.mark.skipif(
    os.environ.get("NETWING_REAL_LAB") != "1" or not ok_,
    reason=why or "set NETWING_REAL_LAB=1 to run the real-network check",
)

CALLS = [
    ("ping", ("h1", "web.lab")), ("ping", ("h1", "10.0.2.10")), ("traceroute", ("h1", "web.lab")),
    ("dns_lookup", ("h1", "web.lab")), ("dns_lookup", ("h1", "other.lab")),
    ("port_check", ("h1", "web.lab", 80)), ("port_check", ("h1", "10.0.2.10", 80)),
    ("port_check", ("h1", "h2", 8080)), ("show_routes", ("r1",)), ("show_routes", ("h1",)),
]


@pytest.mark.parametrize("sid", ALL_IDS)
def test_real_network_matches_simulator(sid):
    real = netns.NetnsNetwork(sid, "labs")
    sim = SimNetwork(get_scenario(sid))
    bad = []
    for tool, args in CALLS:
        r, s = getattr(real, tool)(*args), getattr(sim, tool)(*args)
        if (r.ok, r.category, r.evidence) != (s.ok, s.category, s.evidence):
            bad.append((tool, args, (r.ok, r.category, r.evidence), (s.ok, s.category, s.evidence), r.output[:120]))
    assert not bad, bad
