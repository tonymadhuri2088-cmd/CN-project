# NetWing Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working demo, runnable in minutes, showing that a plain Claude network-diagnosis agent invents faults on a healthy network while NetWing (an evidence-sufficiency controller) does not, using fewer tests and no loss on real faults.

**Architecture:** An LLM diagnosis agent calls network tools through a `NetworkBackend` interface. Two backends: `SimNetwork` (pure Python, runs anywhere, labeled SIMULATED) and `KatharaNetwork` (real emulated lab, Linux only). Three agent modes (`plain`, `healthy_ok`, `netwing`) share one loop; only `netwing` adds the rule-based `Controller` that gates fault claims on evidence and stops the agent when evidence is sufficient. A `CostGuard` enforces a hard USD cap. A runner executes scenarios x modes x repeats, logs JSONL, and prints one results table.

**Tech Stack:** Python 3.10+, `anthropic` SDK, `pytest`. Kathará + Docker only for Task 7 (Linux).

**Spec:** Project doc `claude/netwing-paper-design.md` (Project "CN project Tony"). Demo-first ordering and the reduced API cap come from the user's latest messages; the design doc's old $15/$50/$20/$15 budget split is superseded.

## Global Constraints

- Python 3.10+; runtime deps only `anthropic`; test dep only `pytest`.
- API key only from env var `ANTHROPIC_API_KEY`; never written to files, logs or chat.
- Default model from env `NETWING_MODEL`, default `claude-haiku-5-5`.
- Hard USD cap: total default `15.00`, per run default `0.50`; exceeding either raises `BudgetExceeded` and stops the matrix cleanly.
- Token prices live in `netwing/pricing.json` and must be filled from Anthropic's pricing page before the first real call; no price is guessed in code. Missing price for the model = refuse to make real calls.
- Scenario ids are exactly: `dns_failure`, `route_failure`, `port_blocked`, `healthy_false_alarm`.
- Agent modes are exactly: `plain`, `healthy_ok`, `netwing`.
- `final_answer` tool schema: `{"verdict": "fault"|"healthy", "fault_type": "dns_failure"|"route_failure"|"port_blocked"|"none", "evidence": ["E1", ...]}`.
- Max tool calls per run: 12 for `plain` and `healthy_ok`; 8 for `netwing`.
- Every output produced from `SimNetwork` carries the word `SIMULATED`.
- One JSONL line per run in `results/`; the same logs feed the later paper.
- Git commits need file-deletion permission on the connected folder (git lock files); request it once at Task 1 Step 1.

## Review Focus

- API response has no usage data: guard must count a conservative estimate, not zero.
- Agent never calls `final_answer` within the cap: run is recorded `no_answer`, scored incorrect, no crash.
- Tool called with an unknown host or bad port: returns `ok=False` with category `invalid`, which can never count as fault evidence.
- Claude emits several `tool_use` blocks in one turn: every block gets a `tool_result` and each counts against the test cap.
- Budget exceeded or API key missing mid-matrix: partial logs are saved and the summary says the run is incomplete.

---

### Task 1: Project skeleton, scenarios, SimNetwork

**Files:**
- Create: `netwing/__init__.py`, `netwing/scenarios.py`, `netwing/backend.py`, `netwing/sim.py`, `pyproject.toml`, `tests/test_sim.py`

**Interfaces:**
- Produces: `ToolResult(tool:str, args:dict, output:str, ok:bool, category:str)` dataclass (category in `connectivity|dns|port|routing|invalid`); `NetworkBackend` Protocol with `ping(src,dst)`, `traceroute(src,dst)`, `dns_lookup(src,name)`, `port_check(src,dst,port:int)`, `show_routes(node)`, each returning `ToolResult`; `Scenario(id, ticket, truth, topology, faults)` frozen dataclass; `get_scenario(id:str)->Scenario`; `ALL_IDS: list[str]`; `SimNetwork(scenario)` implementing `NetworkBackend`.

