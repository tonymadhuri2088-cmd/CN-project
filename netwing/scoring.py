"""Deterministic scoring against scenario ground truth (no LLM judge)."""
from __future__ import annotations

from dataclasses import dataclass

from .scenarios import Scenario

_VALID_FAULTS = {"dns_failure", "route_failure", "port_blocked", "high_latency", "packet_loss", "none"}


@dataclass(frozen=True)
class Score:
    """Deterministic outcome of one answer against ground truth (correct, false alarm, no answer, completeness strict and including suspected claims)."""
    correct: bool
    false_alarm: bool
    no_answer: bool
    complete: bool = False  # found every injected fault (single-fault scenarios: same as correct)
    inconclusive: bool = False  # the model honestly said the evidence is inconclusive (counted as no answer)
    complete_incl_suspected: bool = False  # like complete, but also counts claims flagged "suspected" (tiered claims)


def score(scenario: Scenario, answer: dict | None) -> Score:
    """Score an answer against the scenario's ground truth. No LLM judge; an `inconclusive` verdict counts as no answer, never as a false alarm."""
    if isinstance(answer, dict) and answer.get("verdict") == "inconclusive":
        return Score(correct=False, false_alarm=False, no_answer=True, inconclusive=True)
    if (
        not isinstance(answer, dict)
        or answer.get("verdict") not in ("fault", "healthy")
        or answer.get("fault_type") not in _VALID_FAULTS
    ):
        return Score(correct=False, false_alarm=False, no_answer=True)
    verdict, fault_type = answer["verdict"], answer["fault_type"]
    if scenario.truth == "healthy":
        correct = verdict == "healthy"
        return Score(correct=correct, false_alarm=verdict == "fault", no_answer=False, complete=correct,
                     complete_incl_suspected=correct)
    truths = {scenario.truth, *scenario.also}
    correct = verdict == "fault" and fault_type in truths
    claimed = {fault_type}
    other = answer.get("other_faults") or []
    if isinstance(other, list):
        claimed |= {f for f in other if f in _VALID_FAULTS and f != "none"}
    suspected = answer.get("suspected_faults") or []
    with_suspected = claimed | ({f for f in suspected if f in _VALID_FAULTS and f != "none"} if isinstance(suspected, list) else set())
    return Score(correct=correct, false_alarm=False, no_answer=False, complete=correct and claimed == truths,
                 complete_incl_suspected=correct and with_suspected == truths)
