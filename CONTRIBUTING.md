# Contributing

NetWing is a research artefact: every number in the docs must be re-derivable from a recorded run log.

## Ground rules
1. **Controller defaults never change.** New behaviour is an opt-in flag; default behaviour and published results stay identical.
2. **Frozen means frozen.** Pre-registered suites, `results/*.jsonl` logs and the Mini Project 2 baseline are not edited. New experiments get a new pre-registration and a new log file.
3. **Documented numbers are claims.** Add each one to `docs/research/claims.json`; `python -m netwing.reproduce check --strict` must pass.
4. **No secrets.** API keys come from the environment only; never commit them.
5. **Paid model runs need prior approval** (cost and scope stated first).

## Workflow
```
make install      # editable install with dev, lint, typecheck extras
make check        # ruff + mypy + pytest (incl. property tests) + reproduce --strict
```
Optional: `pip install pre-commit && pre-commit install`.

## Tests
- Example tests: `tests/`.
- Property-based tests (Hypothesis): `tests/test_controller_properties.py` state invariants that must hold for every tool-result sequence (append-only ledger, determinism, budget respected, no unsupported fault or healthy claim). They skip automatically if Hypothesis is not installed.