- [ ] **Step 1:** Request delete permission once for the folder (needed by git), then `git init` and add `pyproject.toml` with the `anthropic` dependency and `pytest` config.
- [ ] **Step 2: Write failing tests** in `tests/test_sim.py`:
  - `test_healthy_all_tests_pass`: for `healthy_false_alarm`, `ping("h1","h2").ok`, `dns_lookup("h1","web.lab").ok` and `port_check("h1","h2",80).ok` are all True.
  - `test_dns_failure_only_dns_fails`: in `dns_failure`, `dns_lookup(...).ok` is False with `category=="dns"` while `ping("h1","h2").ok` is True.
  - `test_route_failure_ping_and_traceroute_fail`: in `route_failure`, ping fails with category `connectivity`; `show_routes("r1").output` contains no route to h2's subnet.
  - `test_port_blocked_only_port_fails`: ping ok, `port_check("h1","h2",80).ok` False with category `port`.
  - `test_unknown_host_is_invalid`: `ping("h1","nope")` returns `ok=False`, `category=="invalid"`.
  - `test_sim_outputs_marked_simulated`: every `output` ends with the line `[SIMULATED]`.
- [ ] **Step 3: Run** `pytest tests/test_sim.py -v`. Expected: FAIL (modules missing).
- [ ] **Step 4: Implement** the files above. Topology: hosts h1,h2, router r1, DNS name `web.lab` -> h2. Each scenario's `ticket` text: three real-fault tickets describe the symptom ("users cannot reach web.lab"), and `healthy_false_alarm` has a ticket that wrongly claims "web.lab is down" while everything works. Faults are a small dict the sim consults per tool.
- [ ] **Step 5: Run** `pytest tests/test_sim.py -v`. Expected: PASS.
- [ ] **Step 6: Commit** `git add . && git commit -m "feat: scenarios and simulated network"`

### Task 2: CostGuard

**Files:**
- Create: `netwing/budget.py`, `netwing/pricing.json`, `tests/test_budget.py`

