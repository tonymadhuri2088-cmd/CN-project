# fresh6: `--cover-areas` with confirmation scoring: results

Pre-registration: `18-cover-areas-tier-fresh6-preregistration.md` (criteria unchanged; written before any run). Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh6`, `--cap 3`, 15 repeats of 7 scenarios = 105 runs per arm. Both arms ran to completion: no errors, no excluded runs. Spend $0.14 (A) and $0.16 (B).

Arms: **A** = `--tier-claims`; **B** = `--tier-claims --cover-areas`. Logs: `results/fresh6_tier.jsonl`, `results/fresh6_tier_cover.jsonl`.

## Criteria
| Criterion | A (tier) | B (tier + cover) | Verdict |
|---|---|---|---|
| **M:** all injected faults confirmed on the 60 double-fault runs, B at least +25 points over A | 16/60 (27% [17-39]) | 59/60 (98% [91-100]) | **Met** (+71 points) |
| **H:** no harm: correct, false alarms, no-answers, healthy correct | exact 61/105; false alarms 0/15; no-answer 0/105; healthy 15/15 | exact 104/105; false alarms 0/15; no-answer 0/105; healthy 15/15 | **Met** (nothing worse; exact is higher) |
| **C:** mean tests at most +3 over A | 7.30 (double-fault runs 8.42) | 8.32 (double-fault runs 10.43) | **Met** (+1.0; +2.0 on double-fault runs) |

Suspected (seen once) claims fell from 37 to 0. Missed faults and extra claims were 0 in both arms.

## Reading
The earlier null result (fresh5) was a ceiling effect of scoring only the final answer. Scored by confirmation, `--cover-areas` removes the second-fault under-confirmation seen on Haiku (15/59) and Sonnet (5/21): both faulty areas are tested to the confirmation standard before the controller stops, at about one extra test per run.

## Decision
`--cover-areas` is a candidate to recommend together with `--tier-claims`. It stays opt-in; the default controller and every published number are unchanged.

## Limits (say them)
Simulator only; Haiku only (Sonnet not run on this suite); n=60 double-fault runs, so the interval for B starts at 91%; scenarios are new combinations from the same generator; `fx6_blip_route_dns` carries a blip flag with no effect on an always-failing route fault. Real-network and second-model confirmation are Major-project items. Not claimed: that this holds on real networks or other models.
