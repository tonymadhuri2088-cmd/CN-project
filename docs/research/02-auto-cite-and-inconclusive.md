# `--auto-cite` and `--allow-inconclusive` evaluation (22 Nov 2026)

All runs: Claude Haiku 5.5, simulator unless stated. Companion to `01-results-log.md`.

## `--auto-cite`: simulator safety check (10 repeats per scenario)
Question: does the flag bring back false alarms or lower accuracy anywhere?

| Suite | Mode | Runs | Correct [95% CI] | False alarms | No answer | Mean tests |
|---|---|---|---|---|---|---|
| Hard | plain | 40 | 78% [62-88] | 90% [60-98] | 0 | 11.2 ±0.3 |
| Hard | healthy_ok | 40 | 80% [65-90] | 80% [49-94] | 0 | 11.2 ±0.3 |
| Hard | netwing `--auto-cite` | 40 | 100% [91-100] | 0% [0-28] | 0 | 8.2 ±0.7 |
| Flaky | plain | 20 | 80% [58-92] | 40% [17-69] | 0 | 11.8 ±0.2 |
| Flaky | healthy_ok | 20 | 95% [76-99] | 10% [2-40] | 0 | 11.4 ±0.4 |
| Flaky | netwing `--auto-cite` | 20 | 100% [84-100] | 0% [0-28] | 0 | 9.3 ±1.1 |
| Multi | plain | 20 | 100% [84-100] | n/a | 0 | 9.6 ±0.7 |
| Multi | healthy_ok | 20 | 100% [84-100] | n/a | 0 | 9.7 ±0.6 |
| Multi | netwing `--auto-cite` | 20 | 100% [84-100] | n/a | 0 | 6.7 ±0.8 |

Multi-fault "all faults found": plain 70% [48-85], healthy_ok 65% [43-82], netwing `--auto-cite` 90% [70-97].

Reading: with `--auto-cite` netwing matches the published default-rule results. The one number that moved is multi all-faults-found (90% vs 95%, 18 vs 19 of 20 runs); netwing's own multi results varied between 85% and 95% across runs, so this is within noise. Baselines also moved between runs, which is why 30+ repeats are needed. The flag stays opt-in.

## `--allow-inconclusive`: first real-model run (hard suite, 12 runs per mode)
| Mode | Runs | Correct [95% CI] | False alarms (healthy case) | No answer | Mean tests |
|---|---|---|---|---|---|
| plain | 12 | 75% [47-91] | 67% [21-94] | 1 | 11.4 ±0.7 |
| healthy_ok | 12 | 75% [47-91] | 33% [6-79] | 2 | 11.1 ±0.4 |
| netwing | 12 | 100% [76-100] | 0% [0-56] | 0 | 8.6 ±1.2 |

netwing was unaffected, so the option does not change the controller's behaviour and is not used as an escape hatch. The baselines produced 1-2 no-answers (inconclusive is scored as no answer), so the option is reachable by the model. With 12 runs and 3 healthy runs per mode this is a plausibility check, not evidence about how often "inconclusive" is right. A dedicated "insufficient evidence" scenario is still missing.
