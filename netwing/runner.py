"""Run scenarios x modes x repeats, log JSONL, summarize in one table."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Callable

from .agent import RunLog, run_diagnosis
from .backend import NetworkBackend
from .budget import CostGuard
from .scenarios import Scenario, get_scenario
from .scoring import score

MAX_TESTS = {"plain": 12, "healthy_ok": 12, "netwing": 12}


def run_matrix(
    scenario_ids: list[str],
    modes: list[str],
    repeats: int,
    backend_factory: Callable[[Scenario], NetworkBackend],
    client,
    guard: CostGuard,
    model: str,
    out_path: str,
    inventory: bool = False,
    allow_inconclusive: bool = False,
    guide_citations: bool = False,
    auto_cite: bool = False,
    healthy_strategy: str = "rules",
    belief_tau: float = 0.85,
    retest_hint: bool = False,
    resolver_hosts=None,
) -> list[RunLog]:
    logs: list[RunLog] = []
    with open(out_path, "a", encoding="utf-8") as out:
        for _rep in range(repeats):  # repeats outermost: a partial run stays balanced
            for sid in scenario_ids:
                scenario = get_scenario(sid)
                for mode in modes:
                    backend = backend_factory(scenario)
                    log = run_diagnosis(scenario, backend, mode, client, guard, model, MAX_TESTS[mode], inventory, allow_inconclusive, guide_citations, auto_cite,
                                         healthy_strategy, belief_tau, retest_hint, resolver_hosts)
                    logs.append(log)
                    rec = log.to_dict()
                    rec["score"] = asdict(score(scenario, log.answer))
                    rec["simulated"] = bool(getattr(backend, "simulated", False))
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    if log.status in ("budget", "error"):
                        return logs
    return logs


def _pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{round(100 * n / d)}%"


def wilson(n: int, d: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion n/d (sound for small samples and for 0% or 100%)."""
    if d == 0:
        return 0.0, 1.0
    p = n / d
    den = 1 + z * z / d
    centre = (p + z * z / (2 * d)) / den
    half = z * ((p * (1 - p) / d + z * z / (4 * d * d)) ** 0.5) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def _ci(n: int, d: int) -> str:
    if d == 0:
        return "n/a"
    lo, hi = wilson(n, d)
    return f"{round(100 * n / d)}% [{round(100 * lo)}-{round(100 * hi)}]"


def _spread(xs: list[float]) -> str:
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return f"{m:.1f}"
    sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    return f"{m:.1f} ±{1.96 * sd / len(xs) ** 0.5:.1f}"


def summarize(logs: list[RunLog], simulated: bool, dry_run: bool = False) -> str:
    where = "SIMULATED network" if simulated else "real network"
    head = f"## NetWing demo results ({where})"
    if dry_run:
        head += " - DRY RUN: scripted stub, no API calls; proves the pipeline only"
    stopped = [l for l in logs if l.status in ("budget", "error")]
    done = [l for l in logs if l.status not in ("budget", "error")]
    has_multi = any(get_scenario(l.scenario_id).also for l in done)
    cols = ["Mode", "Runs", "Correct [95% CI]", "False alarms (healthy case) [95% CI]",
            "Healthy answered correctly", "No answer", "Mean tests ±95%", "Mean cost"]
    if has_multi:
        cols.append("All faults found (multi-fault cases) [95% CI]")
    lines = [head, "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for mode in list(dict.fromkeys(l.mode for l in logs)):
        ml = [l for l in done if l.mode == mode]
        if not ml:
            lines.append("| " + " | ".join([mode, "0"] + ["n/a"] * (len(cols) - 2)) + " |")
            continue
        scores = [(l, score(get_scenario(l.scenario_id), l.answer)) for l in ml]
        healthy = [s for l, s in scores if get_scenario(l.scenario_id).truth == "healthy"]
        multi = [s for l, s in scores if get_scenario(l.scenario_id).also]
        row = [
            mode, str(len(ml)), _ci(sum(s.correct for _, s in scores), len(ml)),
            _ci(sum(s.false_alarm for s in healthy), len(healthy)),
            _pct(sum(s.correct for s in healthy), len(healthy)),
            str(sum(s.no_answer for _, s in scores)),
            _spread([l.tests_run for l in ml]), f"${sum(l.cost_usd for l in ml) / len(ml):.4f}",
        ]
        if has_multi:
            row.append(_ci(sum(s.complete for s in multi), len(multi)))
        lines.append("| " + " | ".join(row) + " |")
    if stopped:
        why = "; ".join(f"{l.mode}/{l.scenario_id}: {l.status}" + (f" ({l.error})" if l.error else "") for l in stopped)
        lines += ["", f"INCOMPLETE: the matrix stopped early ({why}). Stopped runs are excluded from the averages."]
    return "\n".join(lines)
