# Results log: controller rules, simulator and real-network results

Model: Claude Haiku 5.5 (`claude-haiku-5-5`). Simulator runs use `--backend sim`, `--inventory` on, 10 repeats per scenario. Intervals are 95% Wilson (rates) and mean ± 1.96 SE (tests). Written 21-22 Nov 2026; later work is in the other documents in this folder.

## Controller rules in force (default; frozen)
1. Evidence ids are numbered E1..; every id in a claim must exist; one string may cite several ids.
2. Relevance: only results about the ticket's subject count as evidence.
3. A failure is cleared when the identical check later passes twice in a row (transient blip).
4. A fault is accepted only when the failure is confirmed (the identical check failed twice, or the same kind of failure appeared from a different check) AND ping, DNS and port were all tested. At budget exhaustion a confirmed fault is accepted even if an area is untried.
5. A ping or port check that failed only because the name did not resolve (category `dns`) does not count as having tested routing or ports.
6. The test budget is 12 for every mode (netwing, plain, healthy_ok).
7. The netwing prompt tells the model to confirm failures by repeating the same check and to try ping, DNS and port before answering.
8. `--inventory` (default on): one line in every mode's prompt saying which names are the same server.
9. A claim citing failures about an unrelated alert gets a specific rejection pointing the model to answer "healthy".

Opt-in layers, all off by default so every published table stays valid: `--allow-inconclusive`, `--guide-citations`, `--auto-cite`.

## Simulator results (all four suites, same code)
| Suite | Mode | Runs | Correct [95% CI] | False alarms (healthy case) | No answer | Mean tests | Mean cost |
|---|---|---|---|---|---|---|---|
| Easy | plain | 40 | 100% [91-100] | 0% [0-28] | 0 | 6.9 ±0.4 | $0.0013 |
| Easy | healthy_ok | 40 | 100% [91-100] | 0% [0-28] | 0 | 5.8 ±0.3 | $0.0011 |
| Easy | netwing | 40 | 100% [91-100] | 0% [0-28] | 0 | 5.5 ±0.5 | $0.0010 |
| Hard | plain | 40 | 80% [65-90] | 80% [49-94] | - | 11.0 | $0.0021 |
| Hard | healthy_ok | 40 | 78% | 90% [60-98] | - | - | - |
| Hard | netwing | 40 | 100% [91-100] | 0% [0-28] | 0 | 8.2 | $0.0014 |
| Flaky | plain | 20 | 65% [43-82] | 70% [40-89] | 0 | 11.7 ±0.4 | $0.0019 |
| Flaky | healthy_ok | 20 | 100% [84-100] | 0% [0-28] | 0 | 11.4 ±0.5 | $0.0019 |
| Flaky | netwing | 20 | 100% [84-100] | 0% [0-28] | 0 | 9.3 ±0.9 | $0.0014 |
| Multi | plain | 20 | 100% [84-100] | n/a | 0 | 10.3 ±0.5 | $0.0020 |
| Multi | healthy_ok | 20 | 100% [84-100] | n/a | 0 | 9.8 ±0.6 | $0.0019 |
| Multi | netwing | 20 | 100% [84-100] | n/a | 0 | 7.0 ±1.0 | $0.0014 |

Multi-fault "all faults found": plain 70% [48-85], healthy_ok 70% [48-85], netwing 95% [76-99].

Reading: the hard suite is the headline (netwing 100% correct, 0 false alarms, against baselines at 78-80% correct and 80-90% false alarms on the noisy healthy case, with about 25% fewer tests). Flaky: netwing matches healthy_ok on accuracy with about 18% fewer tests. Easy: all 100%. Multi: netwing finds all faults more often (95% vs 70%) with about 30% fewer tests.

## Real network (Linux network namespaces, WSL 2 Ubuntu; easy suite; 20 runs per mode)
Backend `NetnsNetwork` (kernel routing, firewalling, dnsmasq); parity-tested against the simulator.

| Run | Mode | Correct [95% CI] | False alarms | No answer | Mean tests |
|---|---|---|---|---|---|
| baseline | plain | 100% | 0% | 0 | 7.4 |
| baseline | healthy_ok | 95% | 20% (1 of 5 healthy runs) | 0 | 7.0 |
| baseline | netwing | 90% [70-97] | 0% | 2 | 5.6 ±0.7 |
| `--guide-citations` | netwing | 75% [53-89] | - | 5 | 5.3 ±0.6 |
| `--auto-cite` | plain | 100% [84-100] | 0% [0-43] | 0 | 7.2 ±0.7 |
| `--auto-cite` | healthy_ok | 95% [76-99] | 20% [4-62] | 0 | 7.3 ±0.9 |
| `--auto-cite` | netwing | 100% [84-100] | 0% [0-43] | 0 | 5.3 ±0.6 |

On the real network netwing used about 24-26% fewer tests than plain, with non-overlapping intervals. The two baseline no-answers came from the controller rejecting correct diagnoses when the model cited exclusion evidence. `--guide-citations` made this worse; `--auto-cite` removed it. Caveats: `--auto-cite` was designed after seeing these failures on this suite; only 5 healthy runs per mode.

## Lab suite (simulator only; 12 runs per mode)
`lab_high_latency`, `lab_packet_loss`, `lab_misleading_dns`, `lab_misleading_healthy`: all modes 100% correct; netwing used fewer tests (5.4 vs 7.2-7.4) but intervals overlap, so this is a direction, not a proven effect.

## What failed and why (kept for honesty)
- Flaky, first confirm-twice rule with an 8-test budget: netwing 30% correct, 14 of 20 no answer. Fixed with an equal 12-test budget, prompt guidance and reading string evidence correctly.
- Multi, first run: netwing found all faults 15% (plain 75%); the model stopped when DNS failed because ping and port failures to `web.lab` were only name-resolution failures. Rule 5 added.
- Multi without the inventory line: netwing 20% correct; the model could not know `web.lab` is also h2 / 10.0.2.10. Inventory line added (given to all modes).
- Multi, route fault seen from several vantage points never repeated the identical check: "different check, same area" confirmation added.
- No-answers at budget exhaustion when only an area was untried: accept a confirmed fault at the cap.
- Hard suite no-answers on the noisy healthy case: specific rejection message added.
- Real network: correct diagnoses rejected over the cited ids; `--auto-cite` added.

## Honest limits
Rules were tuned on these scenarios over several rounds, so held-out and fresh suites were added (see the other documents). Baseline false-alarm rates swing between runs (plain flaky: 0%, 10%, 70% in different runs); 30+ repeats are needed to quote them. One model. The real network covers the easy suite only; the Kathara backend has never been run on real Docker.
