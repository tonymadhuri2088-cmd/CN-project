"""Backend interface shared by the simulator and the real Kathara lab."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

CATEGORIES = ("connectivity", "dns", "port", "routing", "invalid")


@dataclass(frozen=True)
class ToolResult:
    """One diagnostic tool outcome: the call, its output, whether it passed, its evidence category, and whether a failure counts as proof of a fault."""
    tool: str
    args: dict = field(default_factory=dict)
    output: str = ""
    ok: bool = True
    category: str = "connectivity"  # one of CATEGORIES
    evidence: bool = True  # False: ok=False but NOT proof of a fault (e.g. connection refused)


class NetworkBackend(Protocol):
    """Interface every network backend implements (simulator, Linux namespaces, Kathara).

    Methods `ping`, `traceroute`, `dns_lookup`, `port_check` and `show_routes` each return a `ToolResult` and never raise for an ordinary network failure.
    """
    simulated: bool

    def ping(self, src: str, dst: str) -> ToolResult: ...
    def traceroute(self, src: str, dst: str) -> ToolResult: ...
    def dns_lookup(self, src: str, name: str) -> ToolResult: ...
    def port_check(self, src: str, dst: str, port: int) -> ToolResult: ...
    def show_routes(self, node: str) -> ToolResult: ...
