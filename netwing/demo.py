"""CLI: python -m netwing.demo --backend sim|kathara [--dry-run] [--repeats N] [--cap USD]"""
from __future__ import annotations

import argparse
import os
import shutil
import time

from .budget import CostGuard, load_prices
from .runner import run_matrix, summarize
from .scenarios import ALL_IDS, CAMPUS_IDS, FLAKY_IDS, HARD_IDS, LAB_IDS, MULTI_IDS
from .sim import SimNetwork

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = ["plain", "healthy_ok", "netwing"]


def build_parser():
    p = argparse.ArgumentParser(prog="netwing.demo")
    p.add_argument("--backend", choices=["sim", "kathara", "netns"], default="sim")
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--cap", type=float, default=15.0, help="hard total USD cap")
    p.add_argument("--run-cap", type=float, default=0.50, help="hard USD cap per run")
    p.add_argument("--model", default=os.environ.get("NETWING_MODEL", "claude-haiku-5-5"))
    p.add_argument("--dry-run", action="store_true", help="scripted stub client, zero API spend")
    p.add_argument("--suite", choices=["easy", "hard", "flaky", "multi", "campus", "lab", "all"], default="easy",
                   help="easy: four basic cases; hard: plus red-herring alerts; flaky: transient/intermittent; "
                        "multi: two faults at once; campus: bigger network; all: everything")
    p.add_argument("--scenarios", nargs="+", default=None, choices=ALL_IDS + HARD_IDS + FLAKY_IDS + MULTI_IDS + CAMPUS_IDS + LAB_IDS,
                   help="explicit scenario ids (overrides --suite)")
    p.add_argument("--modes", nargs="+", default=MODES, choices=MODES)
    p.add_argument("--lab-root", default="labs", help="kathara lab folders, one per scenario id")
    p.add_argument("--inventory", action=argparse.BooleanOptionalAction, default=True,
                   help="tell every mode which names refer to the same server (a network inventory); "
                        "on by default, --no-inventory turns it off")
    p.add_argument("--out", default=None)
    return p


def _backend_factory(args):
    if args.backend == "sim":
        return SimNetwork
    if args.backend == "netns":
        from .netns import NetnsNetwork, available
        ok, why = available()
        if not ok:
            raise SystemExit(f"the netns backend is not available here: {why}")
        return lambda scenario: NetnsNetwork(scenario.id, args.lab_root)
    try:
        from .kathara import KatharaNetwork
    except ImportError as e:  # pragma: no cover - Task 7 module, Linux only
        raise SystemExit(f"the kathara backend is not available here: {e}") from e
    return lambda scenario: KatharaNetwork(os.path.join(args.lab_root, scenario.id))


def _scenario_ids(args):
    if args.scenarios:
        return args.scenarios
    suites = {"easy": ALL_IDS, "hard": HARD_IDS, "flaky": FLAKY_IDS, "multi": MULTI_IDS, "campus": CAMPUS_IDS}
    suites["all"] = [i for ids in suites.values() for i in ids]  # "all" does not include the lab suite
    suites["lab"] = LAB_IDS
    return suites[args.suite]


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.backend != "sim" and set(_scenario_ids(args)) & set(LAB_IDS):
        raise SystemExit("the lab scenarios (latency, packet loss, misleading complaint) exist only in the simulator: use --backend sim")
    if args.backend == "kathara" and shutil.which("kathara") is None:
        raise SystemExit("the 'kathara' command was not found; install Kathara and Docker first (see SETUP_LINUX.md)")
    if args.dry_run:
        from .dryrun import DryRunClient

        client, model = DryRunClient(), "dry-run"
        prices = {"dry-run": {"input_per_mtok": 1.0, "output_per_mtok": 1.0}}
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set. Set it in your shell (never paste it into chat), "
                "or use --dry-run to test the pipeline without the API."
            )
        try:
            prices = load_prices(os.path.join(HERE, "pricing.json"))
        except ValueError as e:
            raise SystemExit(str(e)) from e
        if args.model not in prices:
            raise SystemExit(f"no price configured for model {args.model!r} in netwing/pricing.json")
        try:
            import anthropic
        except ImportError as e:
            raise SystemExit("the anthropic package is missing: pip install anthropic") from e
        client, model = anthropic.Anthropic(), args.model

    out = args.out or os.path.join("results", f"run-{time.strftime('%Y%m%d-%H%M%S')}.jsonl")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    guard = CostGuard(args.cap, args.run_cap, prices)
    logs = run_matrix(
        _scenario_ids(args), args.modes, args.repeats, _backend_factory(args), client, guard, model, out,
        inventory=args.inventory,
    )
    print(summarize(logs, simulated=args.backend == "sim", dry_run=args.dry_run))
    print(f"\nlogs: {out}   total spend: ${guard.spent_total:.4f} (cap ${args.cap:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
