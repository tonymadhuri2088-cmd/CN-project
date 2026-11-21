"""Backend interface shared by the simulator and the real Kathara lab."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

CATEGORIES = ("connectivity", "dns", "port", "routing", "invalid")


@dataclass(frozen=True)
class ToolResult:
    tool: str
    args: dict = field(default_factory=dict)
    output: str = ""
    ok: bool = True
    category: str = "connectivity"  # one of CATEGORIES
    evidence: bool = True  # False: ok=False but NOT proof of a fault (e.g. connection refused)


class NetworkBackend(Protocol):
    simulated: bool

    def ping(self, src: str, dst: str) -> ToolResult: ...
    def traceroute(self, src: str, dst: str) -> ToolResult: ...
    def dns_lookup(self, src: str, name: str) -> ToolResult: ...
    def port_check(self, src: str, dst: str, port: int) -> ToolResult: ...
    def show_routes(self, node: str) -> ToolResult: ...
