# fresh4: masking v2 (`--mask-reproduced`) pre-registration, written before any run

Status: **not yet run; the paid run needs explicit approval.** Simulator, `claude-haiku-5-5`, netwing mode, suite `fresh4` (7 scenarios, frozen by `tests/test_fresh4_suite.py`), code at the commit that contains this file. Default controller and all numbers in `claims.json` are untouched; new numbers go to `claims_v2.json`.

## Why
The first live run (`10-mask-aware-live-results.md`) showed `--mask-aware` masks on a single connectivity sighting and turned a blip scenario into 10 of 10 no-answers; it also never touched the extra `port_blocked` claims in `other_faults`. v2 (`--mask-reproduced`) masks only when a connectivity failure is reproduced, and drops masked secondary claims (the raw claim and the dropped list stay in the log).

## Frozen suite
fx4 scenarios: three port faults with a one-off lost ping (plain, noisy, campus), four route-only faults (plain flaky-ticket, campus flaky-ticket, noisy with blip, campus noisy with blip). No definition repeats an earlier suite.

## Configurations (15 repeats each, 315 runs; about $0.70 expected, `--cap 1` each)
**off** (default), **v1** (`--mask-aware`, to see whether the defect reproduces), **v2** (`--mask-reproduced`).

## Criteria
- **B (blip over-masking fixed):** on the 45 port-blip runs, v2 no-answer is not higher than off beyond overlapping Wilson 95% intervals, and v2 correct is not lower beyond overlapping intervals.
- **R (no harm on route-only):** on the 60 route-only runs, v2 correct and no-answer are not worse than off beyond overlapping intervals, and mean tests are within +1.
- **S (secondary claims):** benefit only if off has at least 3 of 60 route-only runs with `port_blocked` among the extra faults and v2 has fewer with non-overlapping intervals; otherwise "not informative".
- v2 may be described as a usable opt-in only if B and R both pass; it never becomes the default. v1 is reported either way. Report everything; no rule is changed after looking at the results.

## Data handling
Each configuration writes a new file; an incomplete run is reported as incomplete and rerun into a new file.

## Commands (PowerShell, your own rotated key)
```
python -m netwing.demo --backend sim --suite fresh4 --modes netwing --repeats 15 --cap 1 --out results/fresh4_off.jsonl
python -m netwing.demo --backend sim --suite fresh4 --modes netwing --repeats 15 --cap 1 --mask-aware --out results/fresh4_v1.jsonl
python -m netwing.demo --backend sim --suite fresh4 --modes netwing --repeats 15 --cap 1 --mask-reproduced --out results/fresh4_v2.jsonl
```
