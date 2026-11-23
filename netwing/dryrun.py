"""Scripted stub client for --dry-run: exercises the whole pipeline with zero API calls.

It runs ping, dns_lookup, port_check in order, then reports what those showed.
Its numbers prove the plumbing works; they say nothing about real model behavior.
"""
from __future__ import annotations

import re
from types import SimpleNamespace as NS

_ORDER = [
    ("ping", {"src": "h1", "dst": "h2"}),
    ("dns_lookup", {"src": "h1", "name": "web.lab"}),
    ("port_check", {"src": "h1", "dst": "h2", "port": 80}),
]
_FAIL_WORDS = ("100% loss", "SERVFAIL", "NXDOMAIN", "filtered", "timed out", "refused", "no route")
_FAULT_FOR = {"ping": "route_failure", "dns_lookup": "dns_failure", "port_check": "port_blocked"}


def _observed(messages):
    names = {}
    seen = []  # (tool, evidence_id, failed)
    for m in messages:
        if not isinstance(m["content"], list):
            continue
        for b in m["content"]:
            if b.get("type") == "tool_use":
                names[b["id"]] = b["name"]
            elif b.get("type") == "tool_result" and not b.get("is_error"):
                text = b["content"]
                eid = re.match(r"\[(E\d+)\]", text)
                seen.append((names.get(b["tool_use_id"]), eid.group(1) if eid else None,
                             any(w in text for w in _FAIL_WORDS)))
    return seen


class DryRunClient:
    """Scripted stand-in for the model client so the whole pipeline runs with no API calls; its results prove the pipeline only."""
    def __init__(self):
        self.messages = NS(create=self._create)
        self._n = 0

    def _create(self, **kw):
        self._n += 1
        seen = _observed(kw["messages"])
        forced = kw.get("tool_choice") is not None
        failed_tools = [t for t, _, f in seen if f]
        if len(seen) < len(_ORDER) and not forced:
            tool, args = _ORDER[len(seen)]
            block = NS(type="tool_use", id=f"dry{self._n}", name=tool, input=dict(args))
        elif failed_tools and len(seen) == len(_ORDER) and not forced:
            tool = failed_tools[0]  # confirm the failure by repeating the same check once
            args = dict(dict(_ORDER)[tool])
            block = NS(type="tool_use", id=f"dry{self._n}", name=tool, input=args)
        else:
            failed = [(t, e) for t, e, f in seen if f]
            if failed:
                tool, eid = failed[0]
                ans = {"verdict": "fault", "fault_type": _FAULT_FOR[tool], "evidence": [eid]}
            else:
                ans = {"verdict": "healthy", "fault_type": "none", "evidence": [e for _, e, _ in seen]}
            block = NS(type="tool_use", id=f"dry{self._n}", name="final_answer", input=ans)
        return NS(content=[block], stop_reason="tool_use", usage=NS(input_tokens=100, output_tokens=50))
