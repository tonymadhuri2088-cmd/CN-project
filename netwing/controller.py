"""NetWing: rule-based evidence-sufficiency controller.

It watches every tool result, decides when the agent has enough evidence to
stop, and refuses conclusions that the evidence does not support.
"""
from __future__ import annotations

import re
from enum import Enum

from .backend import ToolResult

_FAULT_CATEGORIES = {
    "dns_failure": {"dns"},
    "port_blocked": {"port"},
    "route_failure": {"connectivity", "routing"},
    "high_latency": {"connectivity"},  # lab scenarios only: the answer enum offers these only there
    "packet_loss": {"connectivity"},
}
_HEALTHY_NEEDS = {"connectivity", "dns", "port"}


class Verdict(Enum):
    CONTINUE = "continue"
    STOP_FAULT = "stop_fault"
    STOP_HEALTHY = "stop_healthy"
    STOP_CAP = "stop_cap"


_ID = re.compile(r"\bE\d+\b")


class Controller:
    def __init__(self, max_tests: int = 8, subject=None):
        self.max_tests = max_tests
        self.subject = subject  # None: every result is relevant
        self._results: dict[str, ToolResult] = {}
        self._order: list[str] = []

    @property
    def tests_run(self) -> int:
        return len(self._order)

    def observe(self, result: ToolResult) -> str:
        eid = f"E{len(self._order) + 1}"
        self._results[eid] = result
        self._order.append(eid)
        return eid

    # -- helpers ---------------------------------------------------------
    def _relevant(self, r: ToolResult) -> bool:
        """A result counts only if it concerns what the ticket is about."""
        s = self.subject
        if s is None:
            return True
        a = r.args
        if r.tool == "dns_lookup":
            return a.get("name") in s.names
        if r.tool in ("ping", "traceroute"):
            return a.get("dst") in s.names
        if r.tool == "port_check":
            return a.get("dst") in s.names and a.get("port") in s.ports
        return True

    def _valid(self) -> list[tuple[str, ToolResult]]:
        return [
            (e, self._results[e]) for e in self._order
            if self._results[e].category != "invalid" and self._results[e].evidence and self._relevant(self._results[e])
        ]

    @staticmethod
    def _key(r: ToolResult):
        return (r.tool, tuple(sorted((k, str(v)) for k, v in r.args.items())))

    def _failures(self) -> list[tuple[str, ToolResult]]:
        """Failures still standing. A failure is cleared when the identical check later passes twice in a row
        (a transient blip); one passing retest is not enough, because an intermittent fault also passes sometimes."""
        valid = self._valid()
        out = []
        for i, (e, r) in enumerate(valid):
            if r.ok:
                continue
            same = [x for _, x in valid[i + 1:] if self._key(x) == self._key(r)]
            if len(same) >= 2 and same[0].ok and same[1].ok:
                continue
            out.append((e, r))
        return out

    def _reproduced(self, failures) -> list[tuple[str, ToolResult]]:
        """Standing failures seen at least twice: the identical check failing again, or the same kind of
        failure from a different check (another source host, or traceroute as well as ping). Not a one-off blip."""
        valid = self._valid()

        def area(x):
            return "connectivity" if x.category == "routing" else x.category

        return [
            (e, r) for e, r in failures
            if sum(1 for _, x in valid if not x.ok and (self._key(x) == self._key(r) or area(x) == area(r))) >= 2
        ]

    def _areas_tried(self) -> set[str]:
        """Areas actually tested. A ping/port check that failed only because the name did not resolve
        (category "dns") says nothing about routing or ports, so it does not count."""
        tried = set()
        for _, r in self._valid():
            if r.tool == "dns_lookup":
                tried.add("dns")
            elif r.category in ("connectivity", "routing"):
                tried.add("connectivity")
            elif r.category == "port":
                tried.add("port")
        return tried

    # -- assurance (read-only; never changes a decision) ------------------
    def assess(self, verdict, fault_type=None, evidence_ids=()) -> tuple[str, str]:
        """How well the evidence backs an answer: ("confirmed" | "suspected" | "inconclusive", reason).

        confirmed: a fault that was reproduced in its area with ping, DNS and port all tried, or a healthy
        verdict with no standing failure and every area passing. suspected: the answer may be right but the
        evidence does not meet that standard. inconclusive: there is no usable answer, or the tests conflict.
        """
        failures = self._failures()
        if verdict == "inconclusive" or verdict not in ("fault", "healthy"):
            return "inconclusive", "No conclusion was reached from the tests."
        if verdict == "healthy":
            passed = {r.category for _, r in self._valid() if r.ok}
            if failures:
                return "inconclusive", f"Called healthy, but {len(failures)} failure(s) still stand in the tests."
            if _HEALTHY_NEEDS <= passed:
                return "confirmed", "No failure stands and connectivity, DNS and port checks all passed."
            miss = ", ".join(sorted(_HEALTHY_NEEDS - passed))
            return "suspected", f"No failure was seen, but these areas never passed a check: {miss}."
        needed = _FAULT_CATEGORIES.get(fault_type)
        ids = {i for e in evidence_ids for i in _ID.findall(str(e))}
        cited = [(e, r) for e, r in failures if r.category in (needed or ()) and (not ids or e in ids)]
        if not cited:
            return "suspected", "The answer cites no standing failure in the matching area."
        if not self._reproduced(cited):
            return "suspected", "The cited failure was seen only once, so it could be a transient blip."
        missing = _HEALTHY_NEEDS - self._areas_tried()
        if missing:
            return "suspected", f"The fault repeated, but these areas were never tested: {', '.join(sorted(missing))}."
        return "confirmed", "The failure repeated and ping, DNS and port were all tested."

    # -- decisions -------------------------------------------------------
    def decide(self) -> Verdict:
        valid = self._valid()
        failures = self._failures()
        if not failures:
            passed = {r.category for _, r in valid if r.ok}
            if _HEALTHY_NEEDS <= passed:
                return Verdict.STOP_HEALTHY
        elif self._reproduced(failures) and _HEALTHY_NEEDS <= self._areas_tried():
            return Verdict.STOP_FAULT
        if self.tests_run >= self.max_tests:
            return Verdict.STOP_CAP
        return Verdict.CONTINUE

    def allow_claim(self, verdict: str, fault_type: str, evidence_ids: list[str]) -> tuple[bool, str]:
        # Models cite "[E1]" or "E1: description"; extract the id rather than demand a bare one.
        # An item may also be one long string citing several ids; take every id in it.
        evidence_ids = [i for e in evidence_ids for i in (_ID.findall(str(e)) or [str(e)])]
        for e in evidence_ids:
            if e not in self._results:
                return False, f"Evidence id {e} does not exist. Cite only ids returned by your tests."
        failures = self._failures()
        if verdict == "healthy":
            if failures:
                return False, (
                    "You cannot call the network healthy: a test already failed "
                    f"({failures[0][0]}). Run the exact same check on it twice more: if it passes twice it was a "
                    "transient blip and you can then call the network healthy; if it fails again, report a fault."
                )
            if not any(r.ok for _, r in self._valid()):
                return False, "Run at least one test before concluding. No test has passed yet."
            return True, ""
        if verdict == "fault":
            needed = _FAULT_CATEGORIES.get(fault_type)
            if needed is None:
                return False, "fault_type must be one of dns_failure, route_failure, port_blocked for a fault claim."
            cited_failing = [
                e for e, r in failures if e in evidence_ids and r.category in needed
            ]
            if not cited_failing:
                unrelated = [
                    e for e in evidence_ids
                    if e in self._results and not self._results[e].ok and not self._relevant(self._results[e])
                ]
                if unrelated:
                    return False, (
                        f"The failures you cite ({', '.join(unrelated)}) are not about the ticket's target, so they "
                        "do not count as evidence of a fault. If every check on the ticket's target passed, "
                        "answer healthy; otherwise cite a failing result on the target itself."
                    )
                return False, (
                    "A fault claim needs a failing test as evidence in the matching area. "
                    "Cite a failing result, gather one, or answer healthy if everything passes."
                )
            if not self._reproduced([(e, r) for e, r in failures if e in evidence_ids and r.category in needed]):
                return False, (
                    f"That failure ({cited_failing[0]}) has only been seen once. Run the same check again "
                    "to confirm it before reporting a fault; a one-off failure may be a transient blip."
                )
            missing = _HEALTHY_NEEDS - self._areas_tried()
            # Once the test budget is used up, a confirmed fault is the best answer available.
            if missing and self.tests_run < self.max_tests:
                names = {"connectivity": "ping", "dns": "dns_lookup", "port": "port_check"}
                todo = " and ".join(names[m] for m in sorted(missing))
                return False, (
                    f"Not enough checked yet: {todo} has not been run against the server itself. A DNS failure makes ping and "
                    "port checks against the name fail without testing routing or ports, so repeat them against the "
                    "server using its node name or IP address instead of the DNS name, so that a second fault "
                    "is not hidden behind the first."
                )
            return True, ""
        if verdict == "inconclusive":
            # Only offered when the run opts in (--allow-inconclusive). It must be an honest last resort.
            if self.tests_run < min(3, self.max_tests):
                return False, "Run at least three tests before saying the evidence is inconclusive."
            if failures and self._reproduced(failures) and _HEALTHY_NEEDS <= self._areas_tried():
                return False, "A confirmed failure stands; report it as a fault instead of inconclusive."
            if not failures and _HEALTHY_NEEDS <= {r.category for _, r in self._valid() if r.ok}:
                return False, "Every area passed and nothing failed; report the network as healthy instead."
            return True, ""
        return False, "verdict must be 'fault' or 'healthy'."