**Interfaces:**
- Produces: `BudgetExceeded(Exception)`; `CostGuard(total_cap_usd:float, per_run_cap_usd:float, prices:dict)` with `start_run()->None`, `add_usage(model:str, input_tokens:int|None, output_tokens:int|None)->float` (returns this call's cost), properties `spent_total`, `spent_run`; `load_prices(path)->dict` returning `{model: {"input_per_mtok": float, "output_per_mtok": float}}`.

- [ ] **Step 1: Write failing tests:** `test_cost_accumulates` (known prices, 1,000,000 input tokens at 1.0/Mtok -> 1.0 spent); `test_raises_over_total_cap`; `test_raises_over_run_cap_then_start_run_resets_run_total_but_not_total`; `test_missing_usage_counts_conservative_estimate` (None tokens add a nonzero fixed estimate); `test_missing_price_raises_clear_error`.
- [ ] **Step 2: Run** `pytest tests/test_budget.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `netwing/budget.py`. `pricing.json` ships with the model key and `null` prices plus a comment field pointing to Anthropic's pricing page; `load_prices` raises if prices are null.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: cost guard with hard caps"`

### Task 3: Evidence ledger and Controller (the core idea)

**Files:**
- Create: `netwing/controller.py`, `tests/test_controller.py`

**Interfaces:**
- Consumes: `ToolResult` from Task 1.
- Produces: `Verdict` enum (`CONTINUE`, `STOP_FAULT`, `STOP_HEALTHY`, `STOP_CAP`); `Controller(max_tests:int=8)` with `observe(result:ToolResult)->str` (returns evidence id `E1`, `E2`, ...; category `invalid` results get an id but never count as evidence), `decide()->Verdict`, `allow_claim(verdict:str, fault_type:str, evidence_ids:list[str])->tuple[bool,str]` (second item is a rejection message for the agent), `tests_run:int`.

Rules (exact): `STOP_CAP` once `tests_run >= max_tests`. `STOP_HEALTHY` once connectivity, dns and port categories each have at least one passing result and there are zero failures. `STOP_FAULT` once at least one failing non-invalid result exists and at least one other valid test was run after it. A `fault` claim is allowed only if the cited ids include a failing result whose category matches the claimed fault type (`dns_failure`->dns, `port_blocked`->port, `route_failure`->connectivity or routing). A `healthy` claim is allowed only if there are zero failing valid results.

- [ ] **Step 1: Write failing tests:** `test_stop_healthy_after_three_passing_categories`; `test_continue_with_only_one_passing_category`; `test_stop_fault_after_failure_plus_one_more_test`; `test_stop_cap_at_max_tests`; `test_invalid_result_never_counts_as_evidence`; `test_fault_claim_without_failing_evidence_rejected` (message tells the agent to gather a failing observation or answer healthy); `test_fault_claim_wrong_category_rejected`; `test_healthy_claim_rejected_when_failure_exists`; `test_unknown_evidence_id_rejected`.
- [ ] **Step 2: Run** `pytest tests/test_controller.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `netwing/controller.py` with the exact rules above.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: evidence controller"`

### Task 4: Scoring

**Files:**
- Create: `netwing/scoring.py`, `tests/test_scoring.py`

**Interfaces:**
- Produces: `Score(correct:bool, false_alarm:bool, no_answer:bool)` dataclass; `score(scenario:Scenario, answer:dict|None)->Score`. Deterministic, no LLM judge.

- [ ] **Step 1: Write failing tests:** `test_correct_fault_identification`; `test_wrong_fault_type_incorrect`; `test_healthy_scenario_fault_claim_is_false_alarm_and_incorrect`; `test_healthy_scenario_healthy_answer_correct`; `test_none_answer_is_no_answer_incorrect_not_false_alarm`.
- [ ] **Step 2: Run** `pytest tests/test_scoring.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `score` per the interface: correct iff (truth=="healthy" and verdict=="healthy") or (verdict=="fault" and fault_type==truth); false_alarm iff truth=="healthy" and verdict=="fault".
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: deterministic scoring"`

### Task 5: Agent loop (Claude tool use, three modes)

**Files:**
- Create: `netwing/agent.py`, `tests/fake_client.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: `NetworkBackend`, `Scenario`, `Controller`, `CostGuard`, `Score`/`score`.
- Produces: `RunLog` dataclass (`scenario_id, mode, model, tests_run, answer:dict|None, status:"answered"|"no_answer"|"budget", cost_usd, transcript:list`); `run_diagnosis(scenario, backend, mode:str, client, guard, model:str, max_tests:int)->RunLog`. `client` is any object with `client.messages.create(**kwargs)` matching the Anthropic SDK shape (`.content` blocks with `type`, `id`, `name`, `input`, `.usage.input_tokens/.output_tokens`, `.stop_reason`). Tools exposed: the five backend tools plus `final_answer`.
- `tests/fake_client.py` produces `FakeClient(script:list[list[block]])` that returns scripted turns and records the kwargs it was called with.

Mode behavior: `plain` prompt treats the ticket as the task ("diagnose the reported problem"); `healthy_ok` adds one sentence that the network may be healthy and "healthy" is a valid answer; `netwing` uses the `healthy_ok` prompt plus: after each tool result `controller.observe`; before accepting `final_answer`, `controller.allow_claim` (rejection returned as a tool error so the loop continues); when `decide()` returns a STOP verdict, the next call sends a forced instruction "give your final answer now" and tool use beyond the cap is refused.

- [ ] **Step 1: Write failing tests** (scripted `FakeClient`, `SimNetwork`, real `Controller`):
  - `test_plain_mode_returns_answer_and_counts_tests`
  - `test_netwing_rejects_fault_claim_without_evidence_then_accepts_healthy` (script: model runs one passing ping then claims fault with no evidence, gets rejected, then answers healthy)
  - `test_netwing_forces_final_answer_after_stop_healthy` (assert the next call's messages contain the forced instruction)
  - `test_no_final_answer_within_cap_gives_no_answer_status`
  - `test_multiple_tool_use_blocks_in_one_turn_all_get_results_and_count` (script emits 3 `tool_use` blocks; assert 3 `tool_result` blocks sent back and `tests_run==3`)
  - `test_budget_exceeded_marks_status_budget_and_stops`
- [ ] **Step 2: Run** `pytest tests/test_agent.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `netwing/agent.py`. Cap tool executions per mode; calls past the cap return a tool error. Log every message into `transcript`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "feat: diagnosis agent with three modes"`

### Task 6: Runner, results table, demo CLI

**Files:**
- Create: `netwing/runner.py`, `netwing/demo.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `run_matrix(scenario_ids:list[str], modes:list[str], repeats:int, backend_factory:Callable[[Scenario],NetworkBackend], client, guard:CostGuard, model:str, out_path:str)->list[RunLog]` (appends one JSONL line per run as it goes; on `BudgetExceeded` stops and returns what exists); `summarize(logs:list[RunLog], simulated:bool)->str` (markdown table, one row per mode: correct %, false-alarm % on the healthy scenario, mean tests, mean cost; heading includes `SIMULATED` when `simulated`; adds a line `INCOMPLETE` if any run had status `budget`). CLI: `python -m netwing.demo --backend sim|kathara --repeats N --cap USD --dry-run`. `--dry-run` uses a scripted fake client and zero API spend.

- [ ] **Step 1: Write failing tests:** `test_matrix_writes_one_jsonl_line_per_run`; `test_summary_has_row_per_mode_and_simulated_heading`; `test_budget_exceeded_returns_partial_and_summary_says_incomplete`; `test_missing_api_key_without_dry_run_exits_with_clear_message`.
- [ ] **Step 2: Run** `pytest tests/test_runner.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** runner and CLI. `--dry-run` must exercise the full pipeline end to end with no network and no key.
- [ ] **Step 4: Run** `pytest -v` (whole suite). Expected: PASS.
- [ ] **Step 5: Run** `python -m netwing.demo --backend sim --dry-run --repeats 1`. Expected: prints a table headed `SIMULATED` with three mode rows and writes `results/*.jsonl`.
- [ ] **Step 6: Commit** `git commit -am "feat: runner, summary table, demo CLI"`

### Task 7: Kathará backend (real lab, Linux only)

**Files:**
- Create: `netwing/kathara.py`, `labs/healthy/lab.conf` (and the three fault labs), `labs/inject.sh`, `tests/test_kathara_parse.py`, `SETUP_LINUX.md`

**Interfaces:**
- Consumes: `NetworkBackend`, `ToolResult`.
- Produces: `KatharaNetwork(lab_dir:str)` implementing `NetworkBackend` by running `kathara exec -d <lab_dir> <device> -- <command>` through `subprocess.run`; pure functions `parse_ping(text)->bool`, `parse_dns(text)->bool`, `parse_port(text)->bool` tested without Docker.

- [ ] **Step 1: Write failing tests** `tests/test_kathara_parse.py` for the three parsers using captured sample outputs (success and failure strings for each).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** parsers and `KatharaNetwork`; each lab mirrors the sim topology (h1, h2, r1, DNS name `web.lab`) so scenario ids and tickets are shared. `inject.sh <scenario_id>` applies exactly one fault.
- [ ] **Step 4: Run** the parser tests. Expected: PASS.
- [ ] **Step 5 (manual, on the user's Linux machine):** follow `SETUP_LINUX.md` (Docker, Kathará install, `kathara lstart` the healthy lab). Run `python -m netwing.demo --backend kathara --repeats 1 --dry-run`. Expected: table without the `SIMULATED` heading and all four labs reachable.
- [ ] **Step 6: Commit** `git commit -am "feat: Kathara backend and labs"`

### Task 8: Real pilot and demo kit

**Files:**
- Create: `README.md`, `DEMO_SCRIPT.md`, `results/pilot-summary.md`

- [ ] **Step 1:** Fill `netwing/pricing.json` from Anthropic's pricing page for the chosen model; set `ANTHROPIC_API_KEY` in the shell.
- [ ] **Step 2:** Run `python -m netwing.demo --backend sim --repeats 2 --cap 3`. Expected: table printed, total spend under the cap, logs saved. Record the measured cost per run in `results/pilot-summary.md`.
- [ ] **Step 3:** Gate check: if `plain` mode does NOT over-diagnose `healthy_false_alarm` at all, stop and report to the user (the premise needs another look); otherwise continue.
- [ ] **Step 4:** On the Linux machine run the same command with `--backend kathara --repeats 3 --cap 8`; save the table.
- [ ] **Step 5:** Write `README.md` (what it is, how to run in sim and real, the honest limits: small scenarios, LLM-run noise, simulated vs real) and `DEMO_SCRIPT.md` (5-minute live walkthrough for the professor: show a healthy network, show plain Claude inventing a fault, show NetWing refusing and stopping early, show the table).
- [ ] **Step 6: Commit** `git commit -am "docs: demo kit and pilot results"`

## Self-review

- Spec coverage: demo first (Tasks 1-8), healthy false-alarm case and three real faults (Task 1), three diagnosers (Task 5), controller as main idea (Task 3), hard cost cap (Task 2), reusable logs (Task 6), real lab (Task 7), pilot gate check (Task 8). Paper-phase work (held-out topologies, human labels, more fault families, repeats with confidence intervals) is deliberately out of this plan and gets its own plan after the demo.
- Type consistency: `ToolResult`, `Scenario`, `Controller`, `CostGuard`, `RunLog`, `Score` names and signatures are used identically in later tasks.
- Proportion: each task names signatures, test names and exact rules only; no function bodies.
