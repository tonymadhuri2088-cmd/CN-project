"""Persistent investigation history (SQLite, stdlib). Imports run logs (results/*.jsonl) idempotently."""
from __future__ import annotations

import builtins
import glob
import json
import os
import sqlite3
import threading

from .records import build_record


class History:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.RLock()  # one connection is shared by the UI's request threads; serialise access to it
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, scenario TEXT, mode TEXT, verdict TEXT, "
            "correct INTEGER, false_alarm INTEGER, tests_run INTEGER, cost REAL, simulated INTEGER, record TEXT)"
        )
        self.db.commit()

    def import_dir(self, results_dir: str) -> int:
        with self._lock:
            return self._import_dir(results_dir)

    def _import_dir(self, results_dir: str) -> int:
        added = 0
        for path in sorted(glob.glob(os.path.join(results_dir, "run-*.jsonl"))):
            base = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = build_record(json.loads(line), f"{base}#{n}")
                    except (ValueError, KeyError):
                        continue
                    sc = rec["score"]
                    cur = self.db.execute(
                        "INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (rec["id"], rec["scenario"], rec["mode"], rec["verdict"],
                         int(bool(sc.get("correct"))), int(bool(sc.get("false_alarm"))), rec["tests_run"],
                         rec["cost_usd"], int(rec["simulated"]), json.dumps(rec)),
                    )
                    added += cur.rowcount
        self.db.commit()
        return added

    @staticmethod
    def _order(run_id: str) -> tuple:
        base, _, n = run_id.rpartition("#")
        return (base, int(n) if n.isdigit() else 0)

    def list(self, scenario: str = "", mode: str = "", limit: int = 200) -> builtins.list[dict]:
        rows, _total = self.list_page(scenario, mode, limit)
        return rows

    def list_page(self, scenario: str = "", mode: str = "", limit: int = 200) -> tuple[builtins.list[dict], int]:
        """Newest run file first, then run number ascending within a file. Returns (rows, total matching)."""
        q, args = ("SELECT id,scenario,mode,verdict,correct,false_alarm,tests_run,cost,simulated,"
                   "json_extract(record,'$.model') FROM runs WHERE 1=1"), []
        if scenario:
            q += " AND scenario=?"
            args.append(scenario)
        if mode:
            q += " AND mode=?"
            args.append(mode)
        cols = ("id", "scenario", "mode", "verdict", "correct", "false_alarm", "tests_run", "cost", "simulated", "model")
        with self._lock:
            rows = [dict(zip(cols, r)) for r in self.db.execute(q, args)]
        rows.sort(key=lambda r: self._order(r["id"])[1])
        rows.sort(key=lambda r: self._order(r["id"])[0], reverse=True)
        return rows[:limit], len(rows)

    def get(self, run_id: str) -> dict | None:
        with self._lock:
            row = self.db.execute("SELECT record FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def compare(self, a: str, b: str) -> dict | None:
        ra, rb = self.get(a), self.get(b)
        if not ra or not rb:
            return None
        ka = {(t["tool"], json.dumps(t["args"], sort_keys=True)) for t in ra["tests"]}
        kb = {(t["tool"], json.dumps(t["args"], sort_keys=True)) for t in rb["tests"]}
        return {"a": ra, "b": rb, "only_a": sorted(ka - kb), "only_b": sorted(kb - ka), "shared": len(ka & kb)}

    def stats(self, scenario: str = "", real_only: bool = True) -> builtins.list[dict]:
        """Per-mode totals for the (optionally filtered) runs. Dry-run stub records are excluded by default."""
        q = ("SELECT mode,COUNT(*),SUM(correct),SUM(false_alarm),AVG(tests_run),AVG(cost) FROM runs WHERE 1=1")
        args: list = []
        if scenario:
            q += " AND scenario=?"
            args.append(scenario)
        if real_only:
            q += " AND COALESCE(json_extract(record,'$.model'),'') != 'dry-run'"
        q += " GROUP BY mode ORDER BY mode"
        with self._lock:
            got = self.db.execute(q, args).fetchall()
        return [dict(mode=m, runs=n, correct=c or 0, false_alarms=f or 0, mean_tests=t, mean_cost=k)
                for m, n, c, f, t, k in got]

    def scenarios(self) -> builtins.list[str]:
        with self._lock:
            return [r[0] for r in self.db.execute("SELECT DISTINCT scenario FROM runs ORDER BY scenario")]
