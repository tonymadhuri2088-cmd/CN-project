from netwing.kathara import KatharaNetwork

OK_PING = "3 packets transmitted, 3 received, 0% packet loss"


def net(out):
    seen = []

    def runner(cmd, timeout):
        seen.append(cmd)
        return out

    return KatharaNetwork("lab", runner), seen


def test_ping_by_dns_name_passes_the_name_to_the_real_resolver():
    n, seen = net(OK_PING)
    r = n.ping("h1", "web.lab")
    assert r.ok and r.category == "connectivity"
    assert seen[0][-1] == "web.lab"


def test_ping_by_ip_works():
    n, seen = net(OK_PING)
    assert n.ping("h1", "10.0.2.10").ok
    assert seen[0][-1] == "10.0.2.10"


def test_name_resolution_failure_is_dns_evidence_not_invalid():
    n, _ = net("ping: web.lab: Temporary failure in name resolution")
    r = n.ping("h1", "web.lab")
    assert not r.ok and r.category == "dns" and r.evidence
    n, _ = net("nc: getaddrinfo for host \"web.lab\" port 80: Name or service not known\nrc=1")
    r = n.port_check("h1", "web.lab", 80)
    assert not r.ok and r.category == "dns" and r.evidence


def test_traceroute_by_name_uses_resolved_ip_for_reached_check():
    n, _ = net("traceroute to web.lab (10.0.2.10)\n 1  10.0.1.1  0.4 ms\n 2  10.0.2.10  0.9 ms")
    assert n.traceroute("h1", "web.lab").ok


def test_unknown_target_is_invalid():
    n, seen = net("")
    assert n.ping("h1", "nowhere").category == "invalid" and not seen
    assert n.port_check("h1", "10.9.9.9", 80).category == "invalid"


def test_refused_for_an_unrelated_name_is_not_evidence_but_for_web_lab_it_is():
    out = ";; ->>HEADER<<- opcode: QUERY, status: REFUSED, id: 1"
    n, _ = net(out)
    r = n.dns_lookup("h1", "other.lab")
    assert not r.ok and r.category == "dns" and not r.evidence
    r = n.dns_lookup("h1", "web.lab")
    assert not r.ok and r.evidence
