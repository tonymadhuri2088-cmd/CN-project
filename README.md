# NetWing

An **evidence-sufficiency controller** for LLM network-diagnosis agents. Question it answers:
*does the agent have enough evidence to conclude, or is it about to invent a fault?*

Why it matters: published benchmarks report that LLM troubleshooting agents often "find" a fault on a
network that is actually healthy. NetWing sits between the agent and its conclusion: it refuses a fault
claim that cites no failing test, refuses "healthy" before anything passed, and stops the agent once the
evidence is enough (or a test budget is hit).

## Technical stack

| Layer | Technology | Status |
|---|---|---|
| Language / packaging | Python 3.10+, setuptools (`pyproject.toml`), editable install | Built |
| LLM | Anthropic Messages API, Claude Haiku 5.5 (`claude-haiku-5-5`), tool use with thinking blocks passed back; model overridable with `NETWING_MODEL` | Built |
| Controller | Pure-Python rule engine (`netwing/controller.py`): numbered evidence ids, relevance filter, transient-blip clearing, confirmation, area coverage, test budget | Built |
| Network backends | `SimNetwork` (deterministic simulator, labeled SIMULATED), `NetnsNetwork` (Linux network namespaces: iproute2, dnsmasq, netcat, iptables, dig, traceroute), `KatharaNetwork` (Docker-based Kathara labs) | Sim and netns built and parity-tested; Kathara written, not yet run on real Docker |
| Diagnostic tools exposed to the agent | ping, DNS lookup (dig), TCP port check (nc), traceroute / routing check | Built |
| Experiment runner | `netwing/runner.py`: matrix of scenarios x modes x repeats, equal 12-test budget per mode, JSONL log per run | Built |
| Statistics | 95% Wilson intervals (correct, false alarms, all faults found), mean +/- 1.96 SE for tests, cost per run | Built |
| Cost control | Hard USD cap (`--cap`), per-model token prices in `netwing/pricing.json`, run marked INCOMPLETE if the cap would be passed | Built |
| Testing | pytest, 226 tests, fake LLM client (`tests/fake_client.py`), dry-run stub so the whole pipeline runs with zero API spend | Built |
| Console commands | `netwing` (experiments) and `netwing-ui` (web UI) installed by `pip install -e .`; also runnable as `python -m netwing.demo` / `python -m netwing.webui` | Built, install tested in a clean virtualenv |
| Lint | ruff (optional: `pip install -e ".[lint]"`; pyflakes and syntax checks in `pyproject.toml`), `requirements.txt` / `requirements-dev.txt` | Built, passes |
| Continuous integration | GitHub Actions (`.github/workflows/ci.yml`): lint, 226 tests and a dry-run of the pipeline on Python 3.10-3.13, no API key needed | Passed on Python 3.10-3.13, including the Docker build and a smoke test of the UI image (runs #1 and #2) |
| Containerisation | `Dockerfile` for the web UI (history, reports, simulator runs) | Built and smoke-tested in CI (the UI answers from inside the container); real Kathara/netns labs are not containerised |
| Lab automation | Bash setup scripts (`setup_linux.sh`, `run_real_lab.sh`), fault-injection script (`labs/inject.sh`) | Built |

### Mini Project 2 layer (built; does not change diagnosis behaviour)
| Layer | Technology | Status |
|---|---|---|
| Structured per-test record (tool, args, output, pass/fail, category, timestamp) | Additive `tests` field in the run log (`netwing/agent.py`); older logs are rebuilt from the transcript | Built |
| Evidence explorer records | `netwing/records.py` | Built |
| Network health score from measured values only (unmeasured indicators shown separately, never assumed healthy) | `netwing/health.py` | Built |
| Persistent investigation history, filter and compare | SQLite (stdlib) in `netwing/history.py`, imports `results/run-*.jsonl` | Built |
| Report export (problem, tests, observations, root cause, evidence, limitations, recommendations) | Standalone HTML (`netwing/report.py`) and a native PDF writer with no third-party library (`netwing/pdfexport.py`; `?format=pdf` on the report URL, a button on each run page) | Built |
| Evidence assurance: Confirmed / Suspected / Inconclusive per investigation | `Controller.assess` (read-only: replays the recorded tests through the controller's own rules); shown on the run page, HTML report and PDF. Older logs without recorded test categories are shown as "not assessed" | Built |
| Opt-in "inconclusive" answer | `--allow-inconclusive` adds an `inconclusive` verdict (gated: at least 3 tests, and not allowed when a confirmed fault or a fully passing network stands). Off by default, so every published result is unchanged. Scored as no answer, never as a false alarm | Built; one small real-model run (12 runs per mode on the hard suite) |
| Opt-in citation helpers | `--guide-citations` (a rejection names the citable failing ids) and `--auto-cite` (accept a fault claim backed by standing failures in the matching area even if the model cites other ids; still needs reproduction, all areas tried, existing ids and relevance). Both off by default, so every published result is unchanged | `--guide-citations` built and measured (did not help); `--auto-cite` measured: on the simulator it kept netwing's results (hard 100% / 0% false alarms / 8.2 tests, flaky 100% / 0% / 9.3, multi 100% correct, 90% all faults found / 6.7 tests), and on the real network it removed netwing's no-answers (see results below). `--allow-inconclusive` measured on the hard suite (12 runs): netwing unchanged at 100% / 0% false alarms, baselines gave 1-2 no-answers |
| Web UI: history, investigation detail, compare, simulation lab with ground truth | Python stdlib `http.server`, `netwing/webui.py`, no extra dependencies | Built |

Run the UI: `python -m netwing.webui --results results --port 8765`, then open http://127.0.0.1:8765
(history with per-mode totals, evidence explorer with health bar, compare, report, simulation lab, and a **Run investigation** page that starts a simulator run, real model if an API key is set in that window, otherwise a dry-run stub that is clearly flagged).

### Lab suite (Mini Project 2, simulator only)
`python -m netwing.demo --backend sim --suite lab --repeats 3 --cap 3` runs four extra scenarios with ground truth: `lab_high_latency`, `lab_packet_loss`, `lab_misleading_dns` (ticket says the server is down; the real fault is DNS), `lab_misleading_healthy`. Only these scenarios offer `high_latency` and `packet_loss` as answers; the experiment suites keep exactly the same tools and prompts. `--suite all` does not include the lab.

### Held-out suite (simulator only; built, not yet run)
`python -m netwing.demo --backend sim --suite heldout --repeats 10 --cap 3` runs eight scenarios that no controller rule or prompt was tuned on: the noise alerts combined with a one-off blip or an intermittent port or two faults at once (`ho_noisy_blip`, `ho_noisy_flaky_port`, `ho_noisy_multi_dns_port`, `ho_noisy_multi_dns_route`), a persistent DNS fault behind the "intermittent" ticket (`ho_flaky_dns`), and the bigger campus network with noise and double faults (`ho_campus_noisy_healthy`, `ho_campus_noisy_route`, `ho_campus_multi_dns_port`). Two of the eight are healthy cases. Protocol: run it once on frozen code with the default rules and report whatever comes out; never change a rule after looking at these results (`--auto-cite` is evaluated separately as an opt-in layer). `--suite all` does not include it, and it refuses the real backends.

### Planned (not built yet)
Lab scenarios on the real Kathara/netns backends; confirming `--auto-cite` on held-out scenarios and more repeats; a second model; 30+ repeats; running the held-out suite (built) and its report; building and testing the Docker image locally (CI now builds it).

### Lab suite results (Haiku 5.5, simulated, 12 runs per mode, 21 Nov 2026)
| Mode | Correct [95% CI] | False alarms | Mean tests | Mean cost |
|---|---|---|---|---|
| plain | 100% [76-100] | 0% [0-56] | 7.2 ±1.5 | $0.0012 |
| healthy_ok | 100% [76-100] | 0% [0-56] | 7.4 ±1.6 | $0.0012 |
| netwing | 100% [76-100] | 0% [0-56] | 5.4 ±0.8 | $0.0010 |

All modes answered every lab scenario correctly, so there is no accuracy difference here. netwing used fewer tests, but with 12 runs the intervals overlap slightly: read it as a consistent direction, not a proven effect. The lab healthy case has only 3 runs per mode, so no false-alarm claim is made from this suite.

## Architecture

```
ticket -> agent (Claude + tools) -> test results -> Controller (evidence ids E1..)
                                                      |-- relevance: only results about the ticket's target count
                                                      |-- blip clearing: failure cleared if same check then passes twice
                                                      |-- confirmation: same check fails twice, or same area from another check
                                                      |-- coverage: ping, DNS and port all tried (DNS-masked checks don't count)
                                                      |-- budget: 12 tests, then stop
                                                      `-- verdict: CONTINUE / STOP_FAULT / STOP_HEALTHY / STOP_CAP
```
A fault claim is accepted only if it cites existing evidence ids that show a confirmed failure about the ticket's target.
A healthy claim is accepted only if nothing relevant is failing and at least one check passed. A rejected claim gets a
specific message saying what is missing, and the agent keeps testing.

## Results so far (Claude Haiku 5.5, SIMULATED network, `--inventory` on)

| Suite | plain | healthy_ok | netwing |
|---|---|---|---|
| Easy (40 runs) | 100%, 6.9 tests | 100%, 5.8 | 100%, 5.5 |
| Hard (40 runs) | 80% correct, 80% false alarms, 11.0 tests | 78%, 90% false alarms | 100%, 0% false alarms, 8.2 tests |
| Flaky (20 runs) | 65%, 70% false alarms, 11.7 tests | 100%, 0%, 11.4 | 100%, 0%, 9.3 |
| Multi (20 runs) | 70% find all faults, 10.3 tests | 70%, 9.8 | 95%, 7.0 |

These are a demo on a simulator with a single model, not final paper evidence (see Honest limits).

## Three diagnosers compared
| Mode | What it is |
|---|---|
| `plain` | Claude with a normal "diagnose the problem in the ticket" prompt |
| `healthy_ok` | Same, plus "the network may be healthy" (the strong prompt-only baseline NetWing must beat) |
| `netwing` | `healthy_ok` prompt + the controller (evidence gate + early stop + test cap) |

Scenario suites: three real faults (`dns_failure`, `route_failure`, `port_blocked`) and `healthy_false_alarm`
(ticket claims an outage, network is fine).

## Run it (Windows, macOS or Linux; Python 3.10+)
```
pip install -e ".[dev]"
pytest                                   # 226 tests, no API needed
python -m netwing.demo --dry-run         # whole pipeline, zero API spend (stub client)
```
Real model run on the **simulated** network (set the key in your shell, never in a file or chat):
```
pip install anthropic
# PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
# bash:        export ANTHROPIC_API_KEY=sk-ant-...
python -m netwing.demo --backend sim --repeats 2 --cap 3
```
Default model `claude-haiku-5-5` (override with `NETWING_MODEL`). `--cap` is a hard USD limit; a run that
would pass it is stopped and the table says INCOMPLETE. Token prices are in `netwing/pricing.json`.
Logs: one JSON line per run in `results/` (these are reused for the paper).

Real emulated lab (Linux + Docker only): see `SETUP_LINUX.md`.

## Honest limits (read before showing numbers)
- Results on the simulated network are labeled SIMULATED and are a demo, **not** paper evidence.
- Only four tiny scenarios. The paper needs more fault types, held-out topologies, repeated runs with
  confidence intervals, and human-checked labels.
- LLM runs are noisy: use `--repeats 3` or more before drawing any conclusion.
- The premise (plain Claude over-diagnoses a healthy network) is **unverified** until the first real run.
  If `plain` never false-alarms, say so; do not hide it.
- The Kathara backend and labs are written but not yet run on real Docker (see `SETUP_LINUX.md`).

## Hard suite (red-herring alerts)

`python -m netwing.demo --backend sim --suite hard --repeats 3 --cap 3`

Same four cases, but the ticket also lists three unrelated alerts (printer.lab DNS timeout, h2:8080 filtered,
decommissioned 10.0.3.10). The ticket is identical for healthy and faulty cases. NetWing's controller only counts
a failure as evidence when it concerns the ticket's target (web.lab / 10.0.2.10 / h2, port 80).

## All suites

| `--suite` | What it adds |
|---|---|
| `easy` (default) | DNS fault, route fault, blocked port, healthy |
| `hard` | same four plus three unrelated alerts in the ticket |
| `flaky` | `transient_blip` (healthy; one ping lost) and `intermittent_port` (web port alternates filtered/open) |
| `multi` | two faults at once (`multi_dns_port`, `multi_dns_route`); the table adds "All faults found" |
| `campus` | the same four cases on 4 hosts, 2 routers, 3 services |
| `all` | everything |

The summary shows 95% Wilson confidence intervals. Use `--repeats 10` or more for numbers you can quote.

### Simulator safety check for `--auto-cite` (netwing mode, Haiku 5.5, `--cap 3`)
| Suite | Runs | Correct [95% CI] | False alarms | No answer | Mean tests | Published default rules |
|---|---|---|---|---|---|---|
| Hard | 40 | 100% [91-100] | 0% [0-28] | 0 | 8.2 +/- 0.7 | 100%, 0%, 8.2 |
| Flaky | 20 | 100% [84-100] | 0% [0-28] | 0 | 9.3 +/- 1.1 | 100%, 0%, 9.3 |
| Multi | 20 | 100% [84-100] | n/a | 0 | 6.7 +/- 0.8 (all faults found 90% [70-97]) | 100%, 7.0 (95%) |

The flag did not change the results beyond run-to-run noise (multi all-faults-found 90% vs 95% earlier is 18 vs 19 of 20 runs; netwing's own multi results have varied between 85% and 95%). Baselines moved between runs (e.g. plain flaky false alarms 40% now vs 70% before), which is why 30+ repeats are needed for baseline numbers.

## Real network, no Docker (Linux, root)

`sudo apt install iproute2 dnsmasq netcat-openbsd dnsutils iputils-ping traceroute iptables`
then `sudo env "PATH=$PATH" ANTHROPIC_API_KEY=... python -m netwing.demo --backend netns --suite easy --repeats 3 --cap 3`.
It builds the lab as Linux network namespaces and runs the lab's own startup scripts; the kernel does the routing,
firewalling and DNS. Check that it agrees with the simulator: `sudo NETWING_REAL_LAB=1 python -m pytest tests/test_netns_parity.py -q`.
This does not test Kathara or its Docker image. Only the `easy` suite has a real lab so far.

### Real-network results (easy suite, 20 runs per mode, Claude Haiku 5.5, Linux namespaces)
| Mode | Correct (95% CI) | False alarms | No answer | Mean tests |
|---|---|---|---|---|
| plain | 100% | 0% | 0 | 7.4 |
| healthy_ok | 95% | 20% (1 of 5 healthy runs) | 0 | 7.0 |
| netwing | 90% [70-97] | 0% | 2 | 5.6 +/- 0.7 |

Solid claim: about 24% fewer tests with netwing, intervals not overlapping. Accuracy differences are not separable at this sample size, and 5 healthy runs per mode are too few for false-alarm claims. Finding: netwing's no-answers come from the controller rejecting correct diagnoses when the model cites exclusion evidence (passing tests or another area's failure). With `--guide-citations` this got worse (75% correct, 5 no-answers), so `--auto-cite` was added.

With `--auto-cite` (same real network, easy suite, 20 runs per mode; log `results/run-20261121-202321.jsonl`):
| Mode | Correct (95% CI) | False alarms | No answer | Mean tests |
|---|---|---|---|---|
| plain | 100% [84-100] | 0% | 0 | 7.2 +/- 0.7 |
| healthy_ok | 95% [76-99] | 20% (1 of 5 healthy runs) | 0 | 7.3 +/- 0.9 |
| netwing `--auto-cite` | 100% [84-100] | 0% | 0 | 5.3 +/- 0.6 |

netwing's no-answers fell from 2 to 0 and it used about 26% fewer tests than plain. Safety check on the simulator hard suite (12 runs per mode): netwing 100% correct, 0% false alarms, 8.3 tests, same as the published run. Caveats: the flag was designed after seeing these failures on the same suite, n=20, and only 5 healthy runs per mode, so the false-alarm interval is wide. It stays opt-in; the published default tables are unchanged.
