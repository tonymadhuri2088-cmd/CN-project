# fresh5: `--cover-areas` results (pre-registration: `13-cover-areas-fresh5-preregistration.md`)

Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh5` (7 scenarios, 15 repeats each, 105 runs per arm), run 25 Nov 2026 at the code of commit `2fea758`. Logs: `results/fresh5_off.jsonl`, `results/fresh5_cover.jsonl`. Spend: $0.12 (off) and $0.15 (cover). No tuning on the results.

**Log note.** `fresh5_cover.jsonl` has 106 lines. Line 1 is an `APIConnectionError` record (`fx5_route_dns`, $0.00) left by a first attempt that lost the network connection; the 105 real runs follow it. All numbers below exclude that error record, as the summary table did.

## Pre-registered criteria
| Criterion | Result | Verdict |
|---|---|---|
| **M**: `complete` on the 60 double-fault runs at least +15 points above off | off 59/60 (98%), cover 59/60 (98%): +0 points | **Not met** |
| **H**: no harm. `correct` not lower beyond overlapping Wilson 95% intervals; false alarms and no-answers not higher; healthy `correct` not lower | correct 104/105 (off) vs 105/105 (cover); false alarms 0 vs 0; no-answers 1 vs 0; healthy 15/15 vs 15/15 | **Met** |
| **C**: mean tests at most 3 above off | 6.57 vs 7.68 (+1.1); double-fault runs 7.25 vs 9.28 | **Met** |

Not a candidate for promotion: M failed. The default is unchanged and `--cover-areas` stays opt-in.

## Why M failed: the metric saturated
The strict `complete` score only asks whether the answer names every injected fault. On these scenarios Haiku already named both faults in 59 of 60 double-fault runs without the rule, so there was no room for the +15 points. This is a weakness in the pre-registered metric, not evidence about the rule: `05-fresh3-tiered-claims.md` measured the gap through confirmation (`claim_report`), which needs `--validate-claims`, and I did not use that in fresh5.

## Exploratory result (not pre-registered; do not read it as a criterion)
Counting, from the logged tool results, the double-fault runs in which BOTH faulty areas had at least two failing checks:

| | off | cover |
|---|---|---|
| both faulty areas seen failing at least twice | 16/60 (27%) [17-39] | 60/60 (100%) [94-100] |

So the rule does what it was built to do: it makes the second fault reproduced, not just named. What it does not show is that this changes the final answer, because the baseline answers were already right. Extra cost: 10 of 105 cover runs reached the 12-test cap against 2 of 105 without it.

## Conclusion for the paper
- `--cover-areas` meets the no-harm and cost criteria and raises second-fault evidence from 27% to 100% of double-fault runs, but shows no gain in answer completeness on this suite (ceiling).
- To show an answer-level benefit, the next test must score confirmation (run with `--validate-claims`, as in fresh3) on a model or suite where the baseline names both faults less often. That would be a new pre-registration on a new frozen suite.
- Evidence is one model, simulator only, 15 repeats per scenario.
