"""SQLite に実験結果を記録する。"""
import json
import sqlite3
from datetime import datetime, timezone

from config import EXPERIMENTS_DB


def _init() -> None:
    EXPERIMENTS_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(EXPERIMENTS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                run_id    TEXT PRIMARY KEY,
                timestamp TEXT,
                cv_score  REAL,
                params    TEXT,
                notes     TEXT
            )
        """)


def log_run(run_id: str, cv_score: float, params: dict, notes: str = "") -> None:
    _init()
    with sqlite3.connect(EXPERIMENTS_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?)",
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                cv_score,
                json.dumps(params),
                notes,
            ),
        )
    print(f"[logger] run_id={run_id}  cv_score={cv_score:.5f}")


def show_runs() -> None:
    """直近 10 件を DuckDB で集計して表示する。"""
    import duckdb

    _init()
    duckdb.sql(f"""
        SELECT run_id, timestamp, cv_score, notes
        FROM read_csv_auto('{EXPERIMENTS_DB}')
    """)

    with sqlite3.connect(EXPERIMENTS_DB) as conn:
        rows = conn.execute(
            "SELECT run_id, timestamp, cv_score, notes FROM experiments ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()

    print(f"\n{'run_id':<20} {'timestamp':<28} {'cv_score':>10}  notes")
    print("-" * 80)
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<28} {r[2]:>10.5f}  {r[3]}")
