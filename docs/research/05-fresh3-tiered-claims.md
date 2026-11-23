# fresh3: tiered claims (confirmed vs suspected)

Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh3` (frozen in `06a1be0`), code `6f2bf36`, results committed in `2103c32`, run 24 Nov 2026. Every log is an intact 15-repeat run (105 runs, 15 per scenario). No tuning on the results.

## Pre-registration (written before any run)
**Why.** In fresh2, strict claim validation removed unsupported extra-fault claims but also dropped real second faults, because the second fault is usually seen once. Tiered claims keep such a claim visible as "suspected" and score it separately.

**Frozen.** Suite `fresh3`: 7 scenarios (4 multi-fault, 2 single faults, 1 healthy), pinned by `tests/test_fresh3_suite.py`, with a test that no definition repeats an earlier suite. Limitation: `fx3_blip_route` carries a blip flag that has no effect on an always-failing route fault. Default rules, hybrid rule, retest hint and strict validation are unchanged. New opt-in flag `--tier-claims` (implies validation): confirmed secondary claims stay in `other_faults`; claims seen once go to `suspected_faults`; unsupported claims are dropped; every claim is logged in `claim_report`. Scores: `complete` (strict, unchanged) and `complete_incl_suspected`; both are reported.

**Configurations (15 repeats each):** original; validate (strict); tier; hybrid + hint; hybrid + hint + tier.

**Criteria.**
- **T, tier vs original:** a candidate only if ALL hold: multi-fault exact including suspected >= 80% and not more than 20 points below the original; extra-fault claims including suspected at least 10 points lower than the original; missed faults and false alarms do not increase; no-answer rate not higher beyond overlapping CIs.
- **H, hybrid + hint (replication):** healthy accuracy not lower; missed faults, false alarms and no-answer not higher; mean tests within +1. Only 15 healthy runs, so this is a replication check.
- **C, hybrid + hint + tier:** reported; promoted only if T and H both pass.

A tier pass would be a reporting-quality result; it would not change the default or show that NetWing detects extra faults better in general.

**Data handling (from the fresh2 lesson).** Each configuration writes a new file; a stopped run is reported as incomplete and rerun into a new file; only an intact 15-repeat log is analysed as primary.

## Results (Wilson 95% CIs; 15 healthy runs, 90 faulty runs of which 60 multi-fault)
| Config | Exact (strict) | Healthy answered healthy | Missed / false fault | Extra fault claimed (confirmed) | No answer | Multi exact (strict, n=60) | Multi exact incl. suspected | Extra incl. suspected | Suspected claims | Tests |
|---|---|---|---|---|---|---|---|---|---|---|
| original | 64% [54-72] | 100% [80-100] | 0 / 0 | 18% [11-27] | 2% | 55% [42-67] | 55% | 18% | 0 | 8.8 |
| validate (strict) | 58% [49-67] | 100% | 0 / 0 | 0% [0-4] | 1% | 28% [19-41] | 28% | 0% | 0 | 9.0 |
| tier | 57% [48-66] | 100% | 0 / 0 | 0% [0-4] | 1% | 25% [16-37] | 65% [52-76] | 11% [6-19] | 41 | 8.6 |
| hybrid + hint | 81% [72-87] | 100% | 0 / 0 | 9% [5-17] | 2% | 77% [65-86] | 77% | 9% | 0 | 8.0 |
| hybrid + hint + tier | 51% [42-61] | 100% | 0 / 0 | 0% [0-4] | 2% | 15% [8-26] | 57% [44-68] | 6% [2-12] | 33 | 8.2 |

## Verdict against the pre-registered criteria
- **T, tier vs original: NOT met.** Multi-fault found counting suspected is 65% (needed >= 80%); extra claims including suspected fall 18% to 11% (needed >= 10 points lower, got 7). Missed faults, false alarms and no-answer did not get worse. Tier is not promoted; the default is unchanged.
- **H, hybrid + hint replication: met, but uninformative.** The only healthy scenario is already 100% for the original, so fresh3 cannot test the hybrid's healthy gain; fresh2 (13% to 97%) remains the evidence.
- **C: not promoted** (T failed).

## What the logs show
1. The controller rarely confirms a second fault. Over the 60 double-fault runs, both injected faults were confirmed in only 15 runs (tier) and 9 (hybrid + hint + tier); in 31 and 28 runs one fault was confirmed and the other "suspected" (seen once). The stop rule ends the investigation once the primary fault is reproduced and ping/DNS/port were tried, so the second fault has had one sighting at most. In the tier log both faults were confirmed in exactly the 15 runs where the other fault's area had at least two failing checks, and 43 of 59 answered double-fault runs stopped with exactly one failing check in that area.
2. The tier layer does what it should as a reporting layer (no unsupported claim survives as confirmed: 0 of 90), but its suspected tier still contains wrong claims (10 of 90 faulty runs with an extra claim once suspected ones are counted).
3. Sampling variance is large. `hybrid + hint` and `hybrid + hint + tier` run identical agent behaviour (tiering only post-processes the accepted answer), yet differ by about 20 points on multi-fault found. So the apparent gain of hybrid + hint on multi-fault (55% to 77%) is NOT established; it was not a pre-registered criterion. Do not claim it.
4. Absolute levels differ across suites (original extra-claim rate 56% on fresh2, 18% on fresh3), so rates must be quoted per suite.

## Consequences
Supported: hybrid + hint fixes the healthy-network failure (fresh2). Strict claim validation removes unsupported extra claims but loses real second faults. Tiering keeps second faults visible but does not meet its bar. Not supported: any claim that NetWing improves multi-fault detection or solves hallucinated diagnoses in general.

## Erratum (added 24 Nov 2026; the text above is unchanged)
An earlier version of this analysis stated that the true second fault was confirmed in only 1 run each of tier and the combined configuration. That figure was wrong: it counted only claims of the injected second fault as listed in `other_faults`, but the model often leads with that fault and names the other as secondary. Recomputed by set (all injected faults confirmed, using `claim_report`) over the 60 double-fault runs:

| Config | both faults confirmed | one confirmed + other suspected | one confirmed, other not claimed / unsupported | no fault answer |
|---|---|---|---|---|
| tier | 15 (25%) | 31 | 13 | 1 |
| hybrid + hint + tier | 9 (15%) | 28 | 21 | 2 |

These match the strict "Multi exact" column (25%, 15%), which was correct all along, so the table, the verdicts (T, H, C) and the conclusions are unaffected.
