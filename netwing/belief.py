"""Bayesian belief over which areas are broken, and which test would tell us the most.

This is an analysis layer. It never changes a diagnosis, a prompt or a controller decision.

Model. Three independent binary causes: DNS broken (D), route to the server broken (R), web port filtered (P).
A state is a combination of them (eight states; none broken = healthy), so two faults at once need no special case.
Each relevant test is a noisy reading of the causes it can see:

    dns check            fails if D
    connectivity check   fails if R              (a ping/port check that failed on name resolution is a DNS result)
    port check           fails if R or P         (with no route the port check times out too)

A reading disagrees with the truth with a small probability: `false_fail` (a healthy path blips, as in the flaky
suites) and `miss` (an intermittent fault passes this time). Tests are treated as independent given the state; that
is the main simplification, and it is the same one the confirm-twice rule makes when it trusts a repeated failure.
Results the controller ignores (invalid, unrelated to the ticket, flagged non-evidence) are ignored here too.
"""
from __future__ import annotations

import itertools
import math

CAUSES = ("dns", "route", "port")
STATES = tuple(itertools.product((False, True), repeat=3))  # (dns, route, port) broken?
TESTABLE = ("dns", "connectivity", "port")
_FAULT_OF = {"dns_failure": "dns", "route_failure": "route", "port_blocked": "port"}


def _sees(category: str, state: tuple) -> bool | None:
    """Would a check of this category fail in this state? None: the category carries no information."""
    d, r, p = state
    if category == "dns":
        return d
    if category == "connectivity":
        return r
    if category == "port":
        return r or p
    return None


def _entropy(weights) -> float:
    return -sum(w * math.log2(w) for w in weights if w > 0)


class Belief:
    def __init__(self, prior: float = 0.25, false_fail: float = 0.08, miss: float = 0.15):
        if not (0 < prior < 1 and 0 < false_fail < 0.5 and 0 < miss < 0.5):
            raise ValueError("prior must be in (0,1); false_fail and miss in (0,0.5)")
        self.false_fail, self.miss = false_fail, miss
        self.w = {s: math.prod(prior if b else 1 - prior for b in s) for s in STATES}
        self._norm()
        self.n = 0  # readings used

    def _norm(self):
        z = sum(self.w.values())
        self.w = {s: v / z for s, v in self.w.items()}

    def _p_fail(self, category: str, state: tuple) -> float | None:
        f = _sees(category, state)
        if f is None:
            return None
        return 1 - self.miss if f else self.false_fail

    def update(self, category: str, ok: bool) -> bool:
        """Fold one reading in. Returns False if the category carries no information (nothing changes)."""
        if _sees(category, STATES[0]) is None:
            return False
        for s in STATES:
            pf = self._p_fail(category, s)
            self.w[s] *= (1 - pf) if ok else pf
        self._norm()
        self.n += 1
        return True

    # -- what the belief says --------------------------------------------
    def map_state(self) -> tuple:
        return max(STATES, key=lambda s: (self.w[s], -sum(s)))  # ties: the state with fewer faults

    def confidence(self) -> float:
        """Posterior probability of the most likely state."""
        return self.w[self.map_state()]

    def marginals(self) -> dict:
        return {c: sum(v for s, v in self.w.items() if s[i]) for i, c in enumerate(CAUSES)}

    def p_healthy(self) -> float:
        return self.w[(False, False, False)]

    def entropy(self) -> float:
        return _entropy(self.w.values())

    def diagnosis(self) -> frozenset:
        """The set of broken areas in the most likely state (empty set = healthy)."""
        return frozenset(c for c, b in zip(CAUSES, self.map_state()) if b)

    # -- which test next --------------------------------------------------
    def expected_info_gain(self, category: str) -> float:
        """Expected entropy reduction (bits) from one more check of this category."""
        if _sees(category, STATES[0]) is None:
            return 0.0
        p_fail = sum(self.w[s] * self._p_fail(category, s) for s in STATES)
        gain = self.entropy()
        for fail, p_y in ((True, p_fail), (False, 1 - p_fail)):
            if p_y <= 0:
                continue
            post = [self.w[s] * (self._p_fail(category, s) if fail else 1 - self._p_fail(category, s)) / p_y
                    for s in STATES]
            gain -= p_y * _entropy(post)
        return gain

    def next_best_test(self) -> tuple[str, float]:
        gains = {c: self.expected_info_gain(c) for c in TESTABLE}
        best = max(TESTABLE, key=lambda c: gains[c])
        return best, gains[best]


def truth_set(scenario) -> frozenset:
    """The areas that are really broken in a scenario (empty set = healthy)."""
    if scenario.truth == "healthy":
        return frozenset()
    return frozenset(_FAULT_OF[t] for t in (scenario.truth, *scenario.also) if t in _FAULT_OF)


def answer_set(answer: dict | None) -> frozenset | None:
    """The areas an agent's final answer calls broken; None if it gave no usable answer."""
    if not answer or answer.get("verdict") not in ("fault", "healthy"):
        return None
    if answer["verdict"] == "healthy":
        return frozenset()
    found = {answer.get("fault_type")} | set(answer.get("other_faults") or [])
    return frozenset(_FAULT_OF[f] for f in found if f in _FAULT_OF)
