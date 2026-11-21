import json

import pytest

from netwing.budget import CostGuard
from netwing.demo import main
from netwing.runner import run_matrix, summarize
from netwing.sim import SimNetwork
from tests.fake_client import FakeClient, final

PRICES = {"m": {"input_per_mtok": 1.0, "output_per_mtok": 5.0}}


def guard(total=10.0):
    return CostGuard(total_cap_usd=total, per_run_cap_usd=5.0, prices=PRICES)


def four_runs(tmp_path, g=None, script=None):
    script = script or [[final(f"f{i}", "healthy", "none", [])] for i in range(4)]
    client = FakeClient(script)
    out = tmp_path / "runs.jsonl"
    logs = run_matrix(
        ["dns_failure", "healthy_false_alarm"], ["plain", "healthy_ok"], 1,
        SimNetwork, client, g or guard(), "m", str(out),
    )
    return logs, out


def test_matrix_writes_one_jsonl_line_per_run(tmp_path):
    logs, out = four_runs(tmp_path)
    lines = out.read_text().splitlines()
    assert len(logs) == 4 and len(lines) == 4
    rec = json.loads(lines[0])
    assert rec["simulated"] is True
    assert {"scenario_id", "mode", "score", "tests_run", "cost_usd", "status", "transcript"} <= rec.keys()


def test_summary_has_row_per_mode_and_simulated_heading(tmp_path):
    logs, _ = four_runs(tmp_path)
    text = summarize(logs, simulated=True)
    assert text.splitlines()[0].startswith("##") and "SIMULATED" in text.splitlines()[0]
    assert "| plain |" in text and "| healthy_ok |" in text
    assert "INCOMPLETE" not in text


def test_summary_computes_false_alarm_rate(tmp_path):
    script = [
        [final("a", "fault", "route_failure", [])],   # dns_failure / plain: wrong type
        [final("b", "fault", "dns_failure", [])],     # dns_failure / healthy_ok: correct
        [final("c", "fault", "route_failure", [])],   # healthy / plain: false alarm
        [final("d", "healthy", "none", [])],          # healthy / healthy_ok: correct
    ]
    logs, _ = four_runs(tmp_path, script=script)
    rows = {}
    for l in summarize(logs, True).splitlines():
        cells = [c.strip() for c in l.split("|")]
        if len(cells) > 4 and cells[1] in ("plain", "healthy_ok"):
            rows[cells[1]] = cells
    # cells: ['', mode, runs, correct, false alarms, ...]
    assert rows["plain"][3].split(" ")[0] == "0%" and rows["plain"][4].split(" ")[0] == "100%"
    assert rows["healthy_ok"][3].split(" ")[0] == "100%" and rows["healthy_ok"][4].split(" ")[0] == "0%"


def test_budget_exceeded_returns_partial_and_summary_says_incomplete(tmp_path):
    tiny = CostGuard(total_cap_usd=0.0000001, per_run_cap_usd=5.0, prices=PRICES)
    logs, out = four_runs(tmp_path, g=tiny)
    assert len(logs) == 1 and logs[0].status == "budget"
    assert len(out.read_text().splitlines()) == 1
    assert "INCOMPLETE" in summarize(logs, True)


def test_missing_api_key_without_dry_run_exits_with_clear_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as e:
        main(["--backend", "sim", "--repeats", "1"])
    assert "ANTHROPIC_API_KEY" in str(e.value)


def test_dry_run_end_to_end_needs_no_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "dry.jsonl"
    assert main(["--backend", "sim", "--dry-run", "--repeats", "1", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    first = printed.splitlines()[0]
    assert "SIMULATED" in printed and "DRY RUN" in printed
    assert "| plain |" in printed and "| healthy_ok |" in printed and "| netwing |" in printed
    assert len(out.read_text().splitlines()) == 12
    assert first.startswith("##")


def test_dry_run_netwing_finds_every_fault_and_stays_healthy(tmp_path, monkeypatch, capsys):
    out = tmp_path / "dry.jsonl"
    main(["--backend", "sim", "--dry-run", "--repeats", "1", "--out", str(out)])
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    nw = [r for r in recs if r["mode"] == "netwing"]
    assert len(nw) == 4 and all(r["score"]["correct"] for r in nw)
