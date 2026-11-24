"""The four demo scenarios. Topology: h1 -- r1 -- h2, DNS name web.lab -> h2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TOPOLOGY = {
    "hosts": {"h1": "10.0.1.10", "h2": "10.0.2.10"},
    "router": "r1",
    "subnets": {"h1": "10.0.1.0/24", "h2": "10.0.2.0/24"},
    "dns": {"web.lab": "10.0.2.10"},
    "services": {("h2", 80): "http"},
}


# Identical for all scenarios on purpose: the ticket must never reveal the ground truth.
TICKET = "Users on h1 report they cannot reach the web server web.lab."


# Hard suite: the same ticket plus three red-herring alerts, identical for every hard scenario
# (healthy or faulty), so the ticket still never reveals the truth.
NOISY_TICKET = (
    TICKET + " Monitoring also shows: (a) DNS lookups for printer.lab time out; "
    "(b) TCP port 8080 on h2 is filtered; (c) 10.0.3.10 stopped answering ping "
    "(host decommissioned last week)."
)


@dataclass(frozen=True)
class Subject:
    """What the ticket is actually about; failures elsewhere are not evidence for it."""
    names: frozenset = frozenset({"web.lab", "10.0.2.10", "h2"})
    ports: frozenset = frozenset({80})


@dataclass(frozen=True)
class Scenario:
    """A ticket plus ground truth: the injected faults (`truth` and `also`), the network topology and the subject the controller treats as relevant."""
    id: str
    ticket: str
    truth: str  # dns_failure | route_failure | port_blocked | healthy
    topology: dict = field(default_factory=lambda: TOPOLOGY, compare=False)
    faults: frozenset = frozenset()
    subject: Subject = Subject()
    also: tuple = ()  # further injected faults (multi-fault scenarios)
    extended: bool = False  # lab scenarios: the answer may also be high_latency or packet_loss


_SCENARIOS = {
    "dns_failure": Scenario(
        id="dns_failure",
        ticket=TICKET,
        truth="dns_failure",
        faults=frozenset({"dns"}),
    ),
    "route_failure": Scenario(
        id="route_failure",
        ticket=TICKET,
        truth="route_failure",
        faults=frozenset({"route"}),
    ),
    "port_blocked": Scenario(
        id="port_blocked",
        ticket=TICKET,
        truth="port_blocked",
        faults=frozenset({"port"}),
    ),
    "healthy_false_alarm": Scenario(
        id="healthy_false_alarm",
        ticket=TICKET,
        truth="healthy",
        faults=frozenset(),
    ),
}

_HARD = {
    "noisy_healthy": ("healthy", frozenset({"noise"})),
    "noisy_dns_failure": ("dns_failure", frozenset({"noise", "dns"})),
    "noisy_route_failure": ("route_failure", frozenset({"noise", "route"})),
    "noisy_port_blocked": ("port_blocked", frozenset({"noise", "port"})),
}
for _id, (_truth, _faults) in _HARD.items():
    _SCENARIOS[_id] = Scenario(id=_id, ticket=NOISY_TICKET, truth=_truth, faults=_faults)

HARD_IDS = list(_HARD)

FLAKY_TICKET = "Users on h1 report intermittent problems reaching the web server web.lab."
_SCENARIOS["transient_blip"] = Scenario(
    id="transient_blip", ticket=FLAKY_TICKET, truth="healthy", faults=frozenset({"blip"}))
_SCENARIOS["intermittent_port"] = Scenario(
    id="intermittent_port", ticket=FLAKY_TICKET, truth="port_blocked", faults=frozenset({"flaky_port"}))
FLAKY_IDS = ["transient_blip", "intermittent_port"]

_SCENARIOS["multi_dns_port"] = Scenario(
    id="multi_dns_port", ticket=TICKET, truth="dns_failure", also=("port_blocked",), faults=frozenset({"dns", "port"}))
_SCENARIOS["multi_dns_route"] = Scenario(
    id="multi_dns_route", ticket=TICKET, truth="dns_failure", also=("route_failure",), faults=frozenset({"dns", "route"}))
MULTI_IDS = ["multi_dns_port", "multi_dns_route"]

# Bigger network: 4 hosts, 2 routers, 3 services. Same ticket and same fault semantics as the small one,
# but many more things to check and a two-hop path to localise a break on.
CAMPUS = {
    "hosts": {"h1": "10.0.1.10", "h2": "10.0.2.10", "h3": "10.0.6.10", "h4": "10.0.7.10"},
    "router": "r1",
    "routers": ["r1", "r2"],
    "subnets": {"h1": "10.0.1.0/24", "h2": "10.0.2.0/24", "h3": "10.0.6.0/24", "h4": "10.0.7.0/24"},
    "dns": {"web.lab": "10.0.2.10", "db.lab": "10.0.6.10", "files.lab": "10.0.7.10"},
    "services": {("h2", 80): "http", ("h3", 5432): "db", ("h4", 445): "smb"},
    "hops": ["r1", "r2"],
    "blurb": ("hosts h1 (clients), h2 (web server web.lab), h3 (database db.lab) and h4 (file server files.lab) "
              "and routers r1 and r2"),
}
_CAMPUS = {"campus_healthy": ("healthy", frozenset()), "campus_dns_failure": ("dns_failure", frozenset({"dns"})),
           "campus_route_failure": ("route_failure", frozenset({"route"})),
           "campus_port_blocked": ("port_blocked", frozenset({"port"}))}
for _id, (_truth, _faults) in _CAMPUS.items():
    _SCENARIOS[_id] = Scenario(id=_id, ticket=TICKET, truth=_truth, faults=_faults, topology=CAMPUS)
CAMPUS_IDS = list(_CAMPUS)

# Mini Project 2 lab scenarios (simulator only). Opt-in: the answer vocabulary is extended ONLY for these,
# so the experiment suites above keep exactly the same tools and prompts.
LAB_TICKET = "Users on h1 report that the web server h2 is down and want it restarted."
_SCENARIOS["lab_high_latency"] = Scenario(
    id="lab_high_latency", ticket=FLAKY_TICKET.replace("intermittent problems", "very slow responses"),
    truth="high_latency", faults=frozenset({"latency"}), extended=True)
_SCENARIOS["lab_packet_loss"] = Scenario(
    id="lab_packet_loss", ticket=FLAKY_TICKET, truth="packet_loss", faults=frozenset({"loss"}), extended=True)
_SCENARIOS["lab_misleading_dns"] = Scenario(
    id="lab_misleading_dns", ticket=LAB_TICKET, truth="dns_failure", faults=frozenset({"dns"}), extended=True)
_SCENARIOS["lab_misleading_healthy"] = Scenario(
    id="lab_misleading_healthy", ticket=LAB_TICKET, truth="healthy", faults=frozenset(), extended=True)
LAB_IDS = ["lab_high_latency", "lab_packet_loss", "lab_misleading_dns", "lab_misleading_healthy"]

# Held-out suite (simulator only). Combinations of conditions that no controller rule or prompt was tuned on:
# the noise alerts combined with blips, intermittent ports and double faults; a persistent fault behind the
# "intermittent" ticket; and the bigger campus network with noise and double faults. Protocol: run once on frozen
# code and report whatever comes out; never change a rule after looking at these results.
_HELDOUT = {
    "ho_noisy_blip": (NOISY_TICKET, "healthy", frozenset({"noise", "blip"}), (), None),
    "ho_noisy_flaky_port": (NOISY_TICKET, "port_blocked", frozenset({"noise", "flaky_port"}), (), None),
    "ho_noisy_multi_dns_port": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns", "port"}), ("port_blocked",), None),
    "ho_noisy_multi_dns_route": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns", "route"}), ("route_failure",), None),
    "ho_flaky_dns": (FLAKY_TICKET, "dns_failure", frozenset({"dns"}), (), None),
    "ho_campus_noisy_healthy": (NOISY_TICKET, "healthy", frozenset({"noise"}), (), CAMPUS),
    "ho_campus_noisy_route": (NOISY_TICKET, "route_failure", frozenset({"noise", "route"}), (), CAMPUS),
    "ho_campus_multi_dns_port": (TICKET, "dns_failure", frozenset({"dns", "port"}), ("port_blocked",), CAMPUS),
}
for _id, (_ticket, _truth, _faults, _also, _topo) in _HELDOUT.items():
    _kw: dict[str, Any] = {"topology": _topo} if _topo is not None else {}
    _SCENARIOS[_id] = Scenario(id=_id, ticket=_ticket, truth=_truth, faults=_faults, also=_also, **_kw)
HELDOUT_IDS = list(_HELDOUT)

# Fresh validation suite (simulator only), written BEFORE any strategy was run on it. New combinations, none of
# which appear in the held-out suite or the tuning suites: it exists to validate the opt-in healthy strategies,
# which were explored on the frozen held-out logs. Protocol: run once; no rule or threshold changes afterwards.
_FRESH = {
    "fx_blip": (TICKET, "healthy", frozenset({"blip"}), (), None),
    "fx_noisy_healthy": (NOISY_TICKET, "healthy", frozenset({"noise"}), (), None),
    "fx_campus_blip": (FLAKY_TICKET, "healthy", frozenset({"blip"}), (), CAMPUS),
    "fx_flaky_port": (FLAKY_TICKET, "port_blocked", frozenset({"flaky_port"}), (), None),
    "fx_noisy_dns": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns"}), (), None),
    "fx_noisy_route": (NOISY_TICKET, "route_failure", frozenset({"noise", "route"}), (), None),
    "fx_noisy_port": (NOISY_TICKET, "port_blocked", frozenset({"noise", "port"}), (), None),
    "fx_noisy_dns_flaky_port": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns", "flaky_port"}), ("port_blocked",), None),
}
for _id, (_ticket, _truth, _faults, _also, _topo) in _FRESH.items():
    _kw = {"topology": _topo} if _topo is not None else {}
    _SCENARIOS[_id] = Scenario(id=_id, ticket=_ticket, truth=_truth, faults=_faults, also=_also, **_kw)
FRESH_IDS = list(_FRESH)

# Second fresh suite (simulator only). FROZEN before the claim-level validation rule was written, and before any strategy
# was run on it. It targets what the first fresh suite missed: noise alerts together with a transient failure on a
# healthy network (the failure class that exposed the healthy no-answers), on both topologies; a noisy flaky port on the
# bigger network; noisy single faults on the bigger network (where an unsupported extra fault claim can appear); and a
# noisy double fault whose second fault IS supported (so a claim validator must keep it). fx2_noisy_blip repeats the
# held-out ho_noisy_blip definition on purpose (a replication of the failing class with fresh agent runs, not an
# independent scenario); the campus scenarios are new. Protocol: run once; no rule, flag or threshold changes afterwards.
_FRESH2 = {
    "fx2_noisy_blip": (NOISY_TICKET, "healthy", frozenset({"noise", "blip"}), (), None),
    "fx2_campus_noisy_blip": (NOISY_TICKET, "healthy", frozenset({"noise", "blip"}), (), CAMPUS),
    "fx2_campus_noisy_flaky_port": (NOISY_TICKET, "port_blocked", frozenset({"noise", "flaky_port"}), (), CAMPUS),
    "fx2_campus_noisy_dns": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns"}), (), CAMPUS),
    "fx2_campus_noisy_port": (NOISY_TICKET, "port_blocked", frozenset({"noise", "port"}), (), CAMPUS),
    "fx2_campus_noisy_route": (NOISY_TICKET, "route_failure", frozenset({"noise", "route"}), (), CAMPUS),
    "fx2_campus_noisy_multi_dns_port": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns", "port"}), ("port_blocked",), CAMPUS),
}
for _id, (_ticket, _truth, _faults, _also, _topo) in _FRESH2.items():
    _kw = {"topology": _topo} if _topo is not None else {}
    _SCENARIOS[_id] = Scenario(id=_id, ticket=_ticket, truth=_truth, faults=_faults, also=_also, **_kw)
FRESH2_IDS = list(_FRESH2)

# Third fresh suite (fresh3). FROZEN before the tiered-claims code was written or run. fresh2 showed that dropping every
# secondary claim without its own reproduced evidence loses real second faults (multi-fault exact 93% -> 13%). The
# tiered variant keeps such claims as "suspected" instead of dropping them, so fresh3 is multi-fault heavy (where recall
# matters) plus noisy single faults on both topologies (where unsupported extra claims appear) and one healthy
# transient-failure network (where nothing may be claimed). Every definition is checked against all earlier suites by tests/test_fresh3_suite.py: none repeats one.
# Protocol: run once; no rule, flag or threshold changes afterwards.
_FRESH3 = {
    "fx3_campus_multi_dns_route": (TICKET, "dns_failure", frozenset({"dns", "route"}), ("route_failure",), CAMPUS),
    "fx3_campus_noisy_multi_dns_route": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns", "route"}), ("route_failure",), CAMPUS),
    "fx3_campus_blip_multi_dns_port": (TICKET, "dns_failure", frozenset({"dns", "port", "blip"}), ("port_blocked",), CAMPUS),
    "fx3_campus_noisy_flaky_multi_dns_port": (NOISY_TICKET, "dns_failure", frozenset({"noise", "dns", "flaky_port"}), ("port_blocked",), CAMPUS),
    "fx3_campus_noisy_blip_port": (NOISY_TICKET, "port_blocked", frozenset({"noise", "port", "blip"}), (), CAMPUS),
    "fx3_blip_route": (TICKET, "route_failure", frozenset({"route", "blip"}), (), None),
    "fx3_campus_blip": (TICKET, "healthy", frozenset({"blip"}), (), CAMPUS),
}
for _id, (_ticket, _truth, _faults, _also, _topo) in _FRESH3.items():
    _kw = {"topology": _topo} if _topo is not None else {}
    _SCENARIOS[_id] = Scenario(id=_id, ticket=_ticket, truth=_truth, faults=_faults, also=_also, **_kw)
FRESH3_IDS = list(_FRESH3)

# fresh4 (simulator only): written BEFORE the masking-v2 evaluation, to test whether a reproduced-only route-masking rule
# avoids the blip over-masking seen in the first live run and does not harm route-only diagnosis. Frozen: run once.
_FRESH4 = {
    "fx4_blip_port": (TICKET, "port_blocked", frozenset({"port", "blip"}), (), None),
    "fx4_noisy_blip_port": (NOISY_TICKET, "port_blocked", frozenset({"noise", "port", "blip"}), (), None),
    "fx4_campus_blip_port": (TICKET, "port_blocked", frozenset({"port", "blip"}), (), CAMPUS),
    "fx4_flaky_route": (FLAKY_TICKET, "route_failure", frozenset({"route"}), (), None),
    "fx4_campus_flaky_route": (FLAKY_TICKET, "route_failure", frozenset({"route"}), (), CAMPUS),
    "fx4_noisy_blip_route": (NOISY_TICKET, "route_failure", frozenset({"noise", "route", "blip"}), (), None),
    "fx4_campus_noisy_blip_route": (NOISY_TICKET, "route_failure", frozenset({"noise", "route", "blip"}), (), CAMPUS),
}
for _id, (_ticket, _truth, _faults, _also, _topo) in _FRESH4.items():
    _kw = {"topology": _topo} if _topo is not None else {}
    _SCENARIOS[_id] = Scenario(id=_id, ticket=_ticket, truth=_truth, faults=_faults, also=_also, **_kw)
FRESH4_IDS = list(_FRESH4)

_EXTRA = set(LAB_IDS) | set(FRESH4_IDS) | set(FRESH3_IDS) | set(FRESH2_IDS) | set(FRESH_IDS) | set(HELDOUT_IDS) | set(HARD_IDS) | set(FLAKY_IDS) | set(MULTI_IDS) | set(CAMPUS_IDS)
ALL_IDS = [i for i in _SCENARIOS if i not in _EXTRA]  # default suite: the easy four


def get_scenario(scenario_id: str) -> Scenario:
    """Look up a scenario by id; raises ValueError for an unknown id."""
    try:
        return _SCENARIOS[scenario_id]
    except KeyError:
        raise ValueError(f"unknown scenario {scenario_id!r}; known: {list(_SCENARIOS)}") from None
