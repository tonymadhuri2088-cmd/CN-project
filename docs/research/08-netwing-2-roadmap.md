# NetWing 2.0 roadmap (proposal, not yet approved or run)

Rule: Mini Project 2 stays a frozen tagged baseline (`mini2-final`). Everything below is opt-in, in new modules, with a new pre-registered suite and new logs.

1. Per-fault state (`netwing/dcc.py`, read-only layer): confidence per candidate fault from the ledger.
2. Dependency and masking graph: removes the route-only `port_blocked` false positive.
3. Evidence completeness score: a completeness stop in place of a bare cap.
4. Contradiction counts: flag clashing evidence before a claim is accepted.
5. Adaptive test selection: pick the next test that best splits remaining candidates.
6. Cross-model evaluation: a second model on the same frozen suites.
7. Real-network hardening: run the Kathara backend; more netns scenarios.
8. fresh4 frozen suite, 30+ repeats, paired comparison against the baseline with Wilson intervals.

Any paid run needs approval first.
