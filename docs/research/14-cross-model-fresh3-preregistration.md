# Cross-model check of fresh3 on Sonnet 5.5: pre-registration, written before any run

Status: **not yet run; the paid run needs explicit approval at the corrected cost below.** Simulator, `claude-sonnet-5-5`, netwing mode, suite `fresh3` (frozen in `06a1be0`, unchanged), code at the commit that contains this file. No tuning.

## Cost correction
Earlier in the project this check was estimated at about $0.50. That was wrong: `netwing/pricing.json` lists Sonnet 5.5 at $2.00 / $10.00 per million tokens against $0.10 / $0.50 for Haiku 5.5, about 20 times more. At the Haiku mean of about $0.002 per run, a Sonnet run is about $0.04. Two arms of 56 runs (8 repeats of 7 scenarios) are therefore about $4.5 in total, so each log is capped at `--cap 3`.

## Why
Every published result uses `claude-haiku-5-5`. This asks whether the main fresh3 findings are a property of the controller or of one model.

## Configurations (8 repeats each, 56 runs per arm)
**original** (default controller) and **tier** (`--tier-claims`). The Haiku logs `fresh3_original.jsonl` and `fresh3_tier.jsonl` (15 repeats) are the comparison.

## Criteria (decided now; descriptive replication, no promotion decision)
- **C1 (controller, not model):** on Sonnet, default-controller `correct` is not lower than Haiku's beyond overlapping Wilson 95% intervals.
- **C2 (second-fault under-confirmation):** over the 32 double-fault runs of the tier arm, all injected faults confirmed (set comparison through `claim_report`, as in `05-fresh3-tiered-claims.md`) is below 50%. Haiku: 15 of 60 (25%). If Sonnet is at or above 50% the finding is model-dependent and the paper says so.
- **C3 (tier still not promoted):** the T criterion of `05-fresh3-tiered-claims.md` is evaluated unchanged on Sonnet and reported met or not met. This does not change the default for either model.
Intervals will be wide at n=56; the write-up reports counts and says so.

## Commands
```
python -m netwing.demo --backend sim --suite fresh3 --modes netwing --repeats 8 --cap 3 --model claude-sonnet-5-5 --out results/fresh3_sonnet_original.jsonl
python -m netwing.demo --backend sim --suite fresh3 --modes netwing --repeats 8 --cap 3 --model claude-sonnet-5-5 --tier-claims --out results/fresh3_sonnet_tier.jsonl
git add -f results/fresh3_sonnet_original.jsonl results/fresh3_sonnet_tier.jsonl
```
