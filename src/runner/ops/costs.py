"""GCP cost-estimate logger -> BigQuery (kaggle_ops.cost_estimates).

汎用のコスト概算レコーダ。リソース1利用＝1行。いまは Vertex Custom Job を実装。
GCS / BigQuery / GCE を足すときは PRICES に単価を追加し、`record_<service>()` を
書いて `_insert_row()` を呼ぶだけ（テーブルは共通）。

価格はすべて us-central1 の list-price 概算（USD）。真値は Cloud Billing
（後で Billing Export -> BigQuery）。本ロガーの行は source='estimate'。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

from utils.bq import clean_env as _clean_env
from utils.bq import insert_row as _bq_insert_row
from utils.bq import query as _bq_query

TABLE = "kaggle_ops.cost_estimates"

# --- price tables (approx, us-central1, USD/hour) ---
VERTEX_HOURLY_USD = {
    "n1-standard-4": 0.1900,
    "n1-highmem-16": 0.9344,
    "n2-standard-16": 0.7769,
    "c2-standard-16": 0.8352,
    "c2-standard-30": 1.5660,
}
SPOT_FACTOR = 0.30  # Spot はおおむね on-demand の ~30%（概算）

COLUMNS = [
    "recorded_at", "service", "resource_type", "resource_id", "detail", "region",
    "usage_qty", "usage_unit", "unit_price_usd", "est_usd", "jpy_per_usd", "est_jpy",
    "start_time", "end_time", "labels", "run_id", "competition", "source",
]
TS_COLS = {"recorded_at", "start_time", "end_time"}


def _vertex_hourly_usd(machine_type: str, spot: bool) -> float | None:
    base = VERTEX_HOURLY_USD.get(machine_type)
    if base is None:
        return None
    return round(base * SPOT_FACTOR, 6) if spot else base


def _insert_row(project: str, row: dict) -> None:
    _bq_insert_row(project, TABLE, COLUMNS, row, TS_COLS)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def record_vertex(*, project: str, region: str, competition: str, run_id: str,
                  jpy_per_usd: float, source: str = "estimate") -> None:
    display_name = f"kaggle-{competition}-{run_id}"
    res = subprocess.run(
        ["gcloud", "ai", "custom-jobs", "list", f"--region={region}",
         f"--project={project}", f"--filter=displayName={display_name}", "--format=json"],
        capture_output=True, text=True, env=_clean_env(),
    )
    jobs = json.loads(res.stdout or "[]")
    if not jobs:
        raise SystemExit(f"[cost] no Vertex job for displayName={display_name}")
    job = sorted(jobs, key=lambda j: j.get("createTime", ""))[-1]
    spec = job["jobSpec"]["workerPoolSpecs"][0]
    machine = spec["machineSpec"]["machineType"]
    spot = (job["jobSpec"].get("scheduling", {}) or {}).get("strategy") == "SPOT"
    start, end = job.get("startTime"), job.get("endTime")
    if not (start and end):
        raise SystemExit(f"[cost] job {display_name} has no start/end (まだ完了していない?)")
    duration_s = (_parse_ts(end) - _parse_ts(start)).total_seconds()
    hourly = _vertex_hourly_usd(machine, spot)
    if hourly is None:
        print(f"[cost] WARN: 未知のマシン単価 {machine}（usage のみ記録、est は NULL）")
    est_usd = round(hourly * duration_s / 3600, 6) if hourly is not None else None
    est_jpy = round(est_usd * jpy_per_usd, 2) if est_usd is not None else None
    row = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "service": "aiplatform", "resource_type": "custom_job",
        "resource_id": job["name"].split("/")[-1],
        "detail": machine + (" (spot)" if spot else ""),
        "region": region, "usage_qty": round(duration_s / 3600, 6), "usage_unit": "hour",
        "unit_price_usd": hourly, "est_usd": est_usd,
        "jpy_per_usd": jpy_per_usd, "est_jpy": est_jpy,
        "start_time": start, "end_time": end,
        "labels": f"purpose=kaggle-bronze,run_id={run_id},comp={competition}",
        "run_id": run_id, "competition": competition, "source": source,
    }
    _insert_row(project, row)
    print(f"[cost] recorded {display_name}: {machine}{' spot' if spot else ''} "
          f"{duration_s:.0f}s ≈ ${est_usd} (¥{est_jpy})")
    # 当月累計が watch/alert ゾーン（¥1000 以上）に入っていれば Discord 通知
    this_month, current, _ = _month_summary(project)
    if current >= 1000:
        _discord_post("💰 kaggle-bronze GCP概算（当月, ジョブ記録時）: " + _zone_line(this_month, current))


def _webhook_url() -> str | None:
    env = os.environ.get("DISCORD_WEBHOOK_URL")
    if env:
        return env
    return _load_yaml(Path("env/secret.yaml")).get("discordWebhookUrl")


def _discord_post(message: str) -> bool:
    url = _webhook_url()
    if not url:
        print("[cost] Discord webhook 未設定（env/secret.yaml discordWebhookUrl / env DISCORD_WEBHOOK_URL）")
        return False
    req = urllib.request.Request(
        url, data=json.dumps({"content": message}).encode("utf-8"),
        # Discord の Cloudflare は既定の Python-urllib UA を 403 で弾くため明示する
        headers={"Content-Type": "application/json", "User-Agent": "kaggle-bronze-cost/1.0"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001 - 通知失敗で本処理は止めない
        print(f"[cost] Discord post failed: {exc}")
        return False


def _month_summary(project: str) -> tuple[str, float, list[dict]]:
    sql = (
        "SELECT FORMAT_TIMESTAMP('%Y-%m', COALESCE(start_time, recorded_at)) AS month, "
        "ROUND(SUM(est_jpy), 1) AS jpy, COUNT(*) AS n "
        f"FROM {TABLE} GROUP BY month ORDER BY month DESC LIMIT 6"
    )
    rows = json.loads(_bq_query(project, sql, fmt="json") or "[]")
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    current = next((float(r["jpy"] or 0) for r in rows if r["month"] == this_month), 0.0)
    return this_month, current, rows


def _zone_line(this_month: str, current: float) -> str:
    if current >= 5000:
        return f"[ALERT] {this_month} 概算 ¥{current:.0f} ≥ ¥5000: 事前相談ライン"
    if current >= 1000:
        return f"[WATCH] {this_month} 概算 ¥{current:.0f}（¥5000まで承認済・累計注視）"
    return f"[OK] {this_month} 概算 ¥{current:.0f}（<¥1000・増強自由）"


def report(*, project: str) -> None:
    this_month, current, rows = _month_summary(project)
    print("=== GCP cost estimate (source=estimate, 概算) ===")
    if not rows:
        print("(まだ記録なし)")
    for r in rows:
        mark = " <- 当月" if r["month"] == this_month else ""
        print(f"  {r['month']}: ¥{r['jpy'] or 0}  ({r['n']} jobs){mark}")
    print(f"--- 当月 {this_month}: ¥{current:.0f} / watch ¥1000 / 相談 ¥5000 ---")
    print("  " + _zone_line(this_month, current))


def notify(*, project: str) -> None:
    this_month, current, _ = _month_summary(project)
    ok = _discord_post("💰 kaggle-bronze GCP概算（当月）: " + _zone_line(this_month, current))
    print(f"[cost] Discord 通知{'成功' if ok else '失敗/未送信'}")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GCP cost-estimate logger (BigQuery)")
    parser.add_argument("command", choices=["record", "report", "notify"])
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    pcfg = _load_yaml(Path(args.project_config))
    gcp = pcfg.get("gcp", {})
    project = pcfg.get("gcpProject") or gcp.get("project")
    region = pcfg.get("gcpRegion") or gcp.get("region", "us-central1")
    jpy = float(pcfg.get("jpyPerUsd", 150))
    if not project:
        raise SystemExit("[cost] gcpProject が env/project.yaml に無い")

    if args.command == "report":
        report(project=project)
        return 0

    if args.command == "notify":
        notify(project=project)
        return 0

    if not args.run_id:
        raise SystemExit("[cost] record には --run-id が必要")
    tcfg = _load_yaml(Path(args.config))
    competition = tcfg.get("data", tcfg).get("comp")
    if not competition:
        raise SystemExit(f"[cost] comp が {args.config} に無い")
    record_vertex(project=project, region=region, competition=competition,
                  run_id=args.run_id, jpy_per_usd=jpy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
