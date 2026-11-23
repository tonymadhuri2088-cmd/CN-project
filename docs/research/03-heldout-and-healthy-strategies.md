# Held-out suite and the healthy-network strategies (22-23 Nov 2026)

Simulator, Claude Haiku 5.5, 12-test cap, 80 runs per mode (10 repeats x 8 scenarios; 20 of the 80 runs per mode are healthy networks). Protocol: run once on frozen code; no rule changed afterwards.

## Held-out results
| Pass | Mode | Correct [95% CI] | False alarms (healthy) | Healthy answered correctly | No answer | Mean tests | All faults found |
|---|---|---|---|---|---|---|---|
| default rules | plain | 90% [81-95] | 40% [22-61] | 60% | 0 | 11.1 | 97% |
| default rules | healthy_ok | 85% [76-91] | 60% [39-78] | 40% | 0 | 11.0 | 97% |
| default rules | netwing | 84% [74-90] | 0% [0-16] | 50% | 13 | 8.3 | 100% |
| `--auto-cite` | plain | 81% [71-88] | 70% [48-85] | 30% | 0 | 11.1 | 97% |
| `--auto-cite` | healthy_ok | 84% [74-90] | 65% [43-82] | 35% | 0 | 11.1 | 97% |
| `--auto-cite` | netwing | 88% [78-93] | 0% [0-16] | 50% | 10 | 8.4 | 97% |

- Zero false alarms held in both passes (0 of 40 healthy netwing runs); baselines had 40-70%.
- Netwing used about 25% fewer tests in both passes.
- Baselines moved a lot between two passes of identical conditions (plain false alarms 40% to 70%), so single-pass baseline comparisons need 30+ repeats.
- Overall correctness differences between modes are within the intervals; no accuracy claim is supported.
- The weakness: netwing gave no answer on 13 runs (10 healthy runs with one transient failure, 3 intermittent-port faults).

## Why the 13 no-answers happened
Every one used all 12 tests and ended after 3 rejected claims. In each, the subject check failed once, the agent re-ran the identical check once (it passed once; the rule needs two), then claimed healthy, was told to repeat the check twice more, and had no tests left. 3-6 of the 12 tests had gone to alerts the controller does not count (`printer.lab` DNS, `h2:8080`, `10.0.3.10`). Feedback arrived only when the agent tried to answer, after the budget was gone. The 3 intermittent-port cases are a real fault that fails then passes; calling them healthy would be wrong, so not every no-answer should become "healthy".

## Opt-in strategies built in response (defaults unchanged)
- `--retest-hint`: tells the agent which results do not count and what a standing failure needs to clear.
- `--healthy-strategy hybrid`: also accepts "healthy" only if connectivity, DNS and port each passed, every standing failure was retested by the identical check and its latest retest passed, no failure is reproduced, and P(healthy) >= `--belief-tau` (default 0.85). Never touches fault verdicts, the budget stop or an unretested failure. Basis logged in `healthy_basis`.
- `--healthy-strategy belief`: experimental; belief alone. Not recommended.
- `--resolver-hosts`: DNS readings from hosts without a resolver are ignored.
- `python -m netwing.strategy_replay`: free counterfactual replay on saved logs.

Exploratory replay on the 240 held-out logs (same trajectories, different stop rule; NOT a validation, threshold chosen after seeing the logs):

| Strategy | tau | Healthy networks: would stop healthy | Faulty networks: would stop healthy | Mean tests at healthy stop |
|---|---|---|---|---|
| rules (default) | - | 30/60 (50%) | 0/180 | 3.0 |
| hybrid | 0.85 | 50/60 (83%) | 0/180 | 5.3 |
| hybrid | 0.90 | 39/60 (65%) | 0/180 | 4.8 |
| belief | 0.85 | 60/60 (100%) | 0/180 | 4.9 |

## First fresh validation (`fresh`, 8 scenarios defined before any run; run once; no tuning)
| Config | Exact diagnosis | Healthy answered healthy | False fault | Missed fault | Extra fault claimed | No answer | Mean tests |
|---|---|---|---|---|---|---|---|
| plain | 64% [53-73] | 60% [42-75] | 40% | 0% | 34% | 0% | 11.5 |
| healthy_ok | 69% [58-78] | 67% [49-81] | 33% | 0% | 28% | 0% | 11.1 |
| netwing (original) | 71% [61-80] | 100% [89-100] | 0% | 0% | 44% | 0% | 9.2 |
| netwing + hint | 75% [65-83] | 100% | 0% | 0% | 40% | 0% | 7.2 |
| netwing + hybrid | 72% [62-81] | 100% | 0% | 0% | 44% | 0% | 7.9 |
| netwing + hybrid + hint | 78% [67-85] | 100% | 0% | 0% | 36% | 0% | 7.4 |
| netwing + belief | 76% [66-84] | 100% | 0% | 0% | 38% | 0% | 8.0 |

Pre-registered verdict: promotion criteria NOT satisfied. Safety held (no missed faults, no false faults), but the improvement the hybrid was built for could not appear, because the original netwing already answered all 30 healthy runs correctly. That suite did not contain the failing class (noise alerts plus a transient failure on a healthy network). The largest test saving came from the retest hint, not the hybrid acceptance. The suite also showed a separate problem: 28-44% of faulty-network answers in every mode listed an unsupported extra fault, which led to claim validation (see `04-fresh2-validation.md`).

## Limits
Simulator only; one model; thresholds and noise parameters unfitted; the belief model assumes independent readings; flaky faults that pass often are the main risk for any belief-based healthy rule.
