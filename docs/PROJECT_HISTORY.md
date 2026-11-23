# Project history: from the first idea to today

NetWing started as a Computer Networks course project and was taken toward research-paper level. This page is the chronological record of what was decided, built, measured, and what failed. Numbers link to the detailed documents in [`research/`](research/).

## Phase 0. Choosing the question (19-20 Nov 2026)
- **Goal:** turn the course project into a publishable piece of work, treated as a paper from day one.
- **Literature scan.** Recent benchmarks (FaulT-Bench, SADE) report that LLM network-troubleshooting agents often "find" a fault on a network that is actually healthy, and that the remedy (an explicit evidence check before concluding) was untested. Models given a tool budget also do not reliably cut their own tool calls, which justifies an *external* controller.
- **Topic chosen:** an evidence-sufficiency controller, i.e. a wrapper that decides when an LLM diagnosis agent has enough evidence to conclude (or to say "healthy"). Alternatives considered and rejected: an internet-measurement study, security of LLM NetOps agents (crowded), root-cause analysis on cloud incident reports (weaker demo).
- **Design decisions:** the controller is a rule engine, not another model; a strong prompt-only baseline (`healthy_ok`) must be beaten, not just a plain agent; all modes get the same 12-test budget; scoring is deterministic from scenario ground truth (no LLM judge).
- **Novelty risk recorded early:** the over-diagnosis in the literature is agents citing a *real but benign* condition, so the gate needs a relevance rule, not only "a failing test exists".

## Phase 1. The research core (21 Nov)
Commit `cebfa36`.
- **Controller** with numbered evidence ids, relevance filtering, transient-blip clearing, confirmation rules, coverage of ping/DNS/port, and a test budget.
- **Three modes:** `plain`, `healthy_ok`, `netwing`; Claude Haiku 5.5 with tool use.
- **Backends:** a deterministic simulator and a real one built from Linux network namespaces (kernel routing, firewalling, dnsmasq), parity-tested against each other. A Kathara backend is written but never run on real Docker.
- **Experiment runner** with a hard USD cap, 95% Wilson intervals, JSONL logs per run, a dry-run stub so the whole pipeline runs with zero API spend.
- **Scenario suites:** easy, hard (red-herring alerts), flaky (transient blip, intermittent port), multi (two faults), campus (bigger topology).

**Rules were found by failing, not guessed.** Each one below was added after a measured failure (details in [`research/01-results-log.md`](research/01-results-log.md)): a confirm-twice rule with an 8-test budget gave 30% correct; DNS failures masked ping and port checks; the model could not know that three names were the same server; route faults seen from several hosts never repeated the identical check; correct diagnoses were rejected at the budget cap; a noisy healthy case kept getting no answer.

**Result of the first round (simulator, 10 repeats per scenario).** Hard suite: netwing 100% correct, 0% false alarms, 8.2 tests, against baselines at 78-80% correct and 80-90% false alarms and 11 tests. Flaky: 100% / 0% false alarms against 65-100%. Multi-fault: all faults found 95% against 70%. Easy: all modes 100%, netwing with the fewest tests.

## Phase 2. Mini Project 2: from controller to product (21-22 Nov)
Commits `6e72951`, `954b850`, `9f772dd`. All additive, so published experiment results stay valid.
- Web UI (stdlib only): investigation history, evidence explorer, compare, simulation lab with ground truth, run-an-investigation page.
- Network health score from *measured* values only (unmeasured indicators are shown separately and never assumed healthy).
- SQLite history, standalone HTML report and a native PDF writer with no third-party library.
- Evidence assurance (Confirmed / Suspected / Inconclusive) per investigation, and an opt-in `inconclusive` verdict.
- Lab scenarios with ground truth (high latency, packet loss, misleading complaint).
- GitHub Actions CI (lint, tests, dry-run on Python 3.10-3.13), Docker image, console commands.

## Phase 3. The real network and the first honest negative result (21-22 Nov)
Commits `9ec8885`, `92662cf`, `eac240c`.
- Ran the easy suite on real Linux namespaces: netwing used 24-26% fewer tests than plain with non-overlapping intervals, but produced 2 no-answers of 20 because it rejected correct diagnoses over *which evidence ids the model cited*.
- `--guide-citations` (tell the model which ids it could cite) made it **worse** (5 no-answers). Reported as a negative result.
- `--auto-cite` (judge the claim by the evidence the run gathered) removed the no-answers (0 of 20, 100% correct) and kept the simulator results unchanged. Opt-in, because it was designed after seeing those failures on the same suite.

