"""The four demo scenarios. Topology: h1 -- r1 -- h2, DNS name web.lab -> h2."""
from __future__ import annotations

from dataclasses import dataclass, field

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
    id: str
    ticket: str
    truth: str  # dns_failure | route_failure | port_blocked | healthy
    topology: dict = field(default_factory=lambda: TOPOLOGY, compare=False)
    faults: frozenset = frozenset()
    subject: Subject = Subject()
    also: tuple = ()  # further injected faults (multi-fault scenarios)


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

_EXTRA = set(HARD_IDS) | set(FLAKY_IDS) | set(MULTI_IDS) | set(CAMPUS_IDS)
ALL_IDS = [i for i in _SCENARIOS if i not in _EXTRA]  # default suite: the easy four


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return _SCENARIOS[scenario_id]
    except KeyError:
        raise ValueError(f"unknown scenario {scenario_id!r}; known: {list(_SCENARIOS)}") from None
