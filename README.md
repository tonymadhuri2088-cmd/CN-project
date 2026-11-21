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
| Testing | pytest, 178 tests, fake LLM client (`tests/fake_client.py`), dry-run stub so the whole pipeline runs with zero API spend | Built |
| Lab automation | Bash setup scripts (`setup_linux.sh`, `run_real_lab.sh`), fault-injection script (`labs/inject.sh`) | Built |

### Mini Project 2 layer (built; does not change diagnosis behaviour)
| Layer | Technology | Status |
|---|---|---|
| Structured per-test record (tool, args, output, pass/fail, category, timestamp) | Additive `tests` field in the run log (`netwing/agent.py`); older logs are rebuilt from the transcript | Built |
| Evidence explorer records | `netwing/records.py` | Built |
| Network health score from measured values only (unmeasured indicators shown separately, never assumed healthy) | `netwing/health.py` | Built |
| Persistent investigation history, filter and compare | SQLite (stdlib) in `netwing/history.py`, imports `results/run-*.jsonl` | Built |
| Report export (problem, tests, observations, root cause, evidence, limitations, recommendations) | Standalone HTML in `netwing/report.py` (print to PDF from the browser) | Built |
| Web UI: history, investigation detail, compare, simulation lab with ground truth | Python stdlib `http.server`, `netwing/webui.py`, no extra dependencies | Built |

Run the UI: `python -m netwing.webui --results results --port 8765`, then open http://127.0.0.1:8765

### Planned (not built yet)
High-latency, packet-loss and misleading-complaint scenarios (need simulator and scoring changes, held until the experiment tables are final); an "inconclusive" verdict; latency and packet-loss numbers as structured measurements; running new investigations from the UI; PDF export without the browser.

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
pytest                                   # 178 tests, no API needed
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

## Real network, no Docker (Linux, root)

`sudo apt install iproute2 dnsmasq netcat-openbsd dnsutils iputils-ping traceroute iptables`
then `sudo env "PATH=$PATH" ANTHROPIC_API_KEY=... python -m netwing.demo --backend netns --suite easy --repeats 3 --cap 3`.
It builds the lab as Linux network namespaces and runs the lab's own startup scripts; the kernel does the routing,
firewalling and DNS. Check that it agrees with the simulator: `sudo NETWING_REAL_LAB=1 python -m pytest tests/test_netns_parity.py -q`.
This does not test Kathara or its Docker image. Only the `easy` suite has a real lab so far.
