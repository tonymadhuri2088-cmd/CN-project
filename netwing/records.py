"""Turn a run log (one JSONL line) into an investigation record for the UI.

Nothing here calls a model or changes diagnosis behaviour. Newer logs carry a structured `tests` list;
older logs are rebuilt from the transcript, in which case pass/fail is parsed from the tool output text
and the record says so (`parsed_from_text`).
"""
from __future__ import annotations

import re

from .backend import ToolResult
from .controller import Controller

_FAIL_PAT = re.compile(
    r"servfail|nxdomain|did not answer|filtered|no route|unreachable|100% loss|timed? ?out|refused|closed|\* \* \*",
    re.I,
)
_ID = re.compile(r"^\[(E\d+)\]\s*")


def _parse_ok(tool: str, output: str) -> bool:
    if tool == "show_routes":
        return True  # a routing table listing is an observation, not a pass/fail check
    m = re.search(r"(\d+)% loss", output)
    if m:
        return int(m.group(1)) < 100
    return not _FAIL_PAT.search(output)


def _tests_from_transcript(transcript: list) -> list[dict]:
    uses: dict[str, dict] = {}
    order: list[str] = []
    out: list[dict] = []
    for msg in transcript:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for b in content:
            if b.get("type") == "tool_use" and b.get("name") != "final_answer":
                uses[b["id"]] = b
                order.append(b["id"])
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in uses and not b.get("is_error"):
                text = b.get("content") or ""
                m = _ID.match(text)
                eid = m.group(1) if m else f"E{len(out) + 1}"
                body = _ID.sub("", text).replace("\n[SIMULATED]", "").strip()
                u = uses[b["tool_use_id"]]
                out.append({"id": eid, "tool": u["name"], "args": u.get("input", {}), "output": body,
                            "ok": _parse_ok(u["name"], body), "category": None, "evidence": True, "ts": None})
    return out


def _ticket(transcript: list) -> str:
    for msg in transcript:
        if isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"]
    return ""


LEVEL_LABEL = {"confirmed": "Confirmed", "suspected": "Suspected", "inconclusive": "Inconclusive"}


def _assurance(run: dict, tests: list, ans: dict, ev: list) -> dict | None:
    """Confirmed / suspected / inconclusive, judged by replaying the recorded tests through the controller's
    own rules. Needs the recorded test categories, so older logs (rebuilt from text) are not assessed."""
    if any(t.get("category") is None for t in tests) or not tests:
        return None
    try:
        from .scenarios import get_scenario
        subject = get_scenario(run.get("scenario_id") or "").subject
    except Exception:  # unknown scenario id: judge without a subject filter
        subject = None
    ctrl = Controller(max_tests=max(12, len(tests)), subject=subject)
    for t in tests:
        ctrl.observe(ToolResult(t["tool"], dict(t.get("args") or {}), str(t.get("output", "")), bool(t["ok"]),
                                t["category"], t.get("evidence", True) is not False))
    level, reason = ctrl.assess(ans.get("verdict"), ans.get("fault_type"), ev)
    return {"level": level, "label": LEVEL_LABEL[level], "reason": reason}


def build_record(run: dict, run_id: str) -> dict:
    """Normalise one run log into the evidence-explorer record (structured tests, evidence ids, assurance level); older logs are rebuilt from the transcript."""
    structured = bool(run.get("tests"))
    tests = run["tests"] if structured else _tests_from_transcript(run.get("transcript", []))
    for t in tests:
        t["output"] = str(t.get("output", "")).replace("\n[SIMULATED]", "").strip()
        if t.get("ok") is None:
            t["ok"] = _parse_ok(t["tool"], t["output"])
    ans = run.get("answer") or {}
    ev = ans.get("evidence") or []
    ev = [ev] if isinstance(ev, str) else list(ev)
    return {
        "id": run_id,
        "scenario": run.get("scenario_id"),
        "mode": run.get("mode"),
        "model": run.get("model"),
        "ticket": _ticket(run.get("transcript", [])),
        "simulated": bool(run.get("simulated")),
        "status": run.get("status"),
        "tests_run": run.get("tests_run", len(tests)),
        "rejected_claims": run.get("rejected_claims", 0),
        "cost_usd": run.get("cost_usd", 0.0),
        "verdict": ans.get("verdict"),
        "fault_type": ans.get("fault_type"),
        "other_faults": list(ans.get("other_faults") or []),
        "claimed_evidence": ev,
        "score": run.get("score") or {},
        "tests": tests,
        "assurance": _assurance(run, tests, ans, ev) if structured else None,
        "parsed_from_text": not structured,
        "error": run.get("error"),
    }
