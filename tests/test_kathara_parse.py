import subprocess

from netwing.kathara import KatharaNetwork, build_exec_cmd, parse_dns, parse_ping, parse_port

PING_OK = """PING 10.0.2.10 (10.0.2.10) 56(84) bytes of data.
64 bytes from 10.0.2.10: icmp_seq=1 ttl=63 time=0.512 ms
--- 10.0.2.10 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms"""
PING_LOST = """PING 10.0.2.10 (10.0.2.10) 56(84) bytes of data.
--- 10.0.2.10 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2050ms"""
PING_UNREACH = """PING 10.0.2.10 (10.0.2.10) 56(84) bytes of data.
From 10.0.1.1 icmp_seq=1 Destination Net Unreachable
3 packets transmitted, 0 received, +3 errors, 100% packet loss, time 2003ms"""

DIG_OK = """;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
;; flags: qr aa rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1
;; ANSWER SECTION:
web.lab.  0 IN A 10.0.2.10"""
DIG_SERVFAIL = ";; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 2"
DIG_NXDOMAIN = ";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 3"
DIG_TIMEOUT = ";; connection timed out; no servers could be reached"
DIG_EMPTY = ";; ->>HEADER<<- opcode: QUERY, status: NOERROR\n;; flags: qr; QUERY: 1, ANSWER: 0, AUTHORITY: 0"
NSLOOKUP_OK = "Server: 10.0.2.53\nAddress: 10.0.2.53#53\n\nName: web.lab\nAddress: 10.0.2.10"
NSLOOKUP_FAIL = "** server can't find web.lab: NXDOMAIN"


def test_parse_ping():
    assert parse_ping(PING_OK) is True
    assert parse_ping(PING_LOST) is False
    assert parse_ping(PING_UNREACH) is False
    assert parse_ping("") is False


def test_parse_dns():
    assert parse_dns(DIG_OK) is True
    assert parse_dns(NSLOOKUP_OK) is True
    for bad in (DIG_SERVFAIL, DIG_NXDOMAIN, DIG_TIMEOUT, DIG_EMPTY, NSLOOKUP_FAIL, ""):
        assert parse_dns(bad) is False


def test_parse_port():
    assert parse_port("rc=0") is True
    assert parse_port("Connection to 10.0.2.10 80 port [tcp/http] succeeded!\nrc=0") is True
    assert parse_port("nc: connect to 10.0.2.10 port 80 (tcp) timed out\nrc=1") is False
    assert parse_port("nc: connect to 10.0.2.10 port 80 (tcp) failed: Connection refused\nrc=1") is False
    assert parse_port("") is False


def test_build_exec_cmd():
    cmd = build_exec_cmd("/labs/dns_failure", "h1", "ping -c 3 10.0.2.10")
    assert cmd == ["kathara", "exec", "-d", "/labs/dns_failure", "h1", "--", "ping", "-c", "3", "10.0.2.10"]


def net(output="", raises=None):
    calls = []

    def runner(cmd, timeout):
        calls.append(cmd)
        if raises:
            raise raises
        return output

    return KatharaNetwork("/labs/x", runner=runner), calls


def test_ping_uses_runner_and_parses():
    n, calls = net(PING_OK)
    r = n.ping("h1", "h2")
    assert r.ok and r.category == "connectivity" and r.tool == "ping"
    assert calls[0][-4:] == ["ping", "-c", "3", "10.0.2.10"] or "10.0.2.10" in calls[0]
    assert not n.simulated


def test_ping_failure_parsed():
    n, _ = net(PING_LOST)
    assert not n.ping("h1", "h2").ok


def test_unknown_host_invalid_without_running_anything():
    n, calls = net(PING_OK)
    r = n.ping("h1", "nope")
    assert not r.ok and r.category == "invalid" and calls == []


def test_bad_port_invalid_without_running_anything():
    n, calls = net("rc=0")
    r = n.port_check("h1", "h2", 70000)
    assert r.category == "invalid" and calls == []


def test_command_timeout_is_a_failed_test_not_a_crash():
    n, _ = net(raises=subprocess.TimeoutExpired(cmd="x", timeout=1))
    r = n.ping("h1", "h2")
    assert not r.ok and r.category == "connectivity" and "timed out" in r.output


def test_missing_kathara_binary_is_a_clear_error():
    n, _ = net(raises=FileNotFoundError("kathara"))
    try:
        n.ping("h1", "h2")
    except RuntimeError as e:
        assert "kathara" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError")


def test_dns_and_port_and_routes():
    n, _ = net(DIG_OK)
    assert n.dns_lookup("h1", "web.lab").ok
    n, _ = net("rc=0")
    assert n.port_check("h1", "h2", 80).ok
    n, _ = net("10.0.1.0/24 dev eth0\n10.0.2.0/24 via 10.0.1.1")
    r = n.show_routes("h1")
    assert r.ok and r.category == "routing" and "10.0.2.0/24" in r.output
