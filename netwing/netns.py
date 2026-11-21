"""Real-network backend without Docker: the lab as Linux network namespaces (needs root + iproute2).

It builds the same topology as labs/base/lab.conf and runs the lab's own *.startup scripts, so the
kernel does the real routing, firewalling and DNS. Commands are the ones KatharaNetwork issues; this module
only translates `kathara exec -d LAB DEVICE -- CMD` into `ip netns exec DEVICE CMD`.
This checks the lab scripts and the output parsers against real tools. It does NOT test Kathara or its image.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import time

from .kathara import KatharaNetwork

DEVICES = ["h1", "r1", "h2", "dns"]
_BRIDGE = "nwbrA"
_NO_DNS_FLAG = "/etc/netwing-no-dns"
_BR_NF = "/proc/sys/net/bridge/bridge-nf-call-iptables"
_saved_br_nf: list[str] = []  # value to restore at teardown


def _bridge_firewall(disable: bool) -> None:
    """Hosts running Docker filter bridged traffic with a DROP policy, which would silently break the lab's
    own bridge. Turn that off while the lab exists, then put the old value back."""
    if not os.path.exists(_BR_NF):
        return
    if disable and not _saved_br_nf:
        _saved_br_nf.append(open(_BR_NF).read().strip())
        open(_BR_NF, "w").write("0")
    elif not disable and _saved_br_nf:
        open(_BR_NF, "w").write(_saved_br_nf.pop())


def available() -> tuple[bool, str]:
    """(usable, reason-if-not)."""
    if os.name != "posix" or not hasattr(os, "geteuid"):
        return False, "needs Linux"
    if os.geteuid() != 0:
        return False, "needs root (run with sudo)"
    for tool in ("ip", "dnsmasq", "nc", "dig", "ping", "traceroute", "iptables"):
        if shutil.which(tool) is None:
            return False, f"missing tool: {tool} (apt install iproute2 dnsmasq netcat-openbsd dnsutils iputils-ping traceroute iptables)"
    return True, ""


def _sh(*cmd, check=True):
    return subprocess.run(list(cmd), capture_output=True, text=True, check=check)


def _pids(ns: str) -> list[str]:
    return _sh("ip", "netns", "pids", ns, check=False).stdout.split()


def teardown() -> None:
    """Remove the lab completely. Startup scripts leave respawning loops behind, so kill until nothing is left
    and wait for the kernel to release the interfaces; a half-removed lab breaks the next build."""
    for d in DEVICES:
        for _ in range(20):
            pids = _pids(d)
            if not pids:
                break
            for pid in pids:
                _sh("kill", "-9", pid, check=False)
            time.sleep(0.1)
        _sh("ip", "netns", "del", d, check=False)
        shutil.rmtree(f"/etc/netns/{d}", ignore_errors=True)
    _sh("ip", "link", "del", _BRIDGE, check=False)
    for leftover in ("nwh1", "nwr1", "nwdns", "nwr1b"):
        _sh("ip", "link", "del", leftover, check=False)
    for _ in range(30):  # wait until the root-side veth ends are really gone
        links = _sh("ip", "-br", "link", check=False).stdout
        if not any(name in links for name in ("nwh1", "nwr1", "nwdns", "nwr1b", _BRIDGE)):
            break
        time.sleep(0.1)
    if os.path.exists(_NO_DNS_FLAG):
        os.remove(_NO_DNS_FLAG)
    _bridge_firewall(disable=False)


def build(lab_dir: str) -> None:
    """Create the namespaces and run each device's startup file from lab_dir."""
    teardown()
    _bridge_firewall(disable=True)
    for d in DEVICES:
        _sh("ip", "netns", "add", d)
        os.makedirs(f"/etc/netns/{d}", exist_ok=True)
        with open(f"/etc/netns/{d}/resolv.conf", "w") as f:
            f.write("")
        _sh("ip", "netns", "exec", d, "ip", "link", "set", "lo", "up")
    _sh("ip", "link", "add", _BRIDGE, "type", "bridge")
    _sh("ip", "link", "set", _BRIDGE, "up")
    for d in ("h1", "r1", "dns"):  # collision domain A
        _sh("ip", "link", "add", f"nw{d}", "type", "veth", "peer", "name", "eth0", "netns", d)
        _sh("ip", "link", "set", f"nw{d}", "master", _BRIDGE)
        _sh("ip", "link", "set", f"nw{d}", "up")
    _sh("ip", "link", "add", "nwr1b", "type", "veth", "peer", "name", "eth0", "netns", "h2")  # domain B
    _sh("ip", "link", "set", "nwr1b", "netns", "r1", "name", "eth1")
    for d, ifs in {"h1": ["eth0"], "r1": ["eth0", "eth1"], "h2": ["eth0"], "dns": ["eth0"]}.items():
        for i in ifs:
            _sh("ip", "netns", "exec", d, "ip", "link", "set", i, "up")
    for d in DEVICES:  # startup scripts may leave daemons behind, so detach them
        path = os.path.join(lab_dir, f"{d}.startup")
        if os.path.exists(path):
            subprocess.Popen(["ip", "netns", "exec", d, "bash", path], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(2.0)  # let dnsmasq and the nc listener come up


def runner(cmd: list[str], timeout: int) -> str:
    """Drop-in for kathara.default_runner: `kathara exec -d LAB DEV -- CMD...` -> `ip netns exec DEV CMD...`."""
    i = cmd.index("--")
    device, args = cmd[i - 1], cmd[i + 1:]
    p = subprocess.run(["ip", "netns", "exec", device, *args], capture_output=True, text=True, timeout=timeout)
    return (p.stdout or "") + (p.stderr or "")


class NetnsNetwork(KatharaNetwork):
    """KatharaNetwork running on real namespaces. Builds the scenario's lab on construction."""

    def __init__(self, scenario_id: str, labs_root: str = "labs"):
        ok, why = available()
        if not ok:
            raise RuntimeError(f"netns backend unavailable: {why}")
        subprocess.run(["bash", os.path.join(labs_root, "inject.sh"), scenario_id], check=True, capture_output=True)
        lab_dir = os.path.join(labs_root, scenario_id)
        build(lab_dir)
        atexit.register(teardown)
        super().__init__(lab_dir, runner)
