# 07. Comprehensive technical and research audit (24 Nov 2026)

A read-only audit of the whole repository (code, tests, logs, documents), followed by the three highest-priority
fixes. Nothing in the controller, the frozen suites, the acceptance criteria or any historical log was changed.
Labels: **[measured]** run or recomputed this session, **[read]** from reading the code, **[judgement]** my assessment.

## 1. Status

| Audit item | Status |
|---|---|
| Reconcile every documented number with the raw logs | **Done.** 42 numbers tie to 11 logs; all reproduce. `python -m netwing.reproduce check` |
| Run provenance (invocation id, commit, config hash, versions) and `--resume` | **Done**, additive; old logs untouched |
| Web UI request checks (Host, Origin, per-process token, security headers) | **Done** |
| Kathara `dns_lookup` argument validation; boolean ports rejected | **Done** |
| History store thread safety | **Done** (a concurrency test failed before the fix) |
| Error taxonomy (`api` / `internal` / `other`) in run logs | **Done** |
| Per-fault state and completeness stop (DCC) | Open: needs a new frozen suite and pre-registered criteria |
| Contradictory-evidence counts, evidence graph | Open |
| Linux-namespace hardening and simultaneous-fault scenarios | Open |

Behaviour check [measured]: old code (git HEAD) and new code give identical decisions on 228 scripted runs across eight
suites (easy, hard, flaky, multi, campus, heldout, fresh2, fresh3). The scripted stub shows the controller and the
pipeline are unchanged; it does not exercise a real model.

## 2. Number reconciliation

Run logs are written in append mode, so one file can hold several invocations (an aborted start, a retry, the reported
run). `netwing.reproduce` splits a file into invocations by the time gap between runs (or by invocation id for new
logs) and ties each documented number to (file, invocation, mode, metric) in `docs/research/claims.json`.

- All 42 locked numbers reproduce exactly, including fresh2 (healthy answered healthy 13% to 97%; extra claims 56% to
  0%; multi-fault exact 93% to 13%) and fresh3 (tier 65% against the 80% bar; 15/60 and 9/60 both-faults-confirmed).
- Replication seen in the logs: on fresh2 the original controller answered a healthy network "healthy" in 8%, 6% and
  13% of runs across three separate invocations, so the 13% is not a one-off.
- Two baselines swap places between the first-round and re-run hard suites (plain 80%/80% vs 78%/90% false alarms,
  `healthy_ok` the reverse). These are separate runs and statistically indistinguishable: quote one invocation, say which.
- Run-to-run variance is large: `plain` scored 90% on the held-out default run and 81% on the auto-cite run, with no
  behavioural difference for `plain`. Differences under about 20 points between single runs are not evidence.
- **A claim not to make:** on the held-out suite NetWing is not more accurate than `plain` (84-88% vs 81-90%). It removes
  false alarms (0% vs 40-70%) by leaving 10-13 of 80 runs unanswered. Say "fewer false alarms at the cost of
  unanswered runs".
- Not locked: the very first hard-suite log (the numbers in the README tie to docs 01 and REFERENCE, but that log file
  was not located) and four 80-run netwing-only logs that no document cites.

## 3. Architecture findings [read]

- `decide()` reads whole-ledger sets, so a fault can be declared after as few as 4 tests. There is no per-fault state,
  so masking and second faults cannot be represented. This is the root cause of the low second-fault recall.
- The controller vetoes or accepts the agent's actions; it never schedules tests. Good for the "external supervisor"
  framing, limiting for completeness.
- `run_diagnosis` is about 140 lines and run options are threaded as roughly 17 separate flags; a policy object would
  compose them better.
- The simulator accepts physically inconsistent claims (a route-only network accepts `port_blocked`): there is no
  dependency or masking model.

## 4. Research candidates and verdicts [judgement]

| Idea | Verdict | Why |
|---|---|---|
| Per-fault state, with a completeness stop (DCC) | Essential next | Fixes the stated root cause; foundation for the rest |
| Contradictory-evidence counts (Beta per check) | High value | The 10-13 held-out no-answers are one failure then one pass of the same check |
| Dependency-aware evidence graph | High value | The principled form of what `--validate-claims` approximated and failed at |
| Adaptive test selection, uncertainty display | Optional | Belief noise parameters are unfitted; keep as a hint |
| Budget-aware stopping | Optional | Adds a tuned parameter; the 12-test cap result already stands |
| Causal validation | Not yet | Largely subsumed by the graph and per-fault state |

Each would need its own frozen suite, pre-registered criteria and independent run before any improvement is claimed.

## 5. Evaluation methodology

Sound already: frozen suites, committed criteria, deterministic scoring, Wilson intervals, negative results reported.
Remaining gaps: one model; mostly simulated; a real-network suite with only 5 healthy cases; no paired tests;
temperature not recorded (the API default is used; provenance now records that explicitly); latency not logged.
Protocol going forward: freeze suite, code hash and criteria in git; one invocation per log (provenance now makes this
checkable); at least 30 runs per condition for a headline claim; paired comparison on identical scenario and repeat keys;
an ablation table; every number regenerated by `netwing.reproduce`.

## 6. Security and reliability

| Finding | Severity | Resolution |
|---|---|---|
| Web UI `POST /new` had no CSRF, Origin or Host check | Low to medium (loopback bind; a run is simulator-only and capped) | Per-process token in the form, same-origin check, Host allow-list, security headers |
| Kathara `dns_lookup` passed an unvalidated name to `dig` | Medium on a real backend | Hostname pattern; non-strings and option-like names refused |
| Shared SQLite connection used from several threads | Low | Lock around every access |
| Broad `except` in the agent loop hid bugs as model errors | Low | Kept (a failed call must keep its cost) but classified and located in the log |
| Namespace backend runs as root and relies on `atexit` teardown | Reliability | Open: use run-scoped names and idempotent teardown |

## 7. Linux-namespace testbed

The namespace backend is real (veth and bridge, `ip netns exec`) and has run on WSL 2, but it has the lowest test
coverage (22%, because it needs root) and fixed namespace names. A controlled testbed for the paper needs: run-scoped
names and idempotent teardown; router and firewall namespaces; `tc netem` latency, loss and transient faults;
simultaneous-fault scenarios. Kathara should be considered only if this proves insufficient; it has never been run on
real Docker.

## 8. Roadmap

1. Done: provenance and resume; reproducibility script and claims lock; security hardening.
2. Next, simulator first, each with pre-registered criteria and a frozen suite, paid runs only with approval:
   per-fault state with completeness stop; contradiction counts; evidence graph.
3. Then: namespace hardening and multi-fault scenarios; a second model; 30+ repeats; human-labelled evaluation.
