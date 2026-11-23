"""The documented numbers must be reproducible from the raw logs, and the tool must notice when they are not."""
import json
import os

import pytest

from netwing import reproduce
from netwing.reproduce import check_claim, split_invocations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "run-sample.jsonl")


def _row(ts, mode="netwing", scenario="dns_failure"):
    return {"scenario_id": scenario, "mode": mode, "tests": [{"ts": ts}] if ts is not None else [], "tests_run": 1,
            "cost_usd": 0.0, "answer": None, "score": {"no_answer": True}}


def test_gap_starts_a_new_invocation_and_untimed_rows_stay_with_the_current_one():
    rows = [_row(0), _row(30), _row(None), _row(5000), _row(5030)]
    groups = split_invocations(rows)
    assert [len(g) for g in groups] == [3, 2]


def test_recorded_invocation_id_wins_over_the_time_heuristic():
    rows = [dict(_row(0), invocation_id="a"), dict(_row(10), invocation_id="b"), dict(_row(20), invocation_id="a")]
    assert [len(g) for g in split_invocations(rows)] == [2, 1]


def test_check_claim_detects_a_changed_number(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text("\n".join(json.dumps(_row(i)) for i in range(4)), encoding="utf-8")
    base = {"id": "x", "file": "log.jsonl", "invocation": 0, "mode": "netwing", "metric": "no_answer"}
    assert check_claim({**base, "k": 4, "n": 4}, str(tmp_path))[0] == "ok"
    assert check_claim({**base, "k": 3, "n": 4}, str(tmp_path))[0] == "FAIL"
    assert check_claim({**base, "metric": "tests", "mean": 1.0}, str(tmp_path))[0] == "ok"
    assert check_claim({**base, "metric": "tests", "mean": 2.0}, str(tmp_path))[0] == "FAIL"
    assert check_claim({**base, "invocation": 5, "k": 0, "n": 0}, str(tmp_path))[0] == "FAIL"
    assert check_claim({**base, "file": "missing.jsonl", "k": 0, "n": 0}, str(tmp_path))[0] == "SKIP"


def test_every_documented_number_reproduces_from_the_logs():
    claims_path = os.path.join(ROOT, "docs", "research", "claims.json")
    if not os.path.exists(claims_path):
        pytest.skip("claims file not present")
    claims = json.load(open(claims_path, encoding="utf-8"))
    results = reproduce.check_all(claims, ROOT)
    if all(s == "SKIP" for s, _, _ in results):
        pytest.skip("run logs not present in this checkout")
    failed = [d for s, d, _ in results if s == "FAIL"]
    assert not failed, "documented number(s) no longer match the raw logs:\n" + "\n".join(failed)
    assert len(claims) >= 40  # guards against the claims file being emptied


def _write_log(path, n=4, mode="netwing"):
    path.write_text("\n".join(json.dumps(_row(i, mode)) for i in range(n)), encoding="utf-8")


def test_cli_inventory_check_and_table(tmp_path, capsys):
    res = tmp_path / "results"
    res.mkdir()
    _write_log(res / "a.jsonl")
    (res / "ignore.txt").write_text("x")
    assert reproduce.main(["inventory", "--results", str(res)]) == 0
    assert "a.jsonl#0\t4 runs\tnetwing:4" in capsys.readouterr().out

    claims = tmp_path / "claims.json"
    good = [{"id": "c1", "file": "results/a.jsonl", "invocation": 0, "mode": "netwing", "metric": "no_answer", "k": 4, "n": 4},
            {"id": "c2", "file": "results/gone.jsonl", "invocation": 0, "mode": "netwing", "metric": "no_answer", "k": 0, "n": 0}]
    claims.write_text(json.dumps(good))
    assert reproduce.main(["check", "--claims", str(claims), "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[ok  ] c1" in out and "[SKIP] c2" in out and "1 ok, 0 FAIL, 1 skipped of 2" in out

    assert reproduce.main(["check", "--claims", str(claims), "--root", str(tmp_path), "--strict"]) == 1  # c2's log is missing
    assert "strict" in capsys.readouterr().out
    good[0]["k"] = 1
    claims.write_text(json.dumps(good))
    assert reproduce.main(["check", "--claims", str(claims), "--root", str(tmp_path)]) == 1
    assert "FAIL" in capsys.readouterr().out

    assert reproduce.main(["table", str(res / "a.jsonl#0")]) == 0
    assert "| netwing |" in capsys.readouterr().out
