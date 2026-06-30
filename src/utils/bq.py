"""BigQuery 共通ユーティリティ（`bq` CLI 経由。Python client lib を足さない）。

tabular メタデータの正本を BigQuery に統一する方針（ADR 0002）に伴い、
costs.py / logger.py が共有する最小ヘルパ。新しい infra lib は導入しない。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml


def clean_env() -> dict:
    """外部 Python CLI (bq/gcloud) は PYTHONPATH=src を渡すと自前 utils が
    こちらの src/utils で shadow されて壊れるため、PYTHONPATH を除いた env を渡す。"""
    return {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


def load_gcp(path: str | Path = "env/project.yaml") -> tuple[str | None, str]:
    """(gcpProject, bqDataset) を返す。project 未設定なら (None, dataset)。"""
    p = Path(path)
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    gcp = cfg.get("gcp", {})
    project = cfg.get("gcpProject") or gcp.get("project")
    dataset = cfg.get("bqDataset", "kaggle_ops")
    return project, dataset


def query(project: str, sql: str, fmt: str | None = None) -> str:
    cmd = ["bq", f"--project_id={project}", "query", "--use_legacy_sql=false", "--quiet"]
    if fmt:
        cmd.append(f"--format={fmt}")
    cmd.append(sql)
    res = subprocess.run(cmd, capture_output=True, text=True, env=clean_env())
    if res.returncode != 0:
        raise SystemExit(f"[bq] error: {res.stderr.strip()}")
    return res.stdout


def lit(value, ts: bool = False) -> str:
    if value is None:
        return "NULL"
    if ts:
        return f"TIMESTAMP('{value}')"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_row(project: str, table: str, columns: list[str], row: dict,
               ts_cols: set[str] | None = None) -> None:
    ts_cols = ts_cols or set()
    vals = ", ".join(lit(row.get(c), ts=(c in ts_cols)) for c in columns)
    query(project, f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({vals})")
