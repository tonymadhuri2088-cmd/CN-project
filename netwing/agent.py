"""LLM diagnosis agent: one tool-use loop shared by three modes.

plain       baseline prompt: "diagnose the reported problem"
healthy_ok  same, plus "the network may be healthy" (the strong prompt-only baseline)
netwing     healthy_ok prompt + the evidence Controller gating claims and stopping
"""
from __future__ import annotations

import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any

from .backend import NetworkBackend, ToolResult
from .budget import BudgetExceeded, CostGuard
from .controller import Controller, Verdict
from .scenarios import Scenario

MODES = ("plain", "healthy_ok", "netwing")
MAX_REJECTIONS = 3
MAX_NUDGES = 2
MAX_TOKENS = 4096  # thinking tokens count against this, so leave room

_BASE = (
    "You are a network troubleshooting agent for a small lab network with hosts h1 and h2 "
    "and a router r1; the web server is named web.lab. Investigate the ticket with the "
    "tools, then call final_answer exactly once. If the network has more than one independent fault, "
    "name the main one in fault_type and list the others in other_faults."
)
_PROMPTS = {
    "plain": _BASE + " Diagnose the problem described in the ticket.",
    "healthy_ok": _BASE
    + " Diagnose the problem described in the ticket. The network may actually be healthy; "
    "if your tests show no problem, answer verdict=healthy and fault_type=none.",
    "netwing": _BASE
    + " Diagnose the problem described in the ticket. The network may actually be healthy; "
    "if your tests show no problem, answer verdict=healthy and fault_type=none. "
    "Each tool result starts with an evidence id like [E1]; cite the ids that support your "
    "answer in final_answer. A fault claim must cite a failing result. Confirm a failure by "
    "running the same check again: a failure that does not repeat was a transient blip. Before "
    "answering, make sure you have tried ping, DNS and port checks.",
}


_SMALL = "hosts h1 and h2 and a router r1"


_INCONCLUSIVE_NOTE = (
    " If after testing the evidence is genuinely conflicting or insufficient, you may answer verdict=inconclusive "
    "with fault_type=none; never guess a fault to avoid it."
)


def _system_prompt(mode: str, scenario: Scenario, inventory: bool = False, allow_inconclusive: bool = False) -> str:
    blurb = scenario.topology.get("blurb")
    p = _PROMPTS[mode].replace(_SMALL, blurb, 1) if blurb else _PROMPTS[mode]
    if inventory and scenario.subject is not None:
        # An engineer has the network inventory; it is given to every mode alike so the comparison stays fair.
        names = ", ".join(sorted(scenario.subject.names))
        p += f" Inventory: the names {names} all refer to the same server."
    if getattr(scenario, "extended", False):
        p += " Faults can also be high_latency (reachable but very slow) or packet_loss (some packets are dropped)."
    if allow_inconclusive:
        p += _INCONCLUSIVE_NOTE
    return p


