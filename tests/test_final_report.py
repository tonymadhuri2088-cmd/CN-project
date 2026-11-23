import json

from netwing.final_report import main, metrics


def run(sid, mode, answer, score, tests=3):
    return {"scenario_id": sid, "mode": mode, "answer": answer, "score": score, "tests_run": tests, "cost_usd": 0.002,
            "tests": [{"ts": 1.0}, {"ts": 3.5}]}


def sc(correct, complete=None, no_answer=False):
    return {"correct": correct, "complete": correct if complete is None else complete, "no_answer": no_answer,
            "false_alarm": False}


ROWS = [
    run("transient_blip", "netwing", {"verdict": "healthy", "fault_type": "none"}, sc(True)),
    run("transient_blip", "netwing", {"verdict": "fault", "fault_type": "route_failure"}, sc(False)),
    run("intermittent_port", "netwing", {"verdict": "healthy", "fault_type": "none"}, sc(False)),
    run("intermittent_port", "netwing", {"verdict": "fault", "fault_type": "port_blocked", "other_faults": ["dns_failure"]}, sc(True, False)),
    run("intermittent_port", "netwing", None, sc(False, no_answer=True)),
    run("multi_dns_port", "netwing", {"verdict": "fault", "fault_type": "dns_failure", "other_faults": []}, sc(True, False)),
]


def test_metrics_separate_each_kind_of_error():
    m = metrics(ROWS)
    assert m["runs"] == 6
    assert m["healthy_ok"] == (1, 2) and m["false_fault"] == (1, 2)
    assert m["missed"] == (1, 4)  # one faulty network answered healthy
    assert m["extra"] == (1, 4)  # right fault plus an unsupported extra one
    assert m["no_answer"] == (1, 6)
    assert m["multi_partial"] == (1, 1) and m["multi_exact"] == (0, 1)
    assert m["latency"] == [2.5] * 6


def test_cli_prints_a_table(tmp_path, capsys):
    f = tmp_path / "a.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in ROWS))
    assert main([f"orig={f}"]) == 0
    out = capsys.readouterr().out
    assert "| orig | netwing | 6 |" in out and "Extra fault claimed" in out


def test_suspected_claims_are_reported_apart_and_old_logs_fall_back_to_the_strict_score():
    rows = [
        run("multi_dns_port", "netwing", {"verdict": "fault", "fault_type": "dns_failure", "other_faults": [],
                                          "suspected_faults": ["port_blocked"]},
            dict(sc(True, False), complete_incl_suspected=True)),
        run("intermittent_port", "netwing", {"verdict": "fault", "fault_type": "port_blocked", "other_faults": [],
                                             "suspected_faults": ["dns_failure"]},
            dict(sc(True, True), complete_incl_suspected=False)),
        run("multi_dns_port", "netwing", {"verdict": "fault", "fault_type": "dns_failure"}, sc(True, True)),  # old log
    ]
    m = metrics(rows)
    assert m["exact_incl"] == (2, 3) and m["extra_incl"] == (1, 3) and m["extra"] == (0, 3)
    assert m["multi_exact_incl"] == (2, 2) and m["suspected_claims"] == 2
