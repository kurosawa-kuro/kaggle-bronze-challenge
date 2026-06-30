"""Submit train.py to Vertex AI Custom Job."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a Vertex AI Custom Job")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--image-uri", default=None)
    parser.add_argument("--input-uri", default=None, help="gs:// source for raw data (default: gs://<bucket>/data/<comp>/raw)")
    parser.add_argument("--machine-type", default=None)
    parser.add_argument("--service-account", default=None)
    parser.add_argument("--timeout-hours", type=float, default=8.0)
    parser.add_argument("--smoke", action="store_true", help="Pass --smoke to train.py (one quick fold)")
    parser.add_argument("--spot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync", action="store_true", help="Wait for the job to finish")
    return parser.parse_args(argv)


def submit_from_config(
    *,
    config_path: str,
    run_id: str,
    project_config: str = "env/project.yaml",
    project: str | None = None,
    region: str | None = None,
    bucket: str | None = None,
    image_uri: str | None = None,
    input_uri: str | None = None,
    machine_type: str | None = None,
    service_account: str | None = None,
    timeout_hours: float = 8.0,
    smoke: bool = False,
    spot: bool = False,
    sync: bool = False,
    dry_run: bool = False,
) -> str | dict:
    """Build + submit one Custom Job. Non-blocking (.submit()) unless sync=True.
    Returns the job resource name (or the plan dict when dry_run)."""
    project_cfg = _load_yaml(Path(project_config))
    train_cfg = _load_yaml(Path(config_path))
    data_cfg = train_cfg.get("data", train_cfg)

    gcp_cfg = project_cfg.get("gcp", {})
    project = project or project_cfg.get("gcpProject") or gcp_cfg.get("project")
    region = region or project_cfg.get("gcpRegion") or gcp_cfg.get("region", "us-central1")
    bucket = bucket or project_cfg.get("gcsBucket")
    image_uri = image_uri or project_cfg.get("imageUri")
    machine_type = machine_type or project_cfg.get("vertexMachineType", "n1-standard-4")
    service_account = service_account or project_cfg.get("vertexServiceAccount")
    competition = data_cfg["comp"]
    if not image_uri and project:
        image_uri = _image_uri(project_cfg, project=project, region=region)

    missing = [name for name, value in {
        "project": project,
        "bucket": bucket,
        "image_uri": image_uri,
    }.items() if not value]
    if missing:
        raise SystemExit(f"[vertex] missing required settings: {', '.join(missing)}")

    output_uri = f"gs://{bucket}/runs/{competition}/{run_id}"
    input_uri = input_uri or f"gs://{bucket}/data/{competition}/raw"
    # config はイメージにベイクせず base64 で渡す（新 config でも再ビルド不要）
    import base64
    config_b64 = base64.b64encode(Path(config_path).read_bytes()).decode("ascii")
    container_args = [
        "--config-b64", config_b64,
        "--run-id", run_id,
        "--output-uri", output_uri,
        "--input-uri", input_uri,
    ]
    if smoke:
        container_args.append("--smoke")
    worker_pool_specs = [{
        "machine_spec": {"machine_type": machine_type},
        "replica_count": 1,
        "container_spec": {
            "image_uri": image_uri,
            "command": ["python", "-m", "runner.experiment.train"],
            "args": container_args,
        },
    }]
    labels = {
        "purpose": "kaggle-bronze",
        "comp": _label_value(competition),
        "run_id": _label_value(run_id),
    }
    plan = {
        "project": project,
        "region": region,
        "display_name": f"kaggle-{competition}-{run_id}",
        "worker_pool_specs": worker_pool_specs,
        "staging_bucket": f"gs://{bucket}",
        "service_account": service_account,
        "scheduling_strategy": "SPOT" if spot else None,
        "labels": labels,
        "sync": sync,
    }
    if dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return plan

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region, staging_bucket=f"gs://{bucket}")
    job = aiplatform.CustomJob(
        display_name=plan["display_name"],
        worker_pool_specs=worker_pool_specs,
        labels=labels,
    )
    kwargs = {"service_account": service_account, "timeout": int(timeout_hours * 3600)}
    if spot:
        kwargs["scheduling_strategy"] = "SPOT"
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    if sync:
        job.run(sync=True, **kwargs)
    else:
        job.submit(**kwargs)  # 非ブロッキング: 作成して即返る（fan-out 可能）
    print(f"[vertex] submitted {job.resource_name}  -> {output_uri}")
    return job.resource_name


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    submit_from_config(
        config_path=args.config,
        run_id=args.run_id,
        project_config=args.project_config,
        project=args.project,
        region=args.region,
        bucket=args.bucket,
        image_uri=args.image_uri,
        input_uri=args.input_uri,
        machine_type=args.machine_type,
        service_account=args.service_account,
        timeout_hours=args.timeout_hours,
        smoke=args.smoke,
        spot=args.spot,
        sync=args.sync,
        dry_run=args.dry_run,
    )
    return 0


def _label_value(value: str) -> str:
    """GCP label values: lowercase letters, digits, '-', '_'; max 63 chars."""
    import re

    return re.sub(r"[^a-z0-9_-]", "-", value.lower())[:63]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _image_uri(project_cfg: dict, *, project: str, region: str) -> str:
    repo = project_cfg.get("artifactRegistryRepo", "kaggle")
    image_name = project_cfg.get("imageName", "kaggle-bronze-challenge")
    image_tag = project_cfg.get("imageTag", "latest")
    return f"{region}-docker.pkg.dev/{project}/{repo}/{image_name}:{image_tag}"


if __name__ == "__main__":
    raise SystemExit(main())
