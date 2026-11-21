"""Real emulated-lab backend: runs commands inside Kathara devices (Linux + Docker)."""
from __future__ import annotations

import re
import shlex
import subprocess
from typing import Callable

from .backend import ToolResult

IPS = {"h1": "10.0.1.10", "h2": "10.0.2.10", "r1": "10.0.1.1"}
NAMES = {"web.lab": "10.0.2.10"}
_RESOLVE_FAIL = ("Temporary failure in name resolution", "Name or service not known", "Unknown host", "unknown host",
                 "getaddrinfo", "lookup failed")
EXEC_TIMEOUT_S = 20


def build_exec_cmd(lab_dir: str, device: str, command: str) -> list[str]:
    return ["kathara", "exec", "-d", lab_dir, device, "--"] + shlex.split(command)


def default_runner(cmd: list[str], timeout: int) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return (p.stdout or "") + (p.stderr or "")


def parse_ping(text: str) -> bool:
    if "100% packet loss" in text or "Unreachable" in text:
        return False
    m = re.search(r"(\d+) received", text)
    return bool(m and int(m.group(1)) > 0)


def parse_dns(text: str) -> bool:
    if any(w in text for w in ("SERVFAIL", "NXDOMAIN", "REFUSED", "no servers could be reached", "timed out", "can't find")):
        return False
    m = re.search(r"ANSWER: (\d+)", text)
    if "status: NOERROR" in text and m:
        return int(m.group(1)) >= 1
    return bool(re.search(r"^Name:.*\n^Address:", text, re.M))


def parse_port(text: str) -> bool:
    if "refused" in text or "timed out" in text:
        return False
    return "rc=0" in text or "succeeded" in text or " open" in text


def _reached(text: str, ip: str) -> bool:
    hops = [l for l in text.splitlines() if re.match(r"\s*\d+\s", l)]
    return bool(hops) and ip in hops[-1] and "* * *" not in hops[-1]


class KatharaNetwork:
    simulated = False

    def __init__(self, lab_dir: str, runner: Callable[[list[str], int], str] = default_runner):
        self.lab_dir = lab_dir
        self._run = runner

    def _known(self, name: str) -> bool:
        return name in IPS

    def _dst(self, dst):
        """Return (what to pass to the command, resolved IP) or None if dst is not a valid target."""
        if dst in IPS:
            return IPS[dst], IPS[dst]
        if dst in IPS.values():
            return dst, dst
        if dst in NAMES:
            return dst, NAMES[dst]  # a name is passed through so the lab's own resolver is exercised
        return None

    @staticmethod
    def _resolve_failed(out):
        return any(w in out for w in _RESOLVE_FAIL)

    def _invalid(self, tool, args, what):
        return ToolResult(tool, args, f"error: {what}", False, "invalid")

    def _exec(self, device: str, command: str) -> tuple[str, bool]:
        """Returns (output, timed_out)."""
        try:
            return self._run(build_exec_cmd(self.lab_dir, device, command), EXEC_TIMEOUT_S), False
        except subprocess.TimeoutExpired:
            return "command timed out", True
        except FileNotFoundError as e:
            raise RuntimeError(
                "the 'kathara' command was not found; install Kathara and Docker (see SETUP_LINUX.md)"
            ) from e

    def ping(self, src, dst):
        args = {"src": src, "dst": dst}
        if not self._known(src):
            return self._invalid("ping", args, f"unknown host {src}")
        t = self._dst(dst)
        if t is None:
            return self._invalid("ping", args, f"unknown host {dst}")
        out, timed_out = self._exec(src, f"ping -c 3 -W 2 {t[0]}")
        if self._resolve_failed(out):
            return ToolResult("ping", args, out, False, "dns")
        return ToolResult("ping", args, out, (not timed_out) and parse_ping(out), "connectivity")

    def traceroute(self, src, dst):
        args = {"src": src, "dst": dst}
        if not self._known(src):
            return self._invalid("traceroute", args, f"unknown host {src}")
        t = self._dst(dst)
        if t is None:
            return self._invalid("traceroute", args, f"unknown host {dst}")
        out, timed_out = self._exec(src, f"traceroute -n -w 2 -m 6 {t[0]}")
        if self._resolve_failed(out):
            return ToolResult("traceroute", args, out, False, "dns")
        return ToolResult("traceroute", args, out, (not timed_out) and _reached(out, t[1]), "connectivity")

    def dns_lookup(self, src, name):
        args = {"src": src, "name": name}
        if not self._known(src):
            return self._invalid("dns_lookup", args, f"unknown host {src}")
        out, timed_out = self._exec(src, f"dig +time=2 +tries=1 {name}")
        unasked = ("NXDOMAIN" in out or "REFUSED" in out) and name != "web.lab"  # a missing unrelated name proves nothing
        return ToolResult("dns_lookup", args, out, (not timed_out) and parse_dns(out), "dns", evidence=not unasked)

    def port_check(self, src, dst, port):
        args = {"src": src, "dst": dst, "port": port}
        if not self._known(src):
            return self._invalid("port_check", args, f"unknown host {src}")
        t = self._dst(dst)
        if t is None:
            return self._invalid("port_check", args, f"unknown host {dst}")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            return self._invalid("port_check", args, f"invalid port {port}")
        out, timed_out = self._exec(src, f"sh -c 'nc -vz -w 3 {t[0]} {port}; echo rc=$?'")
        if self._resolve_failed(out):
            return ToolResult("port_check", args, out, False, "dns")
        refused = "refused" in out  # a closed port proves the host is reachable, not that a fault exists
        return ToolResult("port_check", args, out, (not timed_out) and parse_port(out), "port", evidence=not refused)

    def show_routes(self, node):
        args = {"node": node}
        if not self._known(node):
            return self._invalid("show_routes", args, f"unknown node {node}")
        out, _ = self._exec(node, "ip route")
        return ToolResult("show_routes", args, out, True, "routing")
