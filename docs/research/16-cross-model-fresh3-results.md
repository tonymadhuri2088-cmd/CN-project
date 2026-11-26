# Cross-model check of fresh3 on Sonnet 5.5: results

Pre-registration: `14-cross-model-fresh3-preregistration.md` (criteria unchanged). Simulator, `claude-sonnet-5-5`, netwing mode, suite `fresh3`, `--cap 3`.

## What was run, and deviations (stated before the numbers)
- **Original arm:** complete, 56/56 runs answered, no errors. Spend about $2.00.
- **Tier arm: incomplete.** 36 runs answered (5 full repeats of 7 scenarios plus 1 run) out of the planned 56. The run stopped on an `APIConnectionError` (network, not model) at `fx3_campus_noisy_multi_dns_route`; an earlier attempt stopped after 4 runs for the same reason and is kept as `results/fresh3_sonnet_tier_partial_connerr.jsonl`. The error record is excluded from all numbers. Spend about $1.29. It was not rerun.
- **Code deviation:** Sonnet 5.5 rejects a forced `tool_choice`. The agent now drops it for such models and relies on the in-text instruction already appended at the cap (commit `3eb97b0`, with a test). Haiku behaviour is unchanged. The first two Sonnet attempts failed on this and on an invalid key; both logs are in `results/failed/` and contain no scored runs.
- Counts are small (n=21 double-fault runs in the tier arm); intervals are Wilson 95%.

## Results
| Criterion | Result | Verdict |
|---|---|---|
| **C1** default controller correct, not lower than Haiku | Sonnet 56/56 (93.6-100%) vs Haiku 103/103 (96.4-100%); healthy 8/8, false alarms 0/8, no-answer 0 | **Met** |
| **C2** both faults confirmed in tier-arm double-fault runs, below 50% | 5/21 = 24% [11-45] (Haiku 15/59 = 25% [16-38]) | **Met, provisional** (partial arm, interval reaches 45%) |
| **C3** T criterion of `05` unchanged | multi-fault exact incl. suspected 15/21 = 71% (needs >= 80%); extra claims incl. suspected 0/31 (0%) vs original 1/48 (2%), a 2-point gap (needs >= 10) | **Not met** |

Descriptive: on all-faults-found for the default controller Sonnet reached 24/32 (75%) against Haiku 33/59 (56%).

## Reading
- The central finding is not specific to one model: the controller never invented a fault on a healthy network and never missed a fault on either model.
- The second-fault under-confirmation reproduced (24% vs 25%): it follows from the stop rule, not from Haiku.
- Tiering is not promoted for Sonnet either. C3 cannot be met by this arm even with the missing runs: the original arm has only 1/48 extra claims, so the required 10-point reduction is out of reach.
- Not claimed: a Sonnet-vs-Haiku quality ranking (different n, separate runs), or any completeness gain.
