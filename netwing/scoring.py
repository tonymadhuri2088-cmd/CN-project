"""Deterministic scoring against scenario ground truth (no LLM judge)."""
from __future__ import annotations

from dataclasses import dataclass

from .scenarios import Scenario

_VALID_FAULTS = {"dns_failure", "route_failure", "port_blocked", "high_latency", "packet_loss", "none"}


@dataclass(frozen=True)
class Score:
    correct: bool
    false_alarm: bool
    no_answer: bool
    complete: bool = False  # found every injected fault (single-fault scenarios: same as correct)


def score(scenario: Scenario, answer: dict | None) -> Score:
    if (
        not isinstance(answer, dict)
        or answer.get("verdict") not in ("fault", "healthy")
        or answer.get("fault_type") not in _VALID_FAULTS
    ):
        return Score(correct=False, false_alarm=False, no_answer=True)
    verdict, fault_type = answer["verdict"], answer["fault_type"]
    if scenario.truth == "healthy":
        correct = verdict == "healthy"
        return Score(correct=correct, false_alarm=verdict == "fault", no_answer=False, complete=correct)
    truths = {scenario.truth, *scenario.also}
    correct = verdict == "fault" and fault_type in truths
    claimed = {fault_type}
    other = answer.get("other_faults") or []
    if isinstance(other, list):
        claimed |= {f for f in other if f in _VALID_FAULTS and f != "none"}
    return Score(correct=correct, false_alarm=False, no_answer=False, complete=correct and claimed == truths)