## Phase 4. Held-out evaluation and the healthy-network problem (23 Nov)
Commits `def74b5`, `e4e837d`, `82a25c2`, `d26626e`.
- Because rules had been tuned on the reported scenarios, a **held-out suite** (8 scenarios) was frozen and run once with no changes afterwards. Zero false alarms held again (0 of 40 healthy runs) with about 25% fewer tests, **but netwing gave no answer on 13 of 80 runs**: every case was a healthy network with one transient failure, or an intermittent port.
- Root-cause analysis (not tuning): the agent spent 3-6 of its 12 tests on alerts the controller ignores, re-ran the identical check once instead of twice, and only learned the rule when it tried to answer, after the budget was gone ([`research/03`](research/03-heldout-and-healthy-strategies.md)).
- Built, all opt-in: a **Bayesian belief model** with expected information gain (offline analysis layer), `--retest-hint`, `--healthy-strategy hybrid`, source-aware DNS handling, and a counterfactual replay tool.
- First fresh validation (8 new scenarios): safety held (0 false faults, 0 missed faults) but it could not show the improvement, because the original already did well on its healthy cases. Verdict recorded: **do not promote**.

## Phase 5. Pre-registered validations: fresh2 and fresh3 (23-24 Nov)
Commits `a0b68cf`, `f812db5`, `06a1be0`, `6f2bf36`, `2103c32`.
Method: freeze the suite, write the acceptance criteria, commit, only then run. Never change a criterion after seeing results.
- **fresh2:** hybrid + retest hint raised "healthy answered healthy" from 13% to 97% (30 runs, non-overlapping intervals), with 0 false alarms, 0 missed faults, no-answers 29% to 2%, and fewer tests (10.0 to 8.5). *Criteria met; stays opt-in.*
- **Claim validation** (`--validate-claims`) removed unsupported extra-fault claims (56% to 0%) but also dropped real second faults (multi-fault exact 93% to 13%). *Criteria not met; not promoted.*
- **fresh3 / tiered claims** (`--tier-claims`: keep once-seen claims as "suspected", scored separately) reached 65% multi-fault recall including suspected against an 80% bar. *Criteria not met; not promoted.*
- **Honest corrections:** a duplicate-scenario check caught 3 fresh3 definitions that repeated earlier suites (replaced, and a test now forbids duplicates); log files that mixed several invocations were analysed per invocation and disclosed; an analysis error ("second fault confirmed in only 1 of 60 runs") was corrected by an erratum (the right figures are 15 and 9 of 60).
- **Variance finding:** two configurations with identical agent behaviour differed by about 20 points on multi-fault recall, so gains without a pre-registered criterion are not claimed.

## Phase 6. Why a confirmed fault is not a complete diagnosis (24 Nov)
A read-only architecture audit ([`research/06`](research/06-dcc-architecture-audit.md)) explained the multi-fault results: the controller stops as soon as one fault is reproduced and ping/DNS/port were tried, has no per-fault state, never schedules a test, and does not model masking (a verified latent false positive: a route-only network lets a `port_blocked` claim pass as confirmed). A completeness-aware design is outlined; it is not built and would need a new frozen suite before any evaluation.

## Phase 7. Quality pass (24 Nov)
Commit `4611f0e`. mypy clean (40 errors fixed) and added to CI; docstrings for the public API; a package overview; README and docs rewritten. Verified behaviour-neutral: the zero-cost pipeline produced identical logs before and after (96 runs), 316 tests passing.

## Where it stands
| | |
|---|---|
| Code | about 3,000 lines of Python in `netwing/`, 316 tests (+4 real-lab tests), ruff and mypy clean, CI on Python 3.10-3.13 |
| Supported by evidence | fewer tests and lower cost across suites; 0 false alarms on healthy networks in every netwing run on the simulator; hybrid + retest-hint fixes the healthy-network no-answer failure (fresh2) |
| Reported as negative | `--guide-citations`; strict claim validation; tiered claims; the hybrid's claimed healthy gain was not visible on the first fresh suite |
| Not claimed | that NetWing improves multi-fault detection, or that it eliminates hallucinated diagnoses |
| Known limits | one model; simulator for most suites; real network covers the easy suite only; Kathara never run on Docker; large run-to-run variance needs 30+ repeats |

## Next
Second model; 30+ repeats; real-network hard and lab scenarios; a pre-registered completeness-aware controller on a new frozen suite; human-labelled evaluation; paper draft.
