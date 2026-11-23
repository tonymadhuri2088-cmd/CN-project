# Architecture audit: why a confirmed fault is not a complete diagnosis (24 Nov 2026)

Read-only audit of the repository at `2103c32`; no code was changed. Baseline: 316 tests passed, 4 skipped (real-lab parity tests); ruff clean. Data: the fresh2 and fresh3 logs. This is a design analysis for future work; nothing in it is implemented.

## 1. How the controller works today
- `Controller` (`netwing/controller.py`) is an append-only evidence ledger. `observe` assigns ids E1.. and nothing else. Every decision is recomputed from derived views: `_valid` (valid, evidence-bearing, relevant to the ticket subject), `_failures` (failing results not cleared; cleared only when the identical check later passes twice in a row), `_reproduced` (standing failures seen at least twice: the same check again, or any failure in the same area), `_areas_tried` (DNS, connectivity, port).
- `decide()` returns CONTINUE / STOP_FAULT / STOP_HEALTHY / STOP_CAP: healthy first (per strategy), then STOP_FAULT iff a failure is reproduced and all three areas were tried, then STOP_CAP at 12 tests.
- `allow_claim` gates only the final answer. Opt-in layers sit on top: citation helpers, healthy strategies, claim validation (`validate_other_faults`: confirmed / suspected / unsupported), `assess` (read-only assurance).
- The agent loop lets the model choose every tool call; the controller never schedules a test. Validation and tiering post-process the accepted answer; they never change what is tested.
- Reusable machinery: `belief.py` (posterior over {dns, route, port}, `expected_info_gain`, `next_best_test`), `strategy_replay.py`, `final_report.py`.

## 2. Why it stops after the primary fault
STOP_FAULT is a property of the whole ledger, not of any one fault. Any one reproduced failure plus one test in each area satisfies it, which can happen in 4 tests. "Primary" is not a controller concept: it is whichever fault the model happened to test twice first. Measured on fresh3 double-fault runs: mean 8.7 of 12 tests; 70% of runs left budget unused.

## 3. Why secondary faults are missed (measured)
Evidence for the other fault existed in every answered double-fault run, but a second failing check in its area existed in only about 25-30%. Both faults were confirmed in exactly the 15 tier runs where the other area had at least two failing checks. Confirming the second fault is an accident of the model's own test choices. By set over 60 double-fault runs: tier 15 both confirmed / 31 one confirmed + one suspected / 13 one confirmed + other not claimed; combined configuration 9 / 28 / 21.

## 4. Where the evidence model is insufficient (verified in code)
1. No fault or hypothesis objects: a "fault" exists only as a string in the final answer, so there is no per-fault state and "completeness" is undefined.
2. No causal masking or dependence. The simulator makes port checks time out when there is no route, and masks ping/port by name under a DNS fault (handled by a category rule for DNS only). **Verified latent false positive:** on a route-only network, a `port_blocked` claim is accepted and classed "confirmed". No existing suite triggers it, so no result is affected, but any layer that confirms secondary faults would inherit it. `belief.py` already models "port check fails if route or port is broken".
3. Thin provenance: no timestamps, no source/target fields, claims carry fault types only.
4. Contradictions are implicit: there is no REFUTED state; an alternating (flaky) check is neither confirmed nor refuted in a defined way.
5. "Reproduced" is coarse: ping plus traceroute of one broken route count as independent reproduction.
6. Coverage is coarse and test-count based; no value-of-information or cost model; the controller cannot veto, reorder or require a test.
7. RESOLVED has no referent: no tool changes network state, so it could only mean "observed to recover".

## 5. Sketch of an extension without duplication (not built)
A read-only layer (for example `netwing/dcc.py`) computing per-fault state from the existing ledger views (standing and not reproduced = suspected; reproduced with coverage = confirmed; cleared by two identical passes = refuted or resolved; never tested = unseen), with controller-owned stop states (complete / incomplete / budget exhausted / no fault confirmed) and a scheduler that, when a stop would fire while a suspected fault or untried check remains and budget is left, requires the named re-test (deterministic baseline first, then an information-gain variant built on `belief.py`). Everything would be opt-in and evaluated on a new frozen suite with pre-registered criteria.

## 6. Risks
Masking must be modelled before any secondary fault can be "confirmed". Fault identity (type only vs type + target) limits generality. More probing raises cost, so criteria must pre-register a tolerance. Sampling variance was about 20 points between behaviourally identical configurations, so more repeats and paired comparisons are needed. New scenarios (contradictory evidence, three or more faults, route + port masking) need new simulator flags, which must be opt-in and tested.
