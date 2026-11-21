import math

from netwing.runner import summarize, wilson
from netwing.agent import RunLog


def test_wilson_interval_known_values():
    lo, hi = wilson(0, 12)
    assert lo == 0 and 0.2 < hi < 0.29          # 0/12 -> [0, ~0.243]
    lo, hi = wilson(12, 12)
    assert hi == 1 and 0.7 < lo < 0.8
    lo, hi = wilson(5, 10)
    assert math.isclose(lo, 0.237, abs_tol=0.01) and math.isclose(hi, 0.763, abs_tol=0.01)
    assert wilson(0, 0) == (0.0, 1.0)


def _log(mode, sid, verdict, ft, tests=3, other=None):
    ans = {"verdict": verdict, "fault_type": ft, "evidence": []}
    if other:
        ans["other_faults"] = other
    return RunLog(scenario_id=sid, mode=mode, model="m", tests_run=tests, answer=ans, status="answered", cost_usd=0.001)


def test_summary_shows_intervals_and_all_faults_found_only_for_multi_runs():
    logs = [_log("plain", "multi_dns_port", "fault", "dns_failure", other=["port_blocked"]),
            _log("plain", "multi_dns_port", "fault", "dns_failure"),
            _log("netwing", "multi_dns_port", "fault", "dns_failure")]
    out = summarize(logs, simulated=True)
    assert "All faults found" in out
    plain = [l for l in out.splitlines() if l.startswith("| plain")][0]
    assert "100% [" in plain and "50% [" in plain       # correct 2/2 with CI, all-found 1/2 with CI
    easy = summarize([_log("plain", "route_failure", "fault", "route_failure")], simulated=True)
    assert "All faults found" not in easy


def test_summary_shows_tests_with_spread():
    out = summarize([_log("plain", "route_failure", "fault", "route_failure", tests=t) for t in (2, 4)], simulated=True)
    assert "3.0 ±" in out
