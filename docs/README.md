# Documentation index

| Document | What it covers |
|---|---|
| [PROJECT_HISTORY.md](PROJECT_HISTORY.md) | Chronological record: question, design, every phase, what failed, current state |
| [research/01-results-log.md](research/01-results-log.md) | Controller rules, simulator and real-network results, failures that shaped the rules |
| [research/02-auto-cite-and-inconclusive.md](research/02-auto-cite-and-inconclusive.md) | `--auto-cite` safety check and the opt-in inconclusive verdict |
| [research/03-heldout-and-healthy-strategies.md](research/03-heldout-and-healthy-strategies.md) | Frozen held-out run, the 13 no-answers, hybrid / hint / belief strategies, first fresh validation |
| [research/04-fresh2-validation.md](research/04-fresh2-validation.md) | Pre-registered fresh2: hybrid + hint, claim validation |
| [research/05-fresh3-tiered-claims.md](research/05-fresh3-tiered-claims.md) | Pre-registered fresh3: tiered claims, with erratum |
| [research/06-dcc-architecture-audit.md](research/06-dcc-architecture-audit.md) | Why one confirmed fault is not a complete diagnosis; design sketch |

Reading order for a reviewer: README, PROJECT_HISTORY, then 04 and 05 (the pre-registered evaluations), then 06.

All results are from Claude Haiku 5.5 on a simulator unless stated otherwise. The raw run logs are in `results/`; commits `a0b68cf` and `06a1be0` freeze the fresh2 and fresh3 suites before their evaluations.
