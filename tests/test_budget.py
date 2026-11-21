import json

import pytest

from netwing.budget import BudgetExceeded, CostGuard, load_prices

PRICES = {"m": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}


def guard(total=10.0, run=5.0):
    return CostGuard(total_cap_usd=total, per_run_cap_usd=run, prices=PRICES)


def test_cost_accumulates():
    g = guard()
    g.start_run()
    cost = g.add_usage("m", 1_000_000, 0)
    assert cost == pytest.approx(1.0)
    assert g.spent_total == pytest.approx(1.0)
    assert g.spent_run == pytest.approx(1.0)


def test_output_tokens_priced_separately():
    g = guard()
    g.start_run()
    assert g.add_usage("m", 0, 1_000_000) == pytest.approx(5.0)


def test_raises_over_total_cap():
    g = guard(total=1.5, run=100.0)
    g.start_run()
    g.add_usage("m", 1_000_000, 0)
    with pytest.raises(BudgetExceeded):
        g.add_usage("m", 1_000_000, 0)


def test_raises_over_run_cap_then_start_run_resets_run_total_but_not_total():
    g = guard(total=100.0, run=1.5)
    g.start_run()
    g.add_usage("m", 1_000_000, 0)
    with pytest.raises(BudgetExceeded):
        g.add_usage("m", 1_000_000, 0)
    total_before = g.spent_total
    g.start_run()
    assert g.spent_run == 0
    assert g.spent_total == pytest.approx(total_before)


def test_missing_usage_counts_conservative_estimate():
    g = guard()
    g.start_run()
    cost = g.add_usage("m", None, None)
    assert cost > 0
    assert g.spent_total == pytest.approx(cost)


def test_missing_price_raises_clear_error():
    g = guard()
    g.start_run()
    with pytest.raises(KeyError, match="no price"):
        g.add_usage("unknown-model", 10, 10)


def test_load_prices_rejects_null_prices(tmp_path):
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps({"m": {"input_per_mtok": None, "output_per_mtok": None}}))
    with pytest.raises(ValueError, match="pricing"):
        load_prices(str(p))


def test_load_prices_reads_numbers(tmp_path):
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps({"m": {"input_per_mtok": 1, "output_per_mtok": 5}}))
    assert load_prices(str(p))["m"]["output_per_mtok"] == 5


def test_shipped_pricing_file_is_filled_in_for_default_model():
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "netwing", "pricing.json")
    prices = load_prices(path)
    assert prices["claude-haiku-5-5"]["input_per_mtok"] > 0
    assert prices["claude-haiku-5-5"]["output_per_mtok"] > 0
