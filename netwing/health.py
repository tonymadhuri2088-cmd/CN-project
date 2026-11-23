"""Network health indicators computed ONLY from measured test results (no model involved).

Each indicator is ok / fail / mixed / not_measured. Indicators nobody measured are shown separately and
are never counted as healthy. The score is the share of measured indicators that are ok (mixed counts half).
"""
from __future__ import annotations

from typing import Any

INDICATORS = {
    "dns_resolution": "DNS resolution",
    "reachability": "Host reachability (ping)",
    "port_availability": "Port availability",
    "routing_path": "Routing / path (traceroute)",
    "gateway_reachability": "Gateway reachability",
}
_GATEWAYS = {"r1", "r2"}


def _state(oks: list[bool]) -> str:
    if not oks:
        return "not_measured"
    if all(oks):
        return "ok"
    if not any(oks):
        return "fail"
    return "mixed"


def compute_health(tests: list[dict]) -> dict:
    """Network health score from measured values only; indicators never measured are listed separately and never assumed healthy."""
    buckets: dict[str, list[bool]] = {k: [] for k in INDICATORS}
    for t in tests:
        tool, ok = t.get("tool"), bool(t.get("ok"))
        if t.get("evidence") is False:
            continue  # e.g. connection refused: the host answered, not a measurement of the indicator
        args = t.get("args") or {}
        if tool == "dns_lookup":
            buckets["dns_resolution"].append(ok)
        elif tool == "ping":
            buckets["reachability"].append(ok)
            if args.get("dst") in _GATEWAYS:
                buckets["gateway_reachability"].append(ok)
        elif tool == "port_check":
            buckets["port_availability"].append(ok)
        elif tool == "traceroute":
            buckets["routing_path"].append(ok)
    items: list[dict[str, Any]] = []
    for key, label in INDICATORS.items():
        oks = buckets[key]
        items.append({"key": key, "label": label, "state": _state(oks), "measurements": len(oks),
                      "failed": sum(1 for x in oks if not x)})
    measured = [i for i in items if i["state"] != "not_measured"]
    points = sum({"ok": 1.0, "mixed": 0.5, "fail": 0.0}[i["state"]] for i in measured)
    score = round(100 * points / len(measured)) if measured else None
    return {"score": score, "measured": len(measured), "total": len(items), "indicators": items}
