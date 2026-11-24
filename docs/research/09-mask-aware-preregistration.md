# mask-aware: live-model evaluation (pre-registration, written before any run)

Status: **not yet run.** Commit this file before running anything. Simulator, `claude-haiku-5-5`, netwing mode, code at the commit that contains this file. Nothing here changes the default controller or any of the 44 numbers in `claims.json`; new numbers go to `claims_v2.json`.

## Question
`--mask-aware` stops a `port_blocked` claim while a route failure on the target stands. In simulator unit tests it does. Does it matter with a real model, and does it cost anything?

## Design (paired, same code, same scenarios, same repeats)
- Configurations: **off** (default controller) and **on** (`--mask-aware`). Mode `netwing` only. 10 repeats each.
- **Route-only scenarios (7)** (truth `route_failure`, where a `port_blocked` claim is the known false positive): `route_failure`, `noisy_route_failure`, `campus_route_failure`, `ho_campus_noisy_route`, `fx_noisy_route`, `fx2_campus_noisy_route`, `fx3_blip_route`.
- **Port scenarios (10)** (truth `port_blocked`, a regression check; ping passes so the rule should not fire): `port_blocked`, `noisy_port_blocked`, `intermittent_port`, `campus_port_blocked`, `ho_noisy_flaky_port`, `fx_flaky_port`, `fx_noisy_port`, `fx2_campus_noisy_flaky_port`, `fx2_campus_noisy_port`, `fx3_campus_noisy_blip_port`.
- 17 scenarios x 10 repeats x 2 configurations = 340 runs. Past logs cost about $0.002 per run, so about $0.70. Approved cap: $2 in total (`--cap 1` per configuration).
- Many of these scenarios were used when tuning or in frozen suites. This is a new experiment with its own logs, not a rerun of those suites, and it makes no generalisation claim for the held-out suites.

## Primary measure
On the 70 route-only runs per configuration: runs whose final answer names `port_blocked` as the fault or as an extra fault (the false positive).

## Criteria
- **P1 (benefit):** a benefit is shown only if the off-configuration has at least 3 such runs of 70 AND the on-configuration has fewer, with non-overlapping Wilson 95% intervals. If off has fewer than 3, the result is "not informative: the model rarely makes this mistake", NOT a win.
- **P2 (no regression):** on the 100 port runs per configuration, exact-correct for on is not lower than off beyond overlapping Wilson intervals, and no-answer is not higher beyond overlapping intervals.
- **P3 (no loop):** on the route-only runs, no-answer for on is not higher than off beyond overlapping intervals, and mean tests are within +1 of off. Also report how many on-runs had a rejection by the masking rule (message contains "route failure on the target still stands") and how those runs ended.
- Report everything whichever way it goes. No rule or prompt is changed after looking at the results.

## Data handling
Each configuration writes a new file. A stopped run is reported as incomplete and rerun into a new file; only an intact 10-repeat log is analysed. Documented numbers go into `docs/research/claims_v2.json`; `python -m netwing.reproduce check --claims docs/research/claims_v2.json --strict` checks them. CI keeps checking `claims.json` (44 of 44).

## Commands (PowerShell, from the project folder; use your own rotated key)
```
$sc = "route_failure","noisy_route_failure","campus_route_failure","ho_campus_noisy_route","fx_noisy_route","fx2_campus_noisy_route","fx3_blip_route","port_blocked","noisy_port_blocked","intermittent_port","campus_port_blocked","ho_noisy_flaky_port","fx_flaky_port","fx_noisy_port","fx2_campus_noisy_flaky_port","fx2_campus_noisy_port","fx3_campus_noisy_blip_port"
python -m netwing.demo --backend sim --modes netwing --scenarios $sc --repeats 10 --cap 1 --out results/maskaware_off.jsonl
python -m netwing.demo --backend sim --modes netwing --scenarios $sc --repeats 10 --cap 1 --mask-aware --out results/maskaware_on.jsonl
```
Second model family: not part of this pre-registration (decided separately).
