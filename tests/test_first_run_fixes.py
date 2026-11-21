"""Deferred review minors that would hurt the first real run (M1, M2, M5)."""
import os
import shutil
import subprocess

import pytest

from netwing.agent import TOOLS
from netwing.demo import main

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_node_names_are_listed_in_every_tool_that_takes_one():
    by_name = {t["name"]: t["description"] for t in TOOLS}
    for name in ("ping", "traceroute", "dns_lookup", "port_check", "show_routes"):
        assert "h1, h2, r1" in by_name[name], name


def test_missing_kathara_binary_is_caught_before_any_api_spend(monkeypatch):
    monkeypatch.setattr("netwing.demo.shutil.which", lambda name: None)
    with pytest.raises(SystemExit) as e:
        main(["--backend", "kathara", "--dry-run", "--repeats", "1"])
    assert "kathara" in str(e.value).lower()


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_dns_failure_lab_never_starts_dnsmasq_instead_of_racing_to_kill_it():
    subprocess.run(["bash", os.path.join(ROOT, "labs", "inject.sh"), "dns_failure"], check=True, capture_output=True)
    lines = open(os.path.join(ROOT, "labs", "dns_failure", "dns.startup")).read().splitlines()
    assert lines[0] == "touch /etc/netwing-no-dns"
    base = open(os.path.join(ROOT, "labs", "base", "dns.startup")).read()
    assert "[ -e /etc/netwing-no-dns ] || dnsmasq" in base
    assert "pkill" not in "\n".join(lines)
