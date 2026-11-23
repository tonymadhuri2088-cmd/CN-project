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
HEALTHY_STRATEGIES = ("rules", "hybrid", "belief")


class Verdict(Enum):
    CONTINUE = "continue"
    STOP_FAULT = "stop_fault"
    STOP_HEALTHY = "stop_healthy"
    STOP_CAP = "stop_cap"


_ID = re.compile(r"\bE\d+\b")


class Controller:
    def __init__(self, max_tests: int = 8, subject=None, guide_citations: bool = False, auto_cite: bool = False,
                 healthy_strategy: str = "rules", belief_tau: float = 0.85, resolver_hosts=None,
                 validate_claims: bool = False):
        if healthy_strategy not in HEALTHY_STRATEGIES:
            raise ValueError(f"healthy_strategy must be one of {HEALTHY_STRATEGIES}, got {healthy_strategy!r}")
        if not 0.5 < belief_tau < 1:
            raise ValueError("belief_tau must be between 0.5 and 1 (exclusive)")
        # opt-in healthy decision: "rules" (default, published), "hybrid" (rules, or belief once every standing failure
        # was retested and last passed and is not reproduced), "belief" (experimental: belief alone, ignores failures)
        self.healthy_strategy = healthy_strategy
        self.belief_tau = belief_tau
        self.resolver_hosts = resolver_hosts  # None: every host has a resolver; else DNS readings from other hosts are ignored
        # opt-in claim-level validation: each secondary fault claim (other_faults) must have its own standing,
        # reproduced, relevant failure in the matching area; the primary gate is unchanged
        self.validate_claims = validate_claims
        self.healthy_basis = ""  # why the last accepted/decided healthy verdict was allowed (auditable)
        self.max_tests = max_tests
        self.guide_citations = guide_citations  # opt-in: a rejected fault claim names the ids it could cite
        # opt-in: judge a fault claim by the evidence the run gathered, not by which ids the model happened to cite.
        # A standing failure in the matching area must still exist, be reproduced, and all areas must be tried.
        self.auto_cite = auto_cite
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
        a = r.args
        if r.tool == "dns_lookup" and self.resolver_hosts is not None and a.get("src") not in self.resolver_hosts:
            return False  # opt-in, source-aware: a host with no resolver cannot say anything about the network's DNS
        s = self.subject
        if s is None:
            return True
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

    # -- healthy decision strategies (opt-in; "rules" is the published default) ---------
    def _belief(self):
        from .belief import Belief  # lazy: the analysis layer is not needed by the default rules

        b = Belief()
        for _, r in self._valid():
            b.update(r.category, r.ok, source=r.args.get("src") or r.args.get("node"), resolver_hosts=self.resolver_hosts)
        return b

    def _healthy_ok(self, failures) -> tuple[bool, str]:
        """May the run be called healthy while `failures` still stand? Returns (ok, basis); basis names the rule.

        With no standing failure the default rule applies unchanged. With failures standing, only the opt-in strategies
        can say yes, and only on relevant evidence in which connectivity, DNS and port each passed at least once.
        hybrid additionally requires that every standing failure was retested by the identical check, that the latest
        retest passed, and that no failure is reproduced (the same check failing again, or the same area failing
        from another check): a reproduced failure is never overruled by the belief.
        """
        if not failures:
            passed = {r.category for _, r in self._valid() if r.ok}
            return (True, "rules: no failure stands") if _HEALTHY_NEEDS <= passed else (False, "")
        if self.healthy_strategy == "rules":
            return False, ""
        passed = {r.category for _, r in self._valid() if r.ok}
        if not _HEALTHY_NEEDS <= passed:
            return False, ""
        p = self._belief().p_healthy()
        if p < self.belief_tau:
            return False, ""
        if self.healthy_strategy == "belief":
            return True, f"belief (experimental): P(healthy)={p:.3f} >= {self.belief_tau} with {len(failures)} failure(s) standing"
        if self._reproduced(failures):
            return False, ""
        valid = self._valid()
        order = [e for e, _ in valid]
        for e, r in failures:
            later = [x for _, x in valid[order.index(e) + 1:] if self._key(x) == self._key(r)]
            if not later or not later[-1].ok:
                return False, ""
        return True, f"hybrid: P(healthy)={p:.3f} >= {self.belief_tau}; every standing failure retested, latest retest passed, none reproduced"

    def hint(self, res: ToolResult, eid: str) -> str:
        """Plain-language guidance appended to a tool result (opt-in, netwing mode). It changes no decision: it only
        says when a result does not count and what the standing failure needs, so the budget is not spent blindly."""
        parts = []
        if res.tool == "dns_lookup" and self.resolver_hosts is not None and res.args.get("src") not in self.resolver_hosts:
            parts.append(f"Note: {eid} was taken from a host with no DNS resolver, so it does not count toward a verdict.")
        elif self.subject is not None and res.evidence and res.category != "invalid" and not self._relevant(res):
            parts.append(f"Note: {eid} is not about the ticket's subject, so it does not count toward a verdict.")
        failures = self._failures()
        if failures:
            e, r = failures[0]
            valid = self._valid()
            order = [x for x, _ in valid]
            streak = 0
            for _, x in valid[order.index(e) + 1:]:
                if self._key(x) != self._key(r):
                    continue
                if not x.ok:
                    break
                streak += 1
            need = max(0, 2 - streak)
            args = ", ".join(f"{k}={v}" for k, v in r.args.items())
            parts.append(
                f"Standing failure {e} ({r.tool} {args}): it clears only if that identical check (same tool, same "
                f"arguments; a different name or address is a different check) passes {need} more time(s) in a row. "
                f"{max(0, self.max_tests - self.tests_run)} test(s) left."
            )
        return ("\n" + " ".join(parts)) if parts else ""

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

    def validate_other_faults(self, primary: str, other_faults) -> tuple[list[str], list[dict]]:
        """Check each secondary fault claim against the evidence. Returns (accepted secondary claims, per-claim report).

        confirmed: a relevant failure in the claim's area still stands and was reproduced (accepted).
        suspected: such a failure stands but was seen only once (not accepted: it may be a blip).
        unsupported: no relevant standing failure in that area, or an unknown fault type (not accepted).
        The report records the reason for every claim, including the primary, so a drop is never silent."""
        if not self.validate_claims:
            raise RuntimeError("validate_other_faults needs Controller(validate_claims=True)")
        failures = self._failures()
        report: list[dict] = []

        def judge(fault_type: str, role: str) -> dict:
            needed = _FAULT_CATEGORIES.get(fault_type)
            if needed is None:
                return {"fault_type": fault_type, "role": role, "status": "unsupported", "accepted": False,
                        "evidence": [], "reason": "Unknown fault type; no evidence area maps to it."}
            standing = [(e, r) for e, r in failures if r.category in needed]
            if not standing:
                return {"fault_type": fault_type, "role": role, "status": "unsupported", "accepted": False,
                        "evidence": [], "reason": "No failing check on the ticket's target in this area still stands."}
            ids = [e for e, _ in standing]
            if not self._reproduced(standing):
                return {"fault_type": fault_type, "role": role, "status": "suspected", "accepted": False,
                        "evidence": ids, "reason": "The failure was seen once only, so it may be a transient blip."}
            return {"fault_type": fault_type, "role": role, "status": "confirmed", "accepted": True,
                    "evidence": ids, "reason": "A relevant failure in this area stands and was reproduced."}

        report.append(judge(primary, "primary"))
        kept: list[str] = []
        seen = {primary}
        for ft in other_faults or []:
            if ft in seen:
                continue
            seen.add(ft)
            j = judge(ft, "secondary")
            report.append(j)
            if j["accepted"]:
                kept.append(ft)
        return kept, report

    # -- decisions -------------------------------------------------------
    def decide(self) -> Verdict:
        failures = self._failures()
        ok, basis = self._healthy_ok(failures)
        if ok:
            self.healthy_basis = basis
            return Verdict.STOP_HEALTHY
        if failures and self._reproduced(failures) and _HEALTHY_NEEDS <= self._areas_tried():
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
            basis = "rules: no failure stands"
            if failures:
                ok, basis = self._healthy_ok(failures)
            if failures and not ok:
                return False, (
                    "You cannot call the network healthy: a test already failed "
                    f"({failures[0][0]}). Run the exact same check on it twice more: if it passes twice it was a "
                    "transient blip and you can then call the network healthy; if it fails again, report a fault."
                )
            if not any(r.ok for _, r in self._valid()):
                return False, "Run at least one test before concluding. No test has passed yet."
            self.healthy_basis = basis
            return True, ""
        if verdict == "fault":
            needed = _FAULT_CATEGORIES.get(fault_type)
            if needed is None:
                return False, "fault_type must be one of dns_failure, route_failure, port_blocked for a fault claim."
            cited_failing = [
                e for e, r in failures if e in evidence_ids and r.category in needed
            ]
            if not cited_failing and self.auto_cite:
                standing = [e for e, r in failures if r.category in needed]
                if standing:
                    cited_failing = standing
                    evidence_ids = list(evidence_ids) + standing
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
                if self.guide_citations:
                    options = [e for e, r in failures if r.category in needed]
                    if options:
                        return False, (
                            f"None of the results you cited is a failing check in the area of {fault_type}. "
                            f"The failing results of that kind so far are {', '.join(options)}: cite one of them as evidence."
                        )
                    return False, (
                        f"No failing check in the area of {fault_type} exists yet, and passing results cannot prove a fault. "
                        "Run the check that would show it, or pick the fault type your failing results point to."
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
