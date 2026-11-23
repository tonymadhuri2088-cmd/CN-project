"""Final-validation report: one table per labelled log file, with every metric and 95% intervals.

    python -m netwing.final_report original=results/run-A.jsonl hint=results/run-B.jsonl ... [--mode netwing]

Metrics (per configuration and mode). Truth comes from the scenario, never from the model:
  exact diagnosis        answer names every injected fault and nothing else (score.complete)
  healthy accuracy       healthy networks answered "healthy"
  false fault            healthy networks answered "fault"
  missed fault           faulty networks answered "healthy"
  wrong fault type       faulty networks answered "fault" with a type not injected
  extra fault claimed    faulty networks where the answer also lists a fault that was not injected (an unsupported
                         extra claim: the main fault can be right and the run still not exact)
  no answer              no accepted answer (cap, rejection limit, error, inconclusive), over all runs
  multi-fault            runs of scenarios with 2+ injected faults: exact vs partial (right type, not all)
  mean tests / cost      from the log; latency is the span of the first to the last test timestamp (a proxy: it
                         excludes the final model call, which the log does not time)
Proportions use Wilson 95% intervals; means use mean +/- 1.96 standard errors.
"""
from __future__ import annotations

import argparse
import json
import math

from .runner import wilson
from .scenarios import get_scenario


def _pct(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.0f}% [{100 * lo:.0f}-{100 * hi:.0f}] ({k}/{n})"


def _mean(xs: list[float], digits: int = 1) -> str:
    if not xs:
        return "n/a"
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
    return f"{m:.{digits}f} ±{1.96 * sd / math.sqrt(len(xs)):.{digits}f}"


def load(path: str) -> list[dict]:
    """Read a JSONL run log into a list of dicts."""
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def metrics(rows: list[dict]) -> dict:
    """Every reported metric (exact diagnosis, healthy answered healthy, false/missed fault, extra claims, suspected claims, no answer, multi-fault exactness, tests, cost, latency) for a set of runs."""
    n = len(rows)
    healthy = [r for r in rows if get_scenario(r["scenario_id"]).truth == "healthy"]
    faulty = [r for r in rows if get_scenario(r["scenario_id"]).truth != "healthy"]
    multi = [r for r in faulty if len(get_scenario(r["scenario_id"]).also) > 0]

    def verdict(r):
        a = r.get("answer")
        return a.get("verdict") if isinstance(a, dict) else None

    def sc(r, k):
        return bool((r.get("score") or {}).get(k))

    def extra(r):
        a = r.get("answer")
        if not isinstance(a, dict) or a.get("verdict") != "fault":
            return False
        sc_ = get_scenario(r["scenario_id"])
        truths = {sc_.truth, *sc_.also}
        claimed = {a.get("fault_type"), *(a.get("other_faults") or [])} - {None, "none"}
        return bool(claimed - truths)

    def exact_incl(r):  # logs written before tiered claims have no such field: it equals the strict score there
        s = r.get("score") or {}
        return bool(s.get("complete_incl_suspected", s.get("complete")))

    def extra_incl(r):
        a = r.get("answer")
        if not isinstance(a, dict) or a.get("verdict") != "fault":
            return False
        sc_ = get_scenario(r["scenario_id"])
        truths = {sc_.truth, *sc_.also}
        claimed = {a.get("fault_type"), *(a.get("other_faults") or []), *(a.get("suspected_faults") or [])} - {None, "none"}
        return bool(claimed - truths)

    span = []
    for r in rows:
        ts = [t["ts"] for t in r.get("tests") or [] if "ts" in t]
        if len(ts) > 1:
            span.append(max(ts) - min(ts))
    return {
        "runs": n,
        "exact": (sum(sc(r, "complete") for r in rows), n),
        "healthy_ok": (sum(verdict(r) == "healthy" for r in healthy), len(healthy)),
        "false_fault": (sum(verdict(r) == "fault" for r in healthy), len(healthy)),
        "missed": (sum(verdict(r) == "healthy" for r in faulty), len(faulty)),
        "wrong_type": (sum(verdict(r) == "fault" and not sc(r, "correct") for r in faulty), len(faulty)),
        "extra": (sum(extra(r) for r in faulty), len(faulty)),
        "exact_incl": (sum(exact_incl(r) for r in rows), n),
        "extra_incl": (sum(extra_incl(r) for r in faulty), len(faulty)),
        "multi_exact_incl": (sum(exact_incl(r) for r in multi), len(multi)),
        "suspected_claims": sum(len((r.get("answer") or {}).get("suspected_faults") or []) for r in rows if isinstance(r.get("answer"), dict)),
        "no_answer": (sum(sc(r, "no_answer") for r in rows), n),
        "multi_exact": (sum(sc(r, "complete") for r in multi), len(multi)),
        "multi_partial": (sum(sc(r, "correct") and not sc(r, "complete") for r in multi), len(multi)),
        "tests": [r["tests_run"] for r in rows],
        "cost": [r["cost_usd"] for r in rows],
        "latency": span,
        "basis": sum(1 for r in healthy if verdict(r) == "healthy" and str(r.get("healthy_basis", "")).startswith(("hybrid", "belief"))),
    }


HEAD = ("| Config | Mode | Runs | Exact diagnosis | Healthy answered healthy | False fault | Missed fault | Wrong type | "
        "Extra fault claimed | No answer | Multi exact | Multi partial | Mean tests | Mean cost $ | Mean latency s | "
        "Exact incl. suspected | Multi exact incl. suspected | Extra incl. suspected | Suspected claims |")


def row(label: str, mode: str, rows: list[dict]) -> str:
    """One markdown table row of `metrics` for a labelled configuration."""
    m = metrics(rows)
    return (f"| {label} | {mode} | {m['runs']} | {_pct(*m['exact'])} | {_pct(*m['healthy_ok'])} | {_pct(*m['false_fault'])} | "
            f"{_pct(*m['missed'])} | {_pct(*m['wrong_type'])} | {_pct(*m['extra'])} | {_pct(*m['no_answer'])} | {_pct(*m['multi_exact'])} | "
            f"{_pct(*m['multi_partial'])} | {_mean(m['tests'])} | {_mean(m['cost'], 4)} | {_mean(m['latency'])} | "
            f"{_pct(*m['exact_incl'])} | {_pct(*m['multi_exact_incl'])} | {_pct(*m['extra_incl'])} | {m['suspected_claims']} |")


def main(argv=None) -> int:
    """CLI entry: print one table per `label=path` log file."""
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("logs", nargs="+", help="label=path pairs")
    p.add_argument("--mode", default=None, help="only this mode (default: every mode in each file)")
    a = p.parse_args(argv)
    lines = [HEAD, "|" + "---|" * 19]
    for spec in a.logs:
        label, _, path = spec.partition("=")
        rows = load(path)
        for mode in ([a.mode] if a.mode else sorted({r["mode"] for r in rows})):
            sub = [r for r in rows if r["mode"] == mode]
            if sub:
                lines.append(row(label, mode, sub))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
