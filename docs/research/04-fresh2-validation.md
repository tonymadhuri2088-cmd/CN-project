# fresh2: second independent validation (claim validation and hybrid + hint)

Simulator, `claude-haiku-5-5`, suite `fresh2` (7 scenarios), run 23-24 Nov 2026. The suite was frozen in commit `a0b68cf` and the criteria below were written before any run. No tuning on the results.

## Pre-registration (written before the run)
Frozen: suite `fresh2` (`netwing/scenarios.py::_FRESH2`, pinned by `tests/test_fresh2_suite.py`), the default rules, the hybrid rule (tau 0.85), the retest hint and the belief model. Claim validation is a new opt-in flag (`--validate-claims`).

Configurations (netwing mode, 15 repeats, cap 3 USD each): (1) original; (2) hybrid + retest hint; (3) validate-claims; (4) hybrid + hint + validate-claims.

Acceptance criteria:
- **A, claim validation vs original:** a candidate default only if unsupported extra-fault claims on faulty networks drop by at least 15 points; exact diagnosis, missed faults and false alarms do not get worse beyond overlapping CIs; multi-fault completeness on `fx2_campus_noisy_multi_dns_port` does not fall more than 20 points; the no-answer rate is unchanged.
- **B, hybrid + hint vs original:** a candidate only if healthy accuracy on the two noisy+blip healthy scenarios improves with non-overlapping CIs; missed faults and false alarms do not increase; no-answer rate does not increase; mean tests within +1.
- **C, combination:** reported, promoted only if A and B both pass.

Known limits: simulator only, one model, 7 scenarios; `fx2_noisy_blip` replicates a held-out failing class, so it is a replication rather than fully independent.

## Data handling (deviation, disclosed)
The run block appended to its log files and the matrix stops on an API connection error, so the files hold several invocations of the same configuration. Primary analysis = the last intact invocation of each configuration (original 101 netwing runs; the other three 105 runs = 15 repeats). Pooling every invocation is the sensitivity check and gives the same conclusions. All raw files are preserved.

## Results (netwing mode, Wilson 95% CIs)
| Config | Runs | Exact diagnosis | Healthy answered healthy (30 runs) | False fault | Missed fault | Extra fault claimed | No answer | Multi exact (15) | Mean tests | Cost/run |
|---|---|---|---|---|---|---|---|---|---|---|
| original | 101 | 31% [23-40] | 13% [5-30] | 0% | 0% | 56% [45-67] | 29% [21-38] | 93% [69-99] | 10.0 | $0.0022 |
| hybrid + hint | 105 | 65% [55-73] | 97% [83-99] | 0% | 0% | 44% [33-55] | 2% [1-7] | 87% [62-96] | 8.5 | $0.0018 |
| validate-claims | 105 | 59% [49-68] | 10% [3-26] | 0% | 0% | 0% [0-5] | 29% [21-38] | 13% [4-38] | 9.9 | $0.0022 |
| hybrid + hint + validate | 105 | 85% [77-90] | 100% [89-100] | 0% | 0% | 0% [0-5] | 2% [1-7] | 0% [0-20] | 8.7 | $0.0018 |

Baselines (last original invocation): plain 89% correct with 37% false alarms on healthy networks; healthy_ok 84% correct with 53% of healthy runs answered correctly.

## Verdict against the pre-registered criteria
- **B (hybrid + hint): criteria met.** Healthy accuracy 13% to 97% with non-overlapping CIs; false alarms and missed faults stay 0%; no-answer 29% to 2%; mean tests 10.0 to 8.5. Caveats: only 30 healthy runs; the scenario replicates the class the hybrid was designed around; simulator, one model. The default is NOT changed; hybrid + hint stays opt-in and is the recommended optional configuration.
- **A (validate-claims): criteria NOT met.** Unsupported extra-fault claims fall from 56% to 0% with no new false alarms or misses, but multi-fault exact completeness falls from 93% to 13% (limit: 20 points). Not promoted.
- **C (combination): not promoted** because A fails. Its 85% exact diagnosis comes only from never reporting a second fault: 0 of 15 multi-fault runs are exact.

## Why validation loses real second faults
In the 15 DNS+port runs the model did claim `port_blocked`, but only 2 of 15 had it confirmed; 13 were "suspected" because the port failure was seen once, since the budget goes to confirming the primary DNS fault. The rule does what it was written to do (a once-seen failure may be a blip); the cost is recall on legitimate second faults. In the other faulty scenarios 35 of 36 dropped claims were truly unsupported.

## Proposed next step
Report suspected secondary claims separately instead of dropping them. That is a design change and needs a new frozen suite (done in fresh3, see `05-fresh3-tiered-claims.md`).