def _tool(name, desc, props, required):
    return {
        "name": name,
        "description": desc,
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


_S = {"type": "string"}
_NODES = " Source nodes: h1, h2, r1 (and any other host or router in the network). Targets may be a node name, an IP address or a DNS name."
TOOLS = [
    _tool("ping", "Ping dst from src." + _NODES, {"src": _S, "dst": _S}, ["src", "dst"]),
    _tool("traceroute", "Traceroute from src to dst." + _NODES, {"src": _S, "dst": _S}, ["src", "dst"]),
    _tool("dns_lookup", "Resolve a DNS name (for example web.lab) from src." + _NODES, {"src": _S, "name": _S}, ["src", "name"]),
    _tool(
        "port_check",
        "Check whether a TCP port on dst is reachable from src." + _NODES,
        {"src": _S, "dst": _S, "port": {"type": "integer"}},
        ["src", "dst", "port"],
    ),
    _tool("show_routes", "Show the routing table of a node." + _NODES, {"node": _S}, ["node"]),
    _tool(
        "final_answer",
        "Give the final diagnosis. Call exactly once.",
        {
            "verdict": {"type": "string", "enum": ["fault", "healthy"]},
            "fault_type": {
                "type": "string",
                "enum": ["dns_failure", "route_failure", "port_blocked", "none"],
            },
            "evidence": {"type": "array", "items": _S},
            "other_faults": {
                "type": "array",
                "items": {"type": "string", "enum": ["dns_failure", "route_failure", "port_blocked"]},
                "description": "Only if you found more than one independent fault: the additional fault types.",
            },
        },
        ["verdict", "fault_type", "evidence"],
    ),
]
_EXT_FAULTS = ["high_latency", "packet_loss"]


def _tools_for(scenario: Scenario, allow_inconclusive: bool = False) -> list:
    """The standard tool list. Lab scenarios also allow high_latency and packet_loss in the final answer;
    allow_inconclusive (opt-in) adds an 'inconclusive' verdict."""
    extended = getattr(scenario, "extended", False)
    if not extended and not allow_inconclusive:
        return TOOLS
    import copy

    tools = copy.deepcopy(TOOLS)
    props = tools[-1]["input_schema"]["properties"]
    if extended:
        props["fault_type"]["enum"] = props["fault_type"]["enum"][:-1] + _EXT_FAULTS + ["none"]
        props["other_faults"]["items"]["enum"] = props["other_faults"]["items"]["enum"] + _EXT_FAULTS
    if allow_inconclusive:
        props["verdict"]["enum"] = props["verdict"]["enum"] + ["inconclusive"]
    return tools


_BACKEND_TOOLS = {"ping", "traceroute", "dns_lookup", "port_check", "show_routes"}
FORCED = {"type": "tool", "name": "final_answer"}
FORCE_TEXT = "You have enough information. Give your final answer now with final_answer."


@dataclass
class RunLog:
    """Everything recorded about one diagnosis run: answer, status, cost, rejected claims, transcript, structured per-test records and claim reports."""
    scenario_id: str
    mode: str
    model: str
    tests_run: int = 0
    answer: dict | None = None
    status: str = "no_answer"  # answered | no_answer | budget | error
    cost_usd: float = 0.0
    rejected_claims: int = 0
    error: str | None = None
    transcript: list = field(default_factory=list)
    tests: list = field(default_factory=list)  # structured per-test record (additive; used by the UI layer only)
    claim_report: list = field(default_factory=list)  # per-claim verdicts when claim validation is on (else empty)
    error_kind: str = ""  # on status "error": api (network/API failure) | internal (programming bug) | other
    error_where: str = ""  # file:line of the failing frame, so a bug in this code is not mistaken for a model failure
    healthy_basis: str = ""  # why a "healthy" answer was allowed (rule or belief probability); empty for other answers

    def to_dict(self) -> dict:
        """Plain-dict form of the log, one JSON line per run in `results/`."""
        return asdict(self)


_INTERNAL_ERRORS = (AttributeError, AssertionError, NameError, TypeError, KeyError, IndexError, ImportError, ZeroDivisionError)


def _classify_error(exc: BaseException) -> tuple[str, str]:
    """('api'|'internal'|'other', 'file:line'). Broad catching is deliberate (a failed call must keep its cost and partial
    run), but the kind lets a later analysis exclude infrastructure failures and surface genuine bugs."""
    mod = type(exc).__module__.split(".")[0]
    kind = "api" if mod in ("anthropic", "httpx", "httpcore", "ssl") or isinstance(exc, OSError) else \
        "internal" if isinstance(exc, _INTERNAL_ERRORS) else "other"
    tb = traceback.extract_tb(exc.__traceback__)
    return kind, f"{tb[-1].filename.rsplit('/', 1)[-1]}:{tb[-1].lineno}" if tb else ""


def _execute(backend: NetworkBackend, name: str, args: dict) -> ToolResult:
    if name not in _BACKEND_TOOLS:
        return ToolResult(name, dict(args), f"error: unknown tool {name!r}", False, "invalid")
    try:
        return getattr(backend, name)(**args)
    except (TypeError, KeyError, ValueError) as e:
        return ToolResult(name, dict(args), f"error: invalid arguments ({e})", False, "invalid")


def _block_dict(b) -> dict | None:
    """Convert an API content block to a plain dict; None for block types we do not use.

    Thinking blocks must be sent back unchanged (with their signature) when the model
    thinks and uses tools in the same conversation, so they are kept verbatim.
    """
    t = b.type
    if t == "text":
        return {"type": "text", "text": b.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)}
    if t == "thinking":
        return {"type": "thinking", "thinking": b.thinking, "signature": b.signature}
    if t == "redacted_thinking":
        return {"type": "redacted_thinking", "data": b.data}
    return None


