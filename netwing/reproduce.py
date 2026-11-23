"""Reproduce every documented number from the raw run logs.

    python -m netwing.reproduce inventory [--results results]      # each log file split into its invocations
    python -m netwing.reproduce check [--claims docs/research/claims.json]   # exit 1 if any documented number differs
    python -m netwing.reproduce table results/fresh2_original.jsonl#2 [--mode netwing]

Why this exists. Run logs are written in append mode, so one file can hold several invocations (an aborted start, a
retry, the run that was reported). Numbers quoted from a whole file would silently mix them. An invocation boundary is
detected from the test timestamps: a gap of more than ``GAP_SECONDS`` between consecutive runs starts a new invocation.
This is a heuristic on the log content alone (older logs carry no invocation id); new logs also record one (see
``netwing.provenance``), which is used when present.

A *claim* ties one quoted number to the file, invocation, mode and metric that produce it, so a change in any log, in
the scoring, or in a document is caught by ``check`` and by the regression test.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

from .final_report import HEAD, load, metrics, row

GAP_SECONDS = 600.0


def _first_ts(rec: dict) -> float | None:
    ts = [t["ts"] for t in rec.get("tests") or [] if isinstance(t, dict) and "ts" in t]
    return min(ts) if ts else None


def split_invocations(rows: list[dict], gap: float = GAP_SECONDS) -> list[list[dict]]:
    """Split one append-mode log into invocations. Uses a recorded invocation id when every row has one, otherwise the
    time gap between consecutive runs. Rows without timestamps (dry runs, early errors) stay with the current group."""
    if rows and all(r.get("invocation_id") for r in rows):
        groups: dict[str, list[dict]] = {}
        for r in rows:
            groups.setdefault(r["invocation_id"], []).append(r)
        return list(groups.values())
    out: list[list[dict]] = [[]]
    prev: float | None = None
    for r in rows:
        t = _first_ts(r)
        if prev is not None and t is not None and t - prev > gap:
            out.append([])
        out[-1].append(r)
        if t is not None:
            prev = t
    return [g for g in out if g]


def select(path: str, invocation: int | None = None, mode: str | None = None) -> list[dict]:
    """Rows of one invocation (index into ``split_invocations``; None = the whole file) and optionally one mode."""
    rows = load(path)
    if invocation is not None:
        rows = split_invocations(rows)[invocation]
    return [r for r in rows if mode is None or r["mode"] == mode]


def measure_mean(rows: list[dict], metric: str) -> float:
    """Mean of ``tests`` or ``cost`` over the runs."""
    xs = metrics(rows)[metric]
    return sum(xs) / len(xs) if xs else float("nan")


def measure_count(rows: list[dict], metric: str) -> tuple[int, int]:
    """(k, n) for a proportion metric such as ``healthy_ok`` or ``no_answer``."""
    k, n = metrics(rows)[metric]
    return int(k), int(n)


def check_claim(claim: dict[str, Any], root: str = ".") -> tuple[str, str]:
    """('ok'|'FAIL'|'SKIP', detail) for one claim."""
    path = os.path.join(root, claim["file"])
    if not os.path.exists(path):
        return "SKIP", f"{claim['id']}: {claim['file']} not present"
    try:
        rows = select(path, claim.get("invocation"), claim.get("mode"))
    except IndexError:
        return "FAIL", f"{claim['file']} has no invocation {claim.get('invocation')}"
    if "mean" in claim:
        digits = claim.get("digits", 1)
        got = measure_mean(rows, claim["metric"])
        ok = round(got, digits) == round(claim["mean"], digits)
        return ("ok" if ok else "FAIL"), f"{claim['id']}: documented {claim['mean']}, log gives {round(got, digits)}"
    k, n = measure_count(rows, claim["metric"])
    ok = (k, n) == (claim["k"], claim["n"])
    return ("ok" if ok else "FAIL"), f"{claim['id']}: documented {claim['k']}/{claim['n']}, log gives {k}/{n}"


def check_all(claims: list[dict[str, Any]], root: str = ".") -> list[tuple[str, str, str]]:
    """[(status, claim id, detail)] for every claim."""
    out = []
    for c in claims:
        status, detail = check_claim(c, root)
        out.append((status, detail, c.get("doc", "")))
    return out


def inventory(results_dir: str) -> list[str]:
    """One line per invocation of every ``*.jsonl`` log in ``results_dir``."""
    lines = []
    for name in sorted(os.listdir(results_dir)):
        if not name.endswith(".jsonl"):
            continue
        rows = load(os.path.join(results_dir, name))
        for i, g in enumerate(split_invocations(rows)):
            modes = ",".join(f"{m}:{sum(r['mode'] == m for r in g)}" for m in sorted({r["mode"] for r in g}))
            lines.append(f"{name}#{i}\t{len(g)} runs\t{modes}")
    return lines


def main(argv: list[str] | None = None) -> int:
    """CLI entry (inventory | check | table)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--results", default="results")
    chk = sub.add_parser("check")
    chk.add_argument("--claims", default=os.path.join("docs", "research", "claims.json"))
    chk.add_argument("--root", default=".")
    chk.add_argument("--strict", action="store_true", help="treat a missing log as a failure (use in CI)")
    tab = sub.add_parser("table")
    tab.add_argument("spec", help="path or path#invocation")
    tab.add_argument("--mode", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "inventory":
        print("\n".join(inventory(a.results)))
        return 0
    if a.cmd == "check":
        with open(a.claims, encoding="utf-8") as fh:
            claims = json.load(fh)
        results = check_all(claims, a.root)
        for status, detail, doc in results:
            print(f"[{status:4}] {detail}" + (f"   ({doc})" if doc and status != "ok" else ""))
        bad = sum(s == "FAIL" or (a.strict and s == "SKIP") for s, _, _ in results)
        ok = sum(s == "ok" for s, _, _ in results)
        skipped = sum(s == "SKIP" for s, _, _ in results)
        print(f"{ok} ok, {sum(s == 'FAIL' for s, _, _ in results)} FAIL, {skipped} skipped of {len(results)} documented numbers"
              + (" (strict: skipped counts as failure)" if a.strict and skipped else ""))
        return 1 if bad else 0
    path, _, inv_s = a.spec.partition("#")
    rows = select(path, int(inv_s) if inv_s else None)
    print(HEAD)
    print("|" + "---|" * 19)
    for mode in ([a.mode] if a.mode else sorted({r["mode"] for r in rows})):
        sub_rows = [r for r in rows if r["mode"] == mode]
        if sub_rows:
            print(row(a.spec, mode, sub_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
