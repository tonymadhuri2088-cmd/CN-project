# fresh4: masking v2 results

Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh4` (7 scenarios, frozen in `daa494b`, pre-registered in `11-fresh4-mask-reproduced-preregistration.md`), run 25 Nov 2026. Three intact logs of 105 runs each (15 repeats x 7 scenarios), no errors, about $0.53 in total: `results/fresh4_off.jsonl`, `results/fresh4_v1.jsonl` (`--mask-aware`), `results/fresh4_v2.jsonl` (`--mask-reproduced`). Wilson 95% intervals. No rule or prompt was changed after the results.

| | off | v1 `--mask-aware` | v2 `--mask-reproduced` |
|---|---|---|---|
| All runs, correct | 98% [93-99] | 74% [65-82] | 98% [93-99] |
| Port-blip runs (n=45), correct | 43/45 (96% [85-99]) | 18/45 (40% [27-55]) | 43/45 (96% [85-99]) |
| Port-blip runs, no answer | 2/45 (4% [1-15]) | 27/45 (60% [45-73]) | 2/45 (4% [1-15]) |
| Port-blip runs, mean tests | 9.78 | 11.82 | 9.89 |
| Route-only runs (n=60), correct | 60/60 | 60/60 | 60/60 |
| Route-only runs, no answer | 0/60 | 0/60 | 0/60 |
| Route-only runs, mean tests | 6.05 | 6.63 | 6.48 |
| Route-only runs with `port_blocked` among the extra faults | 1/60 | 1/60 | 0/60 kept (1 dropped and logged) |
| Masking-rule rejections on port-blip runs | 0 | 43 (25 of those runs ended with no answer) | 0 |

## Verdict against the pre-registered criteria
- **B (blip over-masking fixed): met.** v2 on the port-blip runs is identical to off (96% correct, 4% no answer). v1 reproduced the defect on a new suite: 40% correct and 60% no answer, intervals clearly apart from off.
- **R (no harm on route-only): met.** 60/60 correct and 0 no-answers for v2; mean tests 6.48 vs 6.05 (within +1).
- **S (secondary claims): not informative.** The baseline made the targeted mistake in only 1 of 60 route-only runs (needed at least 3). v2 dropped that one claim and logged it, as designed, but one run does not show a benefit.

## What this means
- v2 fixes the specific defect of v1 and is safe on this suite, so it can be described as a usable opt-in. It stays off by default.
- Its benefit is not demonstrated: with this model, the mistake it targets is rare (1 of 60 here; 3 of 70 and mostly in extra claims in the first run), and on these runs v2 never rejected a primary claim. It is a safety rule that is inert unless the model makes the mistake.
- Limits: one model, simulator only, 15 repeats, a suite written by the authors. This is not evidence for any default change.
