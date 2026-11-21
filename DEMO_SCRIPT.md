# NetWing: Monday 23 Nov demo script (about 8 minutes)

Numbers are from the final code, Claude Haiku 5.5, simulated network (label every table "SIMULATED"). Full details are in the results log.

## 1. The problem (1 minute)
LLM agents that diagnose networks have two bad habits: they invent a fault when the network is healthy (a false alarm), and they keep running tests long after they have enough evidence. NetWing is a small controller between the agent and the network that decides when evidence is sufficient to stop.

## 2. How it works (2 minutes)
- Every test result gets a number (E1, E2, ...). The agent may only claim a fault or "healthy" by citing those numbers.
- A fault claim is accepted only if the failure was confirmed (the same check failed twice, or the same kind of failure showed up from a different check) and ping, DNS and port have all been tried. A failure that does not repeat is a blip and is dropped.
- A "healthy" claim is accepted only if nothing is failing and something passed.
- If a claim is rejected, the agent gets a specific message saying what is missing and keeps testing within a 12-test budget.
- The rules are plain code; the model never grades itself.
Compared against two baselines with the same model and the same 12-test budget: plain (no stop rules) and healthy_ok (plain, but allowed to answer "healthy").

## 3. Live run (2 minutes)
`python -m netwing.demo --backend sim --suite hard --repeats 2 --cap 3`
Point at: netwing finishing in fewer tests, and the noisy healthy case answered "healthy" instead of a fabricated fault. If the API is slow, show a saved table from the `results` folder.

## 4. Results (2 minutes)
| Suite | What it tests | plain | healthy_ok | netwing |
|---|---|---|---|---|
| Easy (40 runs) | clear single faults and healthy | 100%, 6.9 tests | 100%, 5.8 | 100%, 5.5 |
| Hard (40 runs) | noisy healthy, unrelated alerts | 80% correct, 80% false alarms, 11.0 tests | 78%, 90% false alarms | 100%, 0% false alarms [0-28], 8.2 tests |
| Flaky (20 runs) | one-off blips on a healthy network | 65%, 70% false alarms, 11.7 tests | 100%, 0%, 11.4 | 100%, 0%, 9.3 |
| Multi (20 runs) | two faults at once | 70% find all faults, 10.3 tests | 70%, 9.8 | 95% [76-99], 7.0 |

Headlines:
- On noisy healthy networks the baselines invented a fault 80-90% of the time; NetWing did not once, with about 25% fewer tests and lower cost.
- With two faults at once, NetWing found both 95% of the time vs 70%.
- On easy cases everyone is correct; NetWing uses a bit fewer tests.

## 5. Limits to say out loud (1 minute)
- Simulated network, one model (Haiku 5.5).
- The false-alarm result rests mainly on one noisy healthy scenario with 10 runs per mode; baseline false-alarm rates vary between runs, so 30+ repeats are needed.
- The rules were refined on these same scenarios; held-out scenarios come next.

## 6. Next steps (30 seconds)
30+ repeats, held-out multi-fault and campus scenarios, ablations of each rule, a second model, real Kathara/netns lab on the Linux machine, human-checked labels, then the paper.

## Likely professor questions
- Why not just prompt the model to be careful? The baselines get the same budget and inventory line; the difference is the enforced rules.
- Were the rules tuned on these cases? Partly, yes; held-out scenarios are the first paper task.
- Does it work on a real network? Kathara and Linux-namespace backends exist; the namespace parity test passed; real-model runs on them are planned.
- Cost? About $0.001 per diagnosis; the whole experiment about $1.5.
