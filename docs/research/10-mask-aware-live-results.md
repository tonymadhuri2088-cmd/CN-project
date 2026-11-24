# mask-aware v1: live-model results (negative result)

Simulator, `claude-haiku-5-5`, netwing mode, code `b99e613` (clean tree), run 25 Nov 2026 under `docs/research/09-mask-aware-preregistration.md`. Logs: `results/maskaware_off.jsonl`, `results/maskaware_on.jsonl` (170 intact runs each, 17 scenarios x 10 repeats, no errors, about $0.50 in total). Wilson 95% intervals.

## Result against the pre-registered criteria
| Criterion | off | on (`--mask-aware`) | Verdict |
|---|---|---|---|
| P1: route-only runs (n=70) naming `port_blocked` | 3/70 (4% [1-12]) | 3/70 (4% [1-12]) | Benefit not shown. The masking rule fired on 0 of 70 route-only runs. |
| P2: port runs (n=100), correct | 92% [85-96] | 85% [77-91] | Formally passes (intervals overlap); see below. |
| P2: port runs, no answer | 8% [4-15] | 15% [9-23] | Formally passes (intervals overlap). |
| P3: route-only, no answer / mean tests | 0/70, 6.34 | 0/70, 6.39 | Passes. |

All 70 route-only runs were answered correctly in both configurations. In all six runs where `port_blocked` appeared, it was an extra fault in `other_faults` next to a correct `route_failure`; the flag gates only the primary claim, so it could not affect them. The latent primary-claim false positive never occurred with this model.

## The regression the pooled criteria hide
All 10 rejections by the masking rule happened in one scenario, `fx3_campus_noisy_blip_port` (true port fault plus a one-off lost ping). Off: 9 of 10 answered correctly. On: 0 of 10, all ending in no-answer at the 12-test cap (mean 12.0 tests). Mechanism: the first ping is lost once (the blip) and only one passing ping follows; a failure is cleared only by two identical passes, so a connectivity failure still "stands", the rule treats it as a route failure, and the true `port_blocked` claim is rejected until the cap. The v1 rule masks on a single sighting, which is the defect. This was found in a per-scenario view that was not pre-registered, and is reported as a finding, not as a pass.

## Consequences
- `--mask-aware` stays opt-in and off by default, unchanged, as a documented negative result. No published number changes.
- Masking v2 (`--mask-reproduced`: only a reproduced connectivity failure masks; masked secondary port claims are dropped and logged) is pre-registered separately on a new frozen suite, `fresh4` (`docs/research/11-fresh4-mask-reproduced-preregistration.md`).
- Limitation of this experiment: the scenarios were mostly used in earlier suites, so it makes no generalisation claim; one model; simulator only.
