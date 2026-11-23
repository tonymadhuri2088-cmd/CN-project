"""Hard USD spending caps for API calls."""
from __future__ import annotations

import json

# Used when the API response carries no usage numbers: count a deliberately
# generous estimate instead of zero so the cap can never be silently bypassed.
FALLBACK_INPUT_TOKENS = 8000
FALLBACK_OUTPUT_TOKENS = 1024


class BudgetExceeded(Exception):
    """Raised when a run or the whole matrix would pass its USD cap."""
    pass


def load_prices(path: str) -> dict:
    """Load per-million-token prices from `pricing.json`; refuses entries whose prices are not filled in."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    prices = {k: v for k, v in raw.items() if not k.startswith("_")}
    for model, p in prices.items():
        if p.get("input_per_mtok") is None or p.get("output_per_mtok") is None:
            raise ValueError(
                f"pricing for {model!r} is not filled in; copy the per-million-token "
                f"prices from Anthropic's pricing page into {path}"
            )
    return prices


class CostGuard:
    """Tracks token cost per run and in total against hard USD caps."""
    def __init__(self, total_cap_usd: float, per_run_cap_usd: float, prices: dict):
        self.total_cap = total_cap_usd
        self.run_cap = per_run_cap_usd
        self.prices = prices
        self.spent_total = 0.0
        self.spent_run = 0.0

    def start_run(self) -> None:
        """Reset the per-run spend."""
        self.spent_run = 0.0

    def add_usage(self, model: str, input_tokens, output_tokens) -> float:
        """Add one API call's token usage, return its cost, and raise `BudgetExceeded` if a cap would be passed."""
        if model not in self.prices:
            raise KeyError(f"no price configured for model {model!r}")
        p = self.prices[model]
        if input_tokens is None:
            input_tokens = FALLBACK_INPUT_TOKENS
        if output_tokens is None:
            output_tokens = FALLBACK_OUTPUT_TOKENS
        cost = (input_tokens * p["input_per_mtok"] + output_tokens * p["output_per_mtok"]) / 1_000_000
        self.spent_total += cost
        self.spent_run += cost
        if self.spent_total > self.total_cap:
            raise BudgetExceeded(f"total cap ${self.total_cap:.2f} exceeded (spent ${self.spent_total:.4f})")
        if self.spent_run > self.run_cap:
            raise BudgetExceeded(f"per-run cap ${self.run_cap:.2f} exceeded (spent ${self.spent_run:.4f})")
        return cost
