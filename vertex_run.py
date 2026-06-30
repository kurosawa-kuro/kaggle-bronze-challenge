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
    parser.add_argument("--project-config", default="conf/project.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--image-uri", default=None)
    parser.add_argument("--machine-type", default=None)
    parser.add_argument("--service-account", default=None)
    parser.add_argument("--timeout-hours", type=float, default=8.0)
    parser.add_argument("--spot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync", action="store_true", help="Wait for the job to finish")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_cfg = _load_yaml(Path(args.project_config))
    train_cfg = _load_yaml(Path(args.config))
    data_cfg = train_cfg.get("data", train_cfg)

    gcp_cfg = project_cfg.get("gcp", {})
    project = args.project or project_cfg.get("gcpProject") or gcp_cfg.get("project")
    region = args.region or project_cfg.get("gcpRegion") or gcp_cfg.get("region", "us-central1")
    bucket = args.bucket or project_cfg.get("gcsBucket")
    image_uri = args.image_uri or project_cfg.get("imageUri")
    machine_type = args.machine_type or project_cfg.get("vertexMachineType", "n1-standard-4")
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

    output_uri = f"gs://{bucket}/runs/{competition}/{args.run_id}"
    container_args = [
        "--config",
        args.config,
        "--run-id",
        args.run_id,
        "--output-uri",
        output_uri,
    ]
    worker_pool_specs = [{
        "machine_spec": {"machine_type": machine_type},
        "replica_count": 1,
        "container_spec": {
            "image_uri": image_uri,
            "command": ["python", "train.py"],
            "args": container_args,
        },
    }]

    plan = {
        "project": project,
        "region": region,
        "display_name": f"kaggle-{competition}-{args.run_id}",
        "worker_pool_specs": worker_pool_specs,
        "staging_bucket": f"gs://{bucket}",
        "service_account": args.service_account or project_cfg.get("vertexServiceAccount"),
        "scheduling_strategy": "SPOT" if args.spot else None,
        "sync": args.sync,
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region, staging_bucket=f"gs://{bucket}")
    job = aiplatform.CustomJob(
        display_name=plan["display_name"],
        worker_pool_specs=worker_pool_specs,
    )
    run_kwargs = {
        "service_account": plan["service_account"],
        "sync": args.sync,
        "timeout": int(args.timeout_hours * 3600),
    }
    if args.spot:
        run_kwargs["scheduling_strategy"] = "SPOT"
    job.run(**{k: v for k, v in run_kwargs.items() if v is not None})
    print(f"[vertex] submitted {job.resource_name}")
    print(f"[vertex] artifacts: {output_uri}")
    return 0


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
