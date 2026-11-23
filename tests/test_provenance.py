"""Every run record says how it was produced, and a partly finished run can be resumed without mixing configurations."""
import json

import pytest

from netwing import provenance
from netwing.budget import CostGuard
from netwing.dryrun import DryRunClient
from netwing.runner import run_matrix
from netwing.sim import SimNetwork

PRICES = {"dry-run": {"input_per_mtok": 1.0, "output_per_mtok": 1.0}}


def _go(out, prov, repeats=2, resume=False, scenarios=("dns_failure", "healthy_false_alarm"), modes=("plain", "netwing")):
    return run_matrix(list(scenarios), list(modes), repeats, SimNetwork, DryRunClient(), CostGuard(50, 5, PRICES), "dry-run",
                      str(out), provenance=prov, resume=resume)


def test_build_records_the_facts_needed_to_reproduce_a_run():
    p = provenance.build({"suite": "hard", "repeats": 2}, model="m")
    assert len(p["invocation_id"]) == 32 and p["config_hash"] and p["config"] == {"suite": "hard", "repeats": 2}
    assert p["model"] == "m" and p["python"] and "temperature" in p  # temperature is recorded (null = API default)
    assert set(p) >= {"git_commit", "git_dirty", "started_at", "platform", "netwing_version"}


def test_config_hash_ignores_key_order_and_changes_with_content():
    a = provenance.build({"x": 1, "y": 2}, "m")["config_hash"]
    assert a == provenance.build({"y": 2, "x": 1}, "m")["config_hash"]
    assert a != provenance.build({"x": 1, "y": 3}, "m")["config_hash"]
    assert a != provenance.build({"x": 1, "y": 2}, "other-model")["config_hash"]


def test_each_record_carries_invocation_id_repeat_and_provenance(tmp_path):
    out = tmp_path / "r.jsonl"
    prov = provenance.build({"k": 1}, "dry-run")
    _go(out, prov, repeats=2)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 8
    assert {r["invocation_id"] for r in rows} == {prov["invocation_id"]}
    assert sorted({r["repeat"] for r in rows}) == [0, 1]
    assert all(r["provenance"]["config_hash"] == prov["config_hash"] for r in rows)


def test_without_provenance_records_are_unchanged_apart_from_the_repeat_index(tmp_path):
    out = tmp_path / "r.jsonl"
    run_matrix(["dns_failure"], ["plain"], 1, SimNetwork, DryRunClient(), CostGuard(50, 5, PRICES), "dry-run", str(out))
    rec = json.loads(out.read_text())
    assert "provenance" not in rec and "invocation_id" not in rec and rec["repeat"] == 0


def test_resume_skips_finished_runs_and_completes_the_rest(tmp_path):
    out = tmp_path / "r.jsonl"
    prov = provenance.build({"k": 1}, "dry-run")
    _go(out, prov, repeats=1)  # first repeat only: 4 runs
    first = out.read_text()
    logs = _go(out, prov, repeats=2, resume=True)  # now ask for 2 repeats
    assert len(logs) == 4  # only repeat 1 was run
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert out.read_text().startswith(first) and len(rows) == 8
    assert {(r["repeat"], r["scenario_id"], r["mode"]) for r in rows} == {
        (rep, s, m) for rep in (0, 1) for s in ("dns_failure", "healthy_false_alarm") for m in ("plain", "netwing")}
    assert {r["invocation_id"] for r in rows} == {prov["invocation_id"]}  # one invocation, not two


def test_resume_of_a_complete_run_does_nothing(tmp_path):
    out = tmp_path / "r.jsonl"
    prov = provenance.build({"k": 1}, "dry-run")
    _go(out, prov, repeats=1)
    before = out.read_text()
    assert _go(out, prov, repeats=1, resume=True) == [] and out.read_text() == before


def test_resume_refuses_when_the_configuration_differs(tmp_path):
    out = tmp_path / "r.jsonl"
    _go(out, provenance.build({"k": 1}, "dry-run"), repeats=1)
    with pytest.raises(ValueError, match="configuration"):
        _go(out, provenance.build({"k": 2}, "dry-run"), repeats=2, resume=True)


def test_resume_refuses_a_log_written_without_provenance(tmp_path):
    out = tmp_path / "r.jsonl"
    run_matrix(["dns_failure"], ["plain"], 1, SimNetwork, DryRunClient(), CostGuard(50, 5, PRICES), "dry-run", str(out))
    with pytest.raises(ValueError, match="provenance"):
        _go(out, provenance.build({"k": 1}, "dry-run"), repeats=1, resume=True)


def test_resume_retries_runs_that_ended_in_error(tmp_path):
    out = tmp_path / "r.jsonl"
    prov = provenance.build({"k": 1}, "dry-run")
    _go(out, prov, repeats=1, scenarios=("dns_failure",), modes=("plain",))
    row = json.loads(out.read_text())
    row["status"] = "error"
    out.write_text(json.dumps(row) + "\n")
    logs = _go(out, prov, repeats=1, scenarios=("dns_failure",), modes=("plain",), resume=True)
    assert len(logs) == 1 and len(out.read_text().splitlines()) == 2  # the failed record is kept, a fresh one appended


def test_cli_resume_completes_a_log_and_refuses_a_changed_configuration(tmp_path):
    from netwing.demo import main

    out = tmp_path / "cli.jsonl"
    base = ["--dry-run", "--backend", "sim", "--scenarios", "dns_failure", "--modes", "plain", "--out", str(out)]
    assert main(base + ["--repeats", "1"]) == 0
    assert main(base + ["--repeats", "2", "--resume"]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["repeat"] for r in rows] == [0, 1] and len({r["invocation_id"] for r in rows}) == 1
    with pytest.raises(SystemExit, match="different configuration"):
        main(["--dry-run", "--backend", "sim", "--scenarios", "dns_failure", "--modes", "netwing", "--out", str(out),
              "--repeats", "3", "--resume"])
    with pytest.raises(SystemExit, match="--out"):
        main(["--dry-run", "--resume"])


def test_resume_with_a_missing_log_starts_fresh_and_blank_lines_are_ignored(tmp_path):
    out = tmp_path / "new.jsonl"
    prov = provenance.build({"k": 1}, "dry-run")
    assert len(_go(out, prov, repeats=1, scenarios=("dns_failure",), modes=("plain",), resume=True)) == 1
    out.write_text(out.read_text() + "\n\n", encoding="utf-8")  # trailing blank lines must not break a later resume
    assert _go(out, prov, repeats=1, scenarios=("dns_failure",), modes=("plain",), resume=True) == []


def test_resume_without_provenance_argument_is_refused(tmp_path):
    with pytest.raises(ValueError, match="provenance"):
        run_matrix(["dns_failure"], ["plain"], 1, SimNetwork, DryRunClient(), CostGuard(50, 5, PRICES), "dry-run",
                   str(tmp_path / "x.jsonl"), resume=True)
