"""Replay saved run logs through the Bayesian belief and report when a principled stopping rule could have stopped.

    python -m netwing.belief_report results/run-*.jsonl --tau 0.9 0.95 0.99

No model call, no cost. For every run the recorded tests are fed, one by one, to `Belief`; the "belief stop" is the
first test after which the most likely explanation has posterior >= tau. The report compares it with what the agent
actually did. It is an offline analysis: it does not change any controller decision.
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

from .backend import ToolResult
from .belief import Belief, answer_set, truth_set
from .controller import Controller
from .scenarios import get_scenario


def replay_run(run: dict, tau: float = 0.95, **belief_kw) -> dict | None:
    """Replay one logged run. Returns None when the log has no structured tests or an unknown scenario."""
    tests = run.get("tests") or []
    if not tests or any(t.get("category") is None for t in tests):
        return None
    try:
        scenario = get_scenario(run.get("scenario_id"))
    except ValueError:
        return None
    truth = truth_set(scenario)
    gate = Controller(max_tests=max(12, len(tests)), subject=scenario.subject)  # same relevance rules as the controller
    belief = Belief(**belief_kw)
    stop_at = stop_correct = None
    used = 0
    trace = []
    for t in tests:
        r = ToolResult(t["tool"], dict(t.get("args") or {}), str(t.get("output", "")), bool(t["ok"]),
                       t["category"], t.get("evidence", True) is not False)
        counts = r.category != "invalid" and r.evidence and gate._relevant(r)
        if counts and belief.update(r.category, r.ok):
            used += 1
        trace.append((len(trace) + 1, round(belief.confidence(), 4), sorted(belief.diagnosis())))
        if stop_at is None and counts and belief.confidence() >= tau:
            stop_at, stop_correct = len(trace), belief.diagnosis() == truth
    score = run.get("score") or {}
    agent = answer_set(run.get("answer"))
    return {
        "scenario": run.get("scenario_id"), "mode": run.get("mode"), "agent_tests": len(tests),
        "agent_correct": bool(score.get("correct")) if score else None,
        "agent_answer_matches_truth": None if agent is None else agent == truth,
        "stop_at": stop_at, "stop_correct": stop_correct,
        "final_confidence": belief.confidence(), "final_correct": belief.diagnosis() == truth,
        "readings_used": used, "trace": trace,
    }


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def summarise(rows: list[dict]) -> dict:
    """Aggregate replayed runs of one group."""
    reached = [r for r in rows if r["stop_at"] is not None]
    belief_tests = [r["stop_at"] if r["stop_at"] is not None else r["agent_tests"] for r in rows]
    return {
        "runs": len(rows),
        "agent_tests": _mean(r["agent_tests"] for r in rows),
        "belief_tests": _mean(belief_tests),
        "reached": len(reached) / len(rows),
        "stop_correct": _mean(1.0 if r["stop_correct"] else 0.0 for r in reached) if reached else float("nan"),
        "confidently_wrong": sum(1 for r in reached if not r["stop_correct"]),
        "final_correct": _mean(1.0 if r["final_correct"] else 0.0 for r in rows),
        "agent_correct": _mean(1.0 if r["agent_correct"] else 0.0 for r in rows if r["agent_correct"] is not None),
    }


def load(paths) -> list[tuple[str, dict]]:
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append((p, json.loads(line)))
    return out


def report(paths, taus=(0.95,), **belief_kw) -> str:
    runs = load(paths)
    lines = ["## Belief replay (offline, no model calls)", "",
             f"Belief model: independent causes (DNS, route, port), noisy readings {belief_kw or 'default'}; "
             "belief stop = first test after which the most likely explanation has posterior >= tau.", ""]
    for tau in taus:
        groups = defaultdict(list)
        skipped = 0
        for path, run in runs:
            res = replay_run(run, tau, **belief_kw)
            if res is None:
                skipped += 1
                continue
            groups[(path.replace("\\", "/").rsplit("/", 1)[-1], res["mode"])].append(res)
        lines += [f"### tau = {tau}", "",
                  "| Log | Mode | Runs | Agent tests | Belief-stop tests | Reached tau | MAP right at stop | Confidently wrong | MAP right on all tests | Agent correct |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for (name, mode), rows in sorted(groups.items()):
            s = summarise(rows)
            lines.append(f"| {name} | {mode} | {s['runs']} | {s['agent_tests']:.1f} | {s['belief_tests']:.1f} | "
                         f"{s['reached']:.0%} | {s['stop_correct']:.0%} | {s['confidently_wrong']} | "
                         f"{s['final_correct']:.0%} | {s['agent_correct']:.0%} |")
        if skipped:
            lines += ["", f"({skipped} run(s) skipped: no structured tests or unknown scenario.)"]
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("logs", nargs="+", help="run log files or globs, e.g. results/run-*.jsonl")
    p.add_argument("--tau", nargs="+", type=float, default=[0.95])
    p.add_argument("--prior", type=float, default=0.25, help="prior probability that each cause is broken")
    p.add_argument("--false-fail", type=float, default=0.08, help="chance a working path fails one check")
    p.add_argument("--miss", type=float, default=0.15, help="chance a broken area passes one check")
    a = p.parse_args(argv)
    paths = sorted({f for g in a.logs for f in (glob.glob(g) or [g])})
    print(report(paths, a.tau, prior=a.prior, false_fail=a.false_fail, miss=a.miss))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