def run_diagnosis(
    scenario: Scenario,
    backend: NetworkBackend,
    mode: str,
    client,
    guard: CostGuard,
    model: str,
    max_tests: int,
    inventory: bool = False,
    allow_inconclusive: bool = False,
    guide_citations: bool = False,
    auto_cite: bool = False,
    healthy_strategy: str = "rules",
    belief_tau: float = 0.85,
    retest_hint: bool = False,
    resolver_hosts=None,
    validate_claims: bool = False,
    tier_claims: bool = False,
    mask_aware: bool = False,
    mask_reproduced: bool = False,
    cover_areas: bool = False,
) -> RunLog:
    """Run one agent diagnosis of a scenario against a backend and return its `RunLog`.

    The model chooses every tool call. In `netwing` mode the controller observes each result, forces a final answer once it
    decides to stop, and rejects unsupported claims (at most `MAX_REJECTIONS`, then the run ends with no answer). All modes share the
    same 12-test budget. Optional flags switch on the opt-in layers (citations, healthy strategy, claim validation and tiering).
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    guard.start_run()
    log = RunLog(scenario_id=scenario.id, mode=mode, model=model)
    ctrl = Controller(max_tests=max_tests, subject=scenario.subject, guide_citations=guide_citations, auto_cite=auto_cite,
                      healthy_strategy=healthy_strategy, belief_tau=belief_tau, resolver_hosts=resolver_hosts,
                      validate_claims=validate_claims, mask_aware=mask_aware, mask_reproduced=mask_reproduced,
                      cover_areas=cover_areas)  # ids + counting in every mode; gating only in netwing
    gated = mode == "netwing"
    messages: list[dict[str, Any]] = [{"role": "user", "content": scenario.ticket}]
    forced = False
    nudges = 0
    max_turns = max_tests + 6

    try:
        for _ in range(max_turns):
            kwargs = dict(model=model, max_tokens=MAX_TOKENS, system=_system_prompt(mode, scenario, inventory, allow_inconclusive), tools=_tools_for(scenario, allow_inconclusive), messages=messages)
            if forced:
                kwargs["tool_choice"] = FORCED
            resp = client.messages.create(**kwargs)
            try:
                usage = getattr(resp, "usage", None)
                guard.add_usage(
                    model,
                    getattr(usage, "input_tokens", None),
                    getattr(usage, "output_tokens", None),
                )
            except BudgetExceeded as e:
                log.status = "budget"
                log.transcript.append({"role": "system", "content": str(e)})
                break
            content = [d for d in (_block_dict(b) for b in resp.content) if d is not None]
            uses = [b for b in content if b["type"] == "tool_use"]

            if not uses:
                nudges += 1
                if nudges > MAX_NUDGES:
                    break
                if content:  # the API rejects an empty assistant message, so never send one back
                    messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Use the tools, then call final_answer."})
                continue
            messages.append({"role": "assistant", "content": content})

            results = []
            accepted = None
            rejected_now = False
            for u in uses:
                if u["name"] == "final_answer":
                    ans = u["input"]
                    ok, why = (True, "")
                    if gated:
                        ev = ans.get("evidence") or []
                        ev = [ev] if isinstance(ev, str) else list(ev)
                        ok, why = ctrl.allow_claim(ans.get("verdict"), ans.get("fault_type"), ev)
                    if ok:
                        accepted = ans
                        break
                    log.rejected_claims += 1
                    rejected_now = True
                    results.append(
                        {"type": "tool_result", "tool_use_id": u["id"], "content": why, "is_error": True}
                    )
                    continue
                if ctrl.tests_run >= max_tests:
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": u["id"],
                            "content": "Test limit reached; no more tests. Call final_answer now.",
                            "is_error": True,
                        }
                    )
                    continue
                res = _execute(backend, u["name"], u["input"])
                eid = ctrl.observe(res)
                log.tests.append({"id": eid, "tool": res.tool, "args": dict(res.args), "output": res.output,
                                  "ok": res.ok, "category": res.category, "evidence": res.evidence,
                                  "ts": time.time()})
                text = f"[{eid}] {res.output}"
                if retest_hint and gated:
                    text += ctrl.hint(res, eid)  # opt-in guidance; never changes a verdict
                if cover_areas and gated:
                    text += ctrl.cover_hint()  # opt-in: names areas with a failure seen once
                results.append({"type": "tool_result", "tool_use_id": u["id"], "content": text})

            if accepted is not None:
                if gated and validate_claims and accepted.get("verdict") == "fault":
                    raw = list(accepted.get("other_faults") or [])
                    kept, log.claim_report = ctrl.validate_other_faults(accepted.get("fault_type"), raw)
                    accepted = dict(accepted, other_faults=kept, other_faults_raw=raw)  # the raw claim stays auditable
                    if tier_claims:  # keep claims backed by a single sighting visible, flagged, and scored apart
                        accepted["suspected_faults"] = [x["fault_type"] for x in log.claim_report
                                                        if x["role"] == "secondary" and x["status"] == "suspected"]
                if gated and mask_reproduced and not validate_claims and accepted.get("verdict") == "fault":
                    raw = list(accepted.get("other_faults") or [])
                    kept, dropped = ctrl.drop_masked_secondary(raw)
                    if dropped:  # a masked secondary claim is removed, never silently: the raw claim stays auditable
                        accepted = dict(accepted, other_faults=kept, other_faults_raw=raw, dropped_masked=dropped)
                log.answer = accepted
                if gated and accepted.get("verdict") == "healthy":
                    log.healthy_basis = ctrl.healthy_basis
                log.status = "answered"
                break
            if log.rejected_claims >= MAX_REJECTIONS:
                break
            # Force a final answer at the test cap in EVERY mode; the evidence-based early stop is
            # netwing-only. After a rejected claim, release forcing so the model can still investigate.
            forced = False
            stop_now = ctrl.tests_run >= max_tests or (gated and ctrl.decide() != Verdict.CONTINUE)
            if stop_now and not rejected_now:
                forced = True
                results[-1]["content"] += "\n" + FORCE_TEXT
            messages.append({"role": "user", "content": results})
    except Exception as e:  # API/network/backend failure: keep the cost and the partial run
        log.status = "error"
        log.error = f"{type(e).__name__}: {e}"
        log.error_kind, log.error_where = _classify_error(e)

    log.tests_run = ctrl.tests_run
    log.cost_usd = guard.spent_run
    log.transcript = messages + log.transcript
    return log
