"""Pure-Python simulated network. Every output ends with [SIMULATED].

Fault flags (Scenario.faults): dns, route (no route to the web server's subnet), port (web port filtered),
noise (red-herring alerts), blip (the first ping to the web server is lost), flaky_port (web port alternates
filtered/open), latency (ping to the web server averages 480 ms), loss (67% packet loss to the web server).
"""
from __future__ import annotations

from collections import Counter

from .backend import ToolResult
from .scenarios import Scenario

_TAG = "\n[SIMULATED]"
_DECOM = "decom"  # decommissioned host that only exists in noisy scenarios
_DECOM_IP = "10.0.3.10"
_WEB = "h2"
_WEB_PORT = 80


class SimNetwork:
    """Deterministic simulated network with injectable faults (DNS, route, port, noise, blip, flaky port, latency, loss); every output is tagged [SIMULATED]."""
    simulated = True

    def __init__(self, scenario: Scenario):
        self.s = scenario
        t = scenario.topology
        self.hosts = t["hosts"]
        self.dns = t["dns"]
        self.faults = scenario.faults
        self.routers = t.get("routers", [t["router"]])
        self.hops = t.get("hops", [t["router"]])
        self._calls: Counter[str] = Counter()

    # -- helpers ---------------------------------------------------------
    def _result(self, tool, args, text, ok, category, evidence=True):
        return ToolResult(tool=tool, args=args, output=text + _TAG, ok=ok, category=category, evidence=evidence)

    def _invalid(self, tool, args, what):
        return self._result(tool, args, f"error: {what}", False, "invalid")

    def _known(self, name):
        return name in self.hosts or name in self.routers

    def _target(self, name):
        """Resolve a ping/port target given as node name, IP or DNS name.

        Returns (node, dns_failed). node is None if the target is unknown.
        """
        if self._known(name):
            return name, False
        for node, ip in self.hosts.items():
            if name == ip:
                return node, False
        if "noise" in self.faults and name == _DECOM_IP:
            return _DECOM, False
        if name in self.dns:
            if "dns" in self.faults:
                return None, True
            for node, ip in self.hosts.items():
                if self.dns[name] == ip:
                    return node, False
        return None, False

    def _dns_fail(self, tool, args, name):
        return self._result(tool, args, f"{name}: Temporary failure in name resolution", False, "dns")

    def _no_route(self, node):
        """True when src cannot reach node: the web server's subnet has no route, or the host is gone."""
        return node == _DECOM or ("route" in self.faults and node == _WEB)

    def _check_target(self, tool, args, src, dst):
        """Common src/dst validation. Returns (node, early_result)."""
        if not self._known(src):
            return None, self._invalid(tool, args, f"unknown host {src}")
        node, dns_failed = self._target(dst)
        if dns_failed:
            return None, self._dns_fail(tool, args, dst)
        if node is None:
            return None, self._invalid(tool, args, f"unknown host {dst}")
        return node, None

    # -- tools -----------------------------------------------------------
    def ping(self, src, dst):
        """ICMP check from src to dst; behaviour depends on the injected faults."""
        args = {"src": src, "dst": dst}
        node, early = self._check_target("ping", args, src, dst)
        if early:
            return early
        lost = self._no_route(node)
        if "blip" in self.faults and node == _WEB:
            self._calls["blip"] += 1
            lost = lost or self._calls["blip"] == 1  # only the first ping is lost
        if lost:
            return self._result("ping", args, f"{src} -> {dst}: 3 packets sent, 0 received, 100% loss", False, "connectivity")
        if node == _WEB and "loss" in self.faults:
            return self._result("ping", args, f"{src} -> {dst}: 3 packets sent, 1 received, 67% loss", False, "connectivity")
        if node == _WEB and "latency" in self.faults:
            return self._result("ping", args, f"{src} -> {dst}: 3 packets sent, 3 received, 0% loss, avg rtt 480 ms (normal: under 100 ms)", False, "connectivity")
        return self._result("ping", args, f"{src} -> {dst}: 3 packets sent, 3 received, 0% loss", True, "connectivity")

    def traceroute(self, src, dst):
        """Path check from src to dst; stops at the hop where a route fault breaks the path."""
        args = {"src": src, "dst": dst}
        node, early = self._check_target("traceroute", args, src, dst)
        if early:
            return early
        if node == _DECOM:
            return self._result("traceroute", args, "1  r1  0.4 ms\n2  * * *\n3  * * *", False, "connectivity")
        if "route" in self.faults and node == _WEB:
            text = f"1  {self.hops[0]}  0.4 ms\n2  * * *\n3  * * *  (no route beyond {self.hops[0]})"
            return self._result("traceroute", args, text, False, "connectivity")
        slow = 120 if ("latency" in self.faults and node == _WEB) else 1  # latency scenario: slow beyond the router
        lines = [f"{i}  {h}  {0.4 * i * (slow if i > 1 else 1):.1f} ms" for i, h in enumerate(self.hops, 1)]
        lines.append(f"{len(self.hops) + 1}  {dst}  {0.4 * (len(self.hops) + 1) * slow:.1f} ms")
        return self._result("traceroute", args, "\n".join(lines), True, "connectivity")

    def dns_lookup(self, src, name):
        """Resolve a name from src: SERVFAIL under a DNS fault, a timeout for the noise alert's printer.lab, NXDOMAIN for unknown names."""
        args = {"src": src, "name": name}
        if not self._known(src):
            return self._invalid("dns_lookup", args, f"unknown host {src}")
        if "noise" in self.faults and name == "printer.lab":
            return self._result("dns_lookup", args, f"{name}: connection timed out; no servers could be reached", False, "dns")
        if "dns" in self.faults:
            return self._result("dns_lookup", args, f"{name}: SERVFAIL (resolver did not answer)", False, "dns")
        if name in self.dns:
            return self._result("dns_lookup", args, f"{name} -> {self.dns[name]}", True, "dns")
        return self._result("dns_lookup", args, f"{name}: NXDOMAIN", False, "dns", evidence=name == "web.lab")

    def port_check(self, src, dst, port):
        """TCP connect from src to dst:port; filtered under a port fault, timed out under a route fault."""
        args = {"src": src, "dst": dst, "port": port}
        node, early = self._check_target("port_check", args, src, dst)
        if early:
            return early
        if not isinstance(port, int) or not 1 <= port <= 65535:
            return self._invalid("port_check", args, f"invalid port {port}")
        timed_out = self._result("port_check", args, f"{dst}:{port} timed out (host unreachable)", False, "port")
        filtered = self._result("port_check", args, f"{dst}:{port} filtered (no response, firewall drop)", False, "port")
        if self._no_route(node):
            return timed_out
        if "noise" in self.faults and (node, port) == (_WEB, 8080):
            return filtered
        if "port" in self.faults and (node, port) == (_WEB, _WEB_PORT):
            return filtered
        if "flaky_port" in self.faults and (node, port) == (_WEB, _WEB_PORT):
            self._calls["flaky"] += 1
            if self._calls["flaky"] % 2 == 1:  # fails on the 1st, 3rd, ... check
                return filtered
        if (node, port) in self.s.topology["services"]:
            return self._result("port_check", args, f"{dst}:{port} open", True, "port")
        return self._result("port_check", args, f"{dst}:{port} closed (connection refused)", False, "port", evidence=False)

    def show_routes(self, node):
        """Routing table of a node."""
        args = {"node": node}
        if not self._known(node):
            return self._invalid("show_routes", args, f"unknown node {node}")
        subnets = self.s.topology["subnets"]
        lines = []
        for i, (host, net) in enumerate(subnets.items()):
            if host == _WEB and "route" in self.faults and node != _WEB:
                continue  # every other node has lost its route to the web server's subnet
            lines.append(f"{net} dev eth{min(i, 1)} connected")
        return self._result("show_routes", args, "\n".join(lines), True, "routing")
