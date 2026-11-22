"""Offline counterfactual replay: when would each healthy strategy have stopped, on logs that already exist?

EXPLORATORY. A saved run is one trajectory the agent actually took. Replaying a different decision rule over it
says when that rule would have stopped along that same trajectory, not what the agent would have done had the rule
(or its hints) been live. Use it to choose what to test live, never as the final evidence. Costs nothing.

    python -m netwing.strategy_replay results/run-*.jsonl --taus 0.85 0.9
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

from .backend import ToolResult
from .controller import Controller, Verdict
from .scenarios import get_scenario


def first_stop(run: dict, strategy: str, tau: float, resolver_hosts=None) -> tuple[Verdict | None, int | None]:
    """The first verdict (other than CONTINUE/STOP_CAP) the controller would have returned, and after which test."""
    scenario = get_scenario(run["scenario_id"])
    c = Controller(max_tests=12, subject=scenario.subject, healthy_strategy=strategy, belief_tau=tau, resolver_hosts=resolver_hosts)
    for t in run.get("tests") or []:
        c.observe(ToolResult(t["tool"], dict(t.get("args") or {}), str(t.get("output", "")), bool(t["ok"]),
                             t["category"], t.get("evidence", True) is not False))
        v = c.decide()
        if v in (Verdict.STOP_HEALTHY, Verdict.STOP_FAULT):
            return v, c.tests_run
    return None, None


def replay(runs: list[dict], configs: list[tuple[str, float]]) -> list[dict]:
    rows = []
    for strategy, tau in configs:
        agg = defaultdict(lambda: {"n": 0, "healthy": 0, "fault": 0, "none": 0, "tests": []})
        for run in runs:
            if not run.get("tests"):
                continue
            truth_healthy = get_scenario(run["scenario_id"]).truth == "healthy"
            v, at = first_stop(run, strategy, tau)
            a = agg["healthy networks" if truth_healthy else "faulty networks"]
            a["n"] += 1
            if v == Verdict.STOP_HEALTHY:
                a["healthy"] += 1
                a["tests"].append(at)
            elif v == Verdict.STOP_FAULT:
                a["fault"] += 1
            else:
                a["none"] += 1
        for k, a in sorted(agg.items()):
            rows.append({"strategy": strategy, "tau": tau if strategy != "rules" else None, "truth": k, **a,
                         "mean_tests_at_healthy_stop": (sum(a["tests"]) / len(a["tests"])) if a["tests"] else None})
    return rows


def load(paths: list[str]) -> list[dict]:
    runs = []
    for p in sorted({f for pat in paths for f in glob.glob(pat)}):
        with open(p, encoding="utf-8") as fh:
            runs += [json.loads(line) for line in fh if line.strip()]
    return runs


def table(rows: list[dict]) -> str:
    out = ["| Strategy | tau | Network truth | Runs | Would stop HEALTHY | Would stop FAULT | No stop | Mean tests at healthy stop |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        m = "n/a" if r["mean_tests_at_healthy_stop"] is None else f"{r['mean_tests_at_healthy_stop']:.1f}"
        out.append(f"| {r['strategy']} | {r['tau'] if r['tau'] is not None else '-'} | {r['truth']} | {r['n']} | "
                   f"{r['healthy']} ({100 * r['healthy'] / r['n']:.0f}%) | {r['fault']} | {r['none']} | {m} |")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("logs", nargs="+")
    p.add_argument("--taus", nargs="+", type=float, default=[0.85])
    p.add_argument("--modes", nargs="+", default=None, help="only logs of these modes (default: all)")
    a = p.parse_args(argv)
    runs = [r for r in load(a.logs) if not a.modes or r.get("mode") in a.modes]
    configs = [("rules", 0.85)] + [(s, t) for s in ("hybrid", "belief") for t in a.taus]
    print(f"EXPLORATORY counterfactual replay of {len(runs)} logged runs (same trajectories, different stop rule)\n")
    print(table(replay(runs, configs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
