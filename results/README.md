# Run logs

One JSON line per run (`netwing.agent.RunLog` plus score, provenance and the full transcript). Only logs that back a
documented number are committed; every other `run-*.jsonl` stays local (`results/*.jsonl` is git-ignored).

| Log | Contents | Cited by |
|---|---|---|
| `run-20261121-110330.jsonl` | Real Linux network, easy suite, baseline controller | [research 01](../docs/research/01-results-log.md) |
| `run-20261122-024239.jsonl` | Hard suite re-run with `--auto-cite` | [research 02](../docs/research/02-auto-cite-and-inconclusive.md) |
| `run-20261123-033549.jsonl` | Frozen held-out suite, default rules | [research 03](../docs/research/03-heldout-and-healthy-strategies.md) |
| `run-20261123-041031.jsonl` | Frozen held-out suite, `--auto-cite` | research 03 |
| `run-20261123-044618.jsonl` | Fresh suite | research 03 |
| `fresh2_*.jsonl` | Pre-registered fresh2 evaluation (several invocations per file) | [research 04](../docs/research/04-fresh2-validation.md) |
| `fresh3_*.jsonl` | Pre-registered fresh3 evaluation | [research 05](../docs/research/05-fresh3-tiered-claims.md) |

Logs are append-mode, so a file can hold more than one invocation. Never quote a whole file: use

```bash
python -m netwing.reproduce inventory            # every file split into its invocations
python -m netwing.reproduce check --strict       # every documented number against the logs
python -m netwing.reproduce table results/fresh2_original.jsonl#2
```

`docs/research/claims.json` lists each documented number with its file, invocation, mode and metric. Logs written
from this version on carry an `invocation_id` and a `provenance` block (commit, configuration hash, versions) and can be
continued with `--resume`.
