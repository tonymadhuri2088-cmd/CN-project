"""CLI: python -m netwing.demo --backend sim|kathara [--dry-run] [--repeats N] [--cap USD]"""
from __future__ import annotations

import argparse
import os
import shutil
import time

from .budget import CostGuard, load_prices
from .runner import run_matrix, summarize
from .scenarios import ALL_IDS, CAMPUS_IDS, FLAKY_IDS, FRESH2_IDS, FRESH3_IDS, FRESH_IDS, HARD_IDS, HELDOUT_IDS, LAB_IDS, MULTI_IDS
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
    p.add_argument("--suite", choices=["easy", "hard", "flaky", "multi", "campus", "lab", "heldout", "fresh", "fresh2", "fresh3", "all"], default="easy",
                   help="easy: four basic cases; hard: plus red-herring alerts; flaky: transient/intermittent; "
                        "multi: two faults at once; campus: bigger network; lab and heldout: simulator-only extra suites; all: easy+hard+flaky+multi+campus")
    p.add_argument("--scenarios", nargs="+", default=None, choices=ALL_IDS + HARD_IDS + FLAKY_IDS + MULTI_IDS + CAMPUS_IDS + LAB_IDS + HELDOUT_IDS + FRESH_IDS + FRESH2_IDS + FRESH3_IDS,
                   help="explicit scenario ids (overrides --suite)")
    p.add_argument("--modes", nargs="+", default=MODES, choices=MODES)
    p.add_argument("--lab-root", default="labs", help="kathara lab folders, one per scenario id")
    p.add_argument("--inventory", action=argparse.BooleanOptionalAction, default=True,
                   help="tell every mode which names refer to the same server (a network inventory); "
                        "on by default, --no-inventory turns it off")
    p.add_argument("--allow-inconclusive", action="store_true",
                   help="let the model answer 'inconclusive' when the evidence conflicts or is insufficient "
                        "(off by default so the published results stay comparable)")
    p.add_argument("--guide-citations", action="store_true",
                   help="netwing mode only: when a fault claim is rejected for citing the wrong results, the message "
                        "names the failing results it could cite (off by default; the published tables used the plain message)")
    p.add_argument("--auto-cite", action="store_true",
                   help="netwing mode only: judge a fault claim by the failing evidence the run gathered, not by "
                        "which result ids the model cited (off by default; the published tables used the strict rule)")
    p.add_argument("--healthy-strategy", choices=["rules", "hybrid", "belief"], default="rules",
                   help="netwing mode only: how a healthy verdict may be reached. rules (default): the published rule. "
                        "hybrid: also accept healthy when every standing failure was retested by the identical check, its "
                        "latest retest passed, none is reproduced, and the belief P(healthy) reaches --belief-tau. "
                        "belief: experimental, belief alone (ignores standing failures; for comparison only)")
    p.add_argument("--belief-tau", type=float, default=0.85,
                   help="P(healthy) needed by --healthy-strategy hybrid/belief (default 0.85, between 0.5 and 1)")
    p.add_argument("--retest-hint", action="store_true",
                   help="netwing mode only: tell the agent which results do not count and what a standing failure needs "
                        "to clear (guidance only; changes no verdict)")
    p.add_argument("--validate-claims", action="store_true",
                   help="netwing mode only: drop secondary fault claims (other_faults) that lack their own reproduced, "
                        "relevant evidence; the primary gate is unchanged and every drop is logged")
    p.add_argument("--tier-claims", action="store_true",
                   help="with claim validation: keep a secondary claim backed by a single sighting as a flagged "
                        "'suspected' fault instead of dropping it (implies --validate-claims)")
    p.add_argument("--resolver-hosts", nargs="+", default=None,
                   help="hosts that have a DNS resolver; the belief ignores DNS readings from any other host "
                        "(default: every host counts)")
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
    suites["all"] = [i for ids in suites.values() for i in ids]  # "all" does not include the lab or held-out suites
    suites["lab"] = LAB_IDS
    suites["fresh3"] = FRESH3_IDS  # simulator only; frozen before tiered claims were written: run once
    suites["fresh2"] = FRESH2_IDS  # simulator only; frozen before claim validation was written: run once
    suites["fresh"] = FRESH_IDS  # simulator only; validation set for the opt-in healthy strategies: run once
    suites["heldout"] = HELDOUT_IDS  # also not part of "all": run it once on frozen code
    return suites[args.suite]


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.backend != "sim" and set(_scenario_ids(args)) & (set(LAB_IDS) | set(HELDOUT_IDS) | set(FRESH_IDS) | set(FRESH2_IDS) | set(FRESH3_IDS)):
        raise SystemExit("the lab and held-out scenarios exist only in the simulator: use --backend sim")
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
        inventory=args.inventory, allow_inconclusive=args.allow_inconclusive,
        guide_citations=args.guide_citations, auto_cite=args.auto_cite,
        healthy_strategy=args.healthy_strategy, belief_tau=args.belief_tau, retest_hint=args.retest_hint, validate_claims=args.validate_claims or args.tier_claims, tier_claims=args.tier_claims,
        resolver_hosts=set(args.resolver_hosts) if args.resolver_hosts else None,
    )
    print(summarize(logs, simulated=args.backend == "sim", dry_run=args.dry_run))
    print(f"\nlogs: {out}   total spend: ${guard.spent_total:.4f} (cap ${args.cap:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
