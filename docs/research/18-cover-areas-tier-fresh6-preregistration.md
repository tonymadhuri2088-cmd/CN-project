# fresh6: `--cover-areas` with confirmation scoring: pre-registration, written before any run

Status: **not run; a paid run needs explicit approval** (about $0.3 on Haiku 5.5). Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh6` (frozen in this commit, pinned by `tests/test_fresh6_suite.py`), `--cap 3`, 15 repeats of 7 scenarios = 105 runs per arm. No tuning.

## Why
The main open weakness is second-fault under-confirmation: with `--tier-claims`, both injected faults were confirmed in only 15 of 59 double-fault runs on Haiku (25%) and 5 of 21 on Sonnet (24%), because the controller stops once one fault is reproduced. `--cover-areas` makes both faulty areas reproduced in 60/60 runs (vs 16/60) but fresh5 scored only the final answer, where the metric was already saturated (59/60), so the benefit could not show. fresh6 measures the thing the intervention targets: confirmation, through `claim_report`.

## Arms (identical code, one flag differs)
- **A (tier):** `--tier-claims`.
- **B (tier + cover):** `--tier-claims --cover-areas`.

Commands:
```
python -m netwing.demo --backend sim --suite fresh6 --modes netwing --repeats 15 --cap 3 --tier-claims --out results/fresh6_tier.jsonl
python -m netwing.demo --backend sim --suite fresh6 --modes netwing --repeats 15 --cap 3 --tier-claims --cover-areas --out results/fresh6_tier_cover.jsonl
```

## Criteria (decided now)
- **M (the point):** over the 60 double-fault runs, "all injected faults confirmed" (set comparison through `claim_report`, as in `05-fresh3-tiered-claims.md`) in B is at least **25 points** higher than in A.
- **H (no harm):** `correct` in B not lower than A beyond overlapping Wilson 95% intervals; false alarms not higher; no-answers not higher beyond overlapping intervals; healthy answered healthy not lower.
- **C (cost):** mean tests in B at most 3 above A.

Verdict: all of M, H, C met means `--cover-areas` is a candidate to recommend together with `--tier-claims`; it still stays opt-in and the default controller and every published number stay unchanged. Otherwise it is reported as not supported. Intervals are wide at n=60; the write-up reports counts and says so. A stopped run is excluded from averages and reported as incomplete. A second model (Sonnet 5.5) is a separate approval.

## Limits
Simulator only; Haiku only; scenarios are new combinations but share the generator with earlier suites; `fx6_blip_route_dns` carries a blip flag that has no effect on an always-failing route fault (as in fresh3).
