# NetWing

[![CI](https://github.com/tonymadhuri2088-cmd/CN-project/actions/workflows/ci.yml/badge.svg)](https://github.com/tonymadhuri2088-cmd/CN-project/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
![Tests](https://img.shields.io/badge/tests-316%20passing-brightgreen)
![Types](https://img.shields.io/badge/mypy-clean-brightgreen)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

**An evidence-sufficiency controller for LLM network-diagnosis agents.**
It answers one question: *does the agent have enough evidence to conclude, or is it about to invent a fault?*

LLM troubleshooting agents are known to "find" a fault on a network that is actually healthy. NetWing sits between the
agent and its conclusion. It numbers every test result, refuses a fault claim that is not backed by a reproduced failure
about the ticket's target, refuses "healthy" before the evidence supports it, and stops the run once the evidence is
sufficient or the test budget is spent. The controller is a transparent rule engine, not another model, so every
decision can be audited.

```
ticket -> agent (Claude + tools) -> test results -> Controller (evidence ids E1..)
                                                      |-- relevance:     only results about the ticket's target count
                                                      |-- blip clearing: a failure is cleared when the same check then passes twice
                                                      |-- confirmation:  same check fails twice, or same area from another check
                                                      |-- coverage:      ping, DNS and port all tried (DNS-masked checks don't count)
                                                      |-- budget:        12 tests, then stop
                                                      `-- verdict:       CONTINUE / STOP_FAULT / STOP_HEALTHY / STOP_CAP
```

## Results at a glance
Claude Haiku 5.5, simulated network, same 12-test budget for every mode, 95% Wilson intervals. `healthy_ok` is the strong
prompt-only baseline ("the network may be healthy"). Full tables: [docs/research](docs/research/).

| Suite (runs per mode) | plain | healthy_ok | **netwing** |
|---|---|---|---|
| Hard, noisy alerts (40): correct / false alarms / tests | 80% / 80% / 11.0 | 78% / 90% / n/a | **100% / 0% / 8.2** |
| Flaky (20): correct / false alarms / tests | 65% / 70% / 11.7 | 100% / 0% / 11.4 | **100% / 0% / 9.3** |
| Multi-fault (20): all faults found / tests | 70% / 10.3 | 70% / 9.8 | **95% / 7.0** |
| Real Linux network, easy (20): tests | 7.2 | 7.3 | **5.3** (with `--auto-cite`) |

What is **not** claimed: that NetWing improves multi-fault detection in general, or that it eliminates hallucinated
diagnoses. Rules were first tuned on these suites, so later results come from **frozen, pre-registered** suites
(held-out, fresh2, fresh3). Those showed one confirmed improvement (opt-in hybrid + retest hint: healthy networks
answered correctly 13% to 97%) and several honest negatives (strict claim validation, tiered claims). Read
[the project history](docs/PROJECT_HISTORY.md) for the full story.

## Quick start (Python 3.10+, no API key needed)
```bash
pip install -e ".[dev]"
pytest                                  # 316 passed, 4 skipped (real-lab parity)
python -m netwing.demo --dry-run        # whole pipeline with a scripted stub: zero API spend
python -m netwing.webui --results results --port 8765   # investigation UI at http://127.0.0.1:8765
```
Real model run on the **simulated** network (set the key in your shell, never in a file):
```bash
pip install anthropic
export ANTHROPIC_API_KEY=...            # PowerShell: $env:ANTHROPIC_API_KEY = "..."
python -m netwing.demo --backend sim --suite hard --repeats 3 --cap 3
```
`--cap` is a hard USD limit; a run that would pass it stops and is marked INCOMPLETE. Real network labs (Linux
namespaces, Kathara): see [SETUP_LINUX.md](SETUP_LINUX.md).

## What is in the repository
| Path | Contents |
|---|---|
| `netwing/controller.py` | The research core: evidence ledger, stop rules, claim gate |
| `netwing/agent.py`, `runner.py`, `demo.py` | Diagnosis loop, experiment matrix, CLI |
| `netwing/sim.py`, `netns.py`, `kathara.py` | Backends: simulator, real Linux namespaces, Kathara labs |
| `netwing/scenarios.py`, `scoring.py` | Scenario suites with ground truth; deterministic scoring (no LLM judge) |
| `netwing/belief.py`, `belief_report.py`, `strategy_replay.py` | Bayesian belief and information gain; offline analysis of saved logs |
| `netwing/final_report.py` | Per-configuration metrics tables with Wilson intervals |
| `netwing/webui.py`, `records.py`, `health.py`, `history.py`, `report.py`, `pdfexport.py` | Investigation UI, evidence explorer, health score, history, HTML and PDF reports |
| `tests/` | 316 tests with a fake LLM client; frozen suites are pinned by tests |
| `docs/` | [Project history](docs/PROJECT_HISTORY.md), [research results](docs/research/), [full reference](docs/REFERENCE.md) |
| `results/` | Raw JSONL run logs (frozen logs are committed) |

## Experiment integrity
- **Opt-in everything.** Defaults are the published rules; every later layer (`--auto-cite`, `--healthy-strategy hybrid`,
  `--retest-hint`, `--validate-claims`, `--tier-claims`, `--allow-inconclusive`) is off unless requested, so no published
  table changes.
- **Freeze, then run.** Validation suites and acceptance criteria are committed before evaluation; a criterion is never
  changed after results exist.
- **Negative results are reported**, and corrections are recorded as errata rather than silent edits.
- **Deterministic scoring** from scenario ground truth; costs capped and logged per run.
- Logs append and runs stop on API errors, so a file can hold several invocations: analyse per invocation and say which.

## Honest limits
One model (Haiku 5.5); most suites are simulator-only; the real network covers the easy suite; the Kathara backend has
never been run on real Docker; run-to-run variance is large (about 20 points between behaviourally identical
configurations on multi-fault recall), so quote rates per suite and use 15-30 repeats. The controller stops once one
fault is confirmed, so a second fault is confirmed only if the agent happens to test its area twice; a
completeness-aware design is analysed in [docs/research/06](docs/research/06-dcc-architecture-audit.md) but not built.

## Roadmap
Second model; 30+ repeats; real-network hard and lab scenarios; completeness-aware controller on a new pre-registered
suite; human-labelled evaluation; paper.

## Development
```bash
pip install -e ".[dev,lint,typecheck]"
ruff check netwing tests && mypy && pytest
```
CI runs lint, type check, tests and a dry-run on Python 3.10-3.13, plus a Docker build. The container image serves the UI.

For details (every flag, suite, the UI, the real-network setup) see [docs/REFERENCE.md](docs/REFERENCE.md).
