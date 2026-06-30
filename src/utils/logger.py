"""実験結果を BigQuery (`<dataset>.experiments`) に記録する。

tabular メタデータの正本は BigQuery に統一する方針（ADR 0002）。run_id で
`cost_estimates` と JOIN でき、実験スコアと概算コストを 1 クエリで突き合わせられる。
gcpProject 未設定 / オフライン時は no-op（ローカル smoke を止めない）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from config import COMP, METRIC
from utils import bq

_TABLE_NAME = "experiments"
_COLUMNS = ["run_id", "recorded_at", "cv_score", "metric",
            "competition", "params", "notes", "source"]
_TS_COLS = {"recorded_at"}
_ensured = False


def _table(dataset: str) -> str:
    return f"{dataset}.{_TABLE_NAME}"


def _ensure(project: str, dataset: str) -> None:
    """テーブルが無ければ作る（1 プロセス内 1 回）。"""
    global _ensured
    if _ensured:
        return
    bq.query(project, f"""
        CREATE TABLE IF NOT EXISTS {_table(dataset)} (
            run_id      STRING,
            recorded_at TIMESTAMP,
            cv_score    FLOAT64,
            metric      STRING,
            competition STRING,
            params      STRING,
            notes       STRING,
            source      STRING
        )
    """)
    _ensured = True


def log_run(run_id: str, cv_score: float, params: dict, notes: str = "") -> None:
    project, dataset = bq.load_gcp()
    if not project:
        print(f"[logger] gcpProject 未設定: BQ 記録を skip  run_id={run_id} cv_score={cv_score:.5f}")
        return
    try:
        _ensure(project, dataset)
        bq.insert_row(project, _table(dataset), _COLUMNS, {
            "run_id": run_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "cv_score": cv_score,
            "metric": METRIC,
            "competition": COMP,
            "params": json.dumps(params, ensure_ascii=False),
            "notes": notes,
            "source": "cv",
        }, _TS_COLS)
        print(f"[logger] BQ {_table(dataset)} <- run_id={run_id}  cv_score={cv_score:.5f}")
    except SystemExit as exc:
        # 記録失敗で学習本体は止めない（costs.py の Discord 失敗握りつぶしと同思想）
        print(f"[logger] WARN: BQ 記録失敗 run_id={run_id}: {exc}")


def show_runs(limit: int = 10) -> None:
    """直近 N 件を表示する。"""
    project, dataset = bq.load_gcp()
    if not project:
        print("[logger] gcpProject 未設定のため表示できない")
        return
    sql = (
        f"SELECT run_id, recorded_at, cv_score, notes FROM {_table(dataset)} "
        f"ORDER BY recorded_at DESC LIMIT {limit}"
    )
    print(bq.query(project, sql, fmt="pretty"))
