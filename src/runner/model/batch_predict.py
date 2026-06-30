"""Submit a Vertex AI Batch Prediction job from a registered model.

ADR 0002 item 4。`runner.model.register --serving-image ...` で **実推論コンテナ付き**に登録した
モデル（`kaggle-<comp>`）に対し、GCS 上の instances(jsonl) をバッチ推論する。

推論コンテナは `infra/Dockerfile.serving`（`src/serving/predictor.py`、LightGBM seed-bag
平均）。serving 未配線（プレースホルダ）で登録したモデルは Batch Prediction に使えない。
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml


def submit_batch(
    *,
    config_path: str,
    run_id: str | None = None,
    project_config: str = "env/project.yaml",
    project: str | None = None,
    region: str | None = None,
    bucket: str | None = None,
    model: str | None = None,
    gcs_source: str | None = None,
    gcs_destination: str | None = None,
    machine_type: str | None = None,
    instances_format: str = "jsonl",
    predictions_format: str = "jsonl",
    dry_run: bool = False,
) -> str | dict:
    """登録済みモデルで Batch Prediction を非ブロッキング投入する。dry_run 時は plan を返す。"""
    project_cfg = _load_yaml(Path(project_config))
    train_cfg = _load_yaml(Path(config_path))
    data_cfg = train_cfg.get("data", train_cfg)

    gcp_cfg = project_cfg.get("gcp", {})
    project = project or project_cfg.get("gcpProject") or gcp_cfg.get("project")
    region = region or project_cfg.get("gcpRegion") or gcp_cfg.get("region", "us-central1")
    bucket = bucket or project_cfg.get("gcsBucket")
    machine_type = machine_type or project_cfg.get("vertexMachineType", "n1-standard-4")
    competition = data_cfg["comp"]

    if not gcs_source:
        raise SystemExit("[batch] --gcs-source（instances jsonl の gs://...）が必要")
    missing = [name for name, value in {"project": project, "bucket": bucket}.items() if not value]
    if missing:
        raise SystemExit(f"[batch] missing required settings: {', '.join(missing)}")

    job_tag = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    gcs_destination = gcs_destination or f"gs://{bucket}/batch_predict/{competition}/{job_tag}"
    model_ref = model or f"kaggle-{competition}"
    display_name = f"kaggle-{competition}-batch-{_label_value(job_tag)}"
    sources = gcs_source if isinstance(gcs_source, list) else [gcs_source]

    plan = {
        "project": project,
        "region": region,
        "display_name": display_name,
        "model": model_ref,
        "gcs_source": sources,
        "gcs_destination_prefix": gcs_destination,
        "instances_format": instances_format,
        "predictions_format": predictions_format,
        "machine_type": machine_type,
    }
    if dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return plan

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    model_name = model_ref
    if not model_ref.startswith("projects/"):
        models = aiplatform.Model.list(filter=f'display_name="{model_ref}"')
        if not models:
            raise SystemExit(f"[batch] model display_name={model_ref} が Registry に無い")
        model_name = models[0].resource_name

    job = aiplatform.BatchPredictionJob.create(
        job_display_name=display_name,
        model_name=model_name,
        gcs_source=sources,
        gcs_destination_prefix=gcs_destination,
        instances_format=instances_format,
        predictions_format=predictions_format,
        machine_type=machine_type,
        sync=False,  # 非ブロッキング投入
    )
    print(f"[batch] submitted {job.resource_name}  -> {gcs_destination}")
    return job.resource_name


def _label_value(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "-", value.lower())[:63]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a Vertex Batch Prediction job")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", default=None, help="出力先・ジョブ名のタグ。未指定なら時刻")
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--model", default=None, help="Registry の display_name か model resource name。既定 kaggle-<comp>")
    parser.add_argument("--gcs-source", default=None, help="instances jsonl の gs://...（必須）")
    parser.add_argument("--gcs-destination", default=None)
    parser.add_argument("--machine-type", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    submit_batch(
        config_path=args.config,
        run_id=args.run_id,
        project_config=args.project_config,
        project=args.project,
        region=args.region,
        bucket=args.bucket,
        model=args.model,
        gcs_source=args.gcs_source,
        gcs_destination=args.gcs_destination,
        machine_type=args.machine_type,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
