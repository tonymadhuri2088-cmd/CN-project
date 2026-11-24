# fresh5: layer-coverage stopping rule (`--cover-areas`) pre-registration, written before any run

Status: **not yet run; the paid run needs explicit approval.** Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh5` (7 scenarios, frozen by `tests/test_fresh5_suite.py`), code at the commit that contains this file. Default controller and all numbers in `claims.json` are untouched; new numbers go to `claims_v2.json`.

## Why
`05-fresh3-tiered-claims.md` found that the controller rarely confirms a second fault: it stops as soon as the primary fault is reproduced and connectivity, DNS and port were all tried, so the other fault has had at most one sighting (in 43 of 59 answered double-fault runs exactly one failing check stood in the other fault's area). The tier layer could only relabel that thin evidence. `--cover-areas` changes the stopping rule instead.

## The rule (opt-in; default off)
With `cover_areas`, `decide()` does not return STOP_FAULT while any area (connectivity, DNS, port) holds a standing failure seen only once. Keep testing until that failure is reproduced, clears (identical check passes twice), or the 12-test cap is reached. A port failure is not pending while a reproduced route failure stands (masking: the route failure makes port checks fail by itself). Healthy decisions are unchanged. Each tool result also carries a one-line coverage hint naming the area to repeat. Pinned by `tests/test_cover_areas.py` (8 tests).

## Frozen suite fresh5
Four double-fault scenarios (`fx5_route_dns`, `fx5_campus_port_dns`, `fx5_noisy_port_dns`, `fx5_flaky_dns_port`), two single-fault controls (`fx5_flaky_campus_dns`, `fx5_flaky_campus_port`) and one healthy control (`fx5_flaky_campus_healthy`). No definition repeats an earlier suite (tested).

## Configurations (15 repeats each, 210 runs; about $0.5 expected, `--cap 1` each)
**off** (default), **cover** (`--cover-areas`). Nothing else differs. Scores use the existing strict `complete` field.

## Criteria (decided now)
- **M (completeness gain):** over the 60 double-fault runs, `complete` with cover is at least 15 percentage points above off.
- **H (no harm):** over all 105 runs, `correct` is not lower than off beyond overlapping Wilson 95% intervals; false alarms and no-answers are not higher beyond overlapping intervals; on the 15 healthy runs, `correct` is not lower.
- **C (cost):** mean tests per run with cover is at most 3 above off (cap 12 unchanged).

The rule is a candidate for promotion only if M, H and C all hold. Even then it stays opt-in until a second model and a second frozen suite agree. If M fails, the result is reported as negative in the paper's Analysis.

## Known risk, stated in advance
The rule can push runs to the cap when a single-sighting failure is a blip the model does not retest; H and C are there to catch that.

## Commands (PowerShell, key set only for the session)
```
python -m netwing.demo --backend sim --suite fresh5 --modes netwing --repeats 15 --cap 1 --out results/fresh5_off.jsonl
python -m netwing.demo --backend sim --suite fresh5 --modes netwing --repeats 15 --cap 1 --cover-areas --out results/fresh5_cover.jsonl
git add -f results/fresh5_off.jsonl results/fresh5_cover.jsonl
```
