"""Register a trained run's model into Vertex AI Model Registry.

学習成果物 `gs://<bucket>/runs/<comp>/<run_id>/model` を 1 バージョンとして登録する。
同じ `display_name`（`kaggle-<comp>`）に積み重ね、version で履歴を持つ。`latest` alias は
常に最新版へ移る。

目的は **版管理 / lineage**。serving（Endpoint）は現状未配線で、ADR 0002 でも「邪魔なら削る」側。
`serving_container_image_uri` は upload に必須なので学習イメージをプレースホルダとして渡す
（deploy 時にしか実体は要求されない）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import yaml

from utils.bq import clean_env


def register_from_run(
    *,
    config_path: str,
    run_id: str,
    project_config: str = "conf/project.yaml",
    project: str | None = None,
    region: str | None = None,
    bucket: str | None = None,
    image_uri: str | None = None,
    artifact_uri: str | None = None,
    aliases: list[str] | None = None,
    dry_run: bool = False,
) -> str | dict:
    """run_id のモデルを Vertex Model Registry に 1 バージョン登録する。
    既存 display_name があれば parent にして版を積む。dry_run 時は plan dict を返す。"""
    project_cfg = _load_yaml(Path(project_config))
    train_cfg = _load_yaml(Path(config_path))
    data_cfg = train_cfg.get("data", train_cfg)

    gcp_cfg = project_cfg.get("gcp", {})
    project = project or project_cfg.get("gcpProject") or gcp_cfg.get("project")
    region = region or project_cfg.get("gcpRegion") or gcp_cfg.get("region", "us-central1")
    bucket = bucket or project_cfg.get("gcsBucket")
    image_uri = image_uri or project_cfg.get("imageUri")
    competition = data_cfg["comp"]
    if not image_uri and project:
        image_uri = _image_uri(project_cfg, project=project, region=region)

    missing = [name for name, value in {
        "project": project, "bucket": bucket, "image_uri": image_uri,
    }.items() if not value]
    if missing:
        raise SystemExit(f"[register] missing required settings: {', '.join(missing)}")

    artifact_uri = artifact_uri or f"gs://{bucket}/runs/{competition}/{run_id}/model"
    cv_score = _read_cv_score(competition, run_id, bucket, project_cfg.get("output_root", "outputs/runs"))
    display_name = f"kaggle-{competition}"
    aliases = aliases or ["latest"]
    labels = {
        "purpose": "kaggle-bronze",
        "comp": _label_value(competition),
        "run_id": _label_value(run_id),
    }
    version_description = f"run_id={run_id}" + (f" cv_score={cv_score}" if cv_score is not None else "")

    plan = {
        "project": project,
        "region": region,
        "display_name": display_name,
        "artifact_uri": artifact_uri,
        "serving_container_image_uri": image_uri,
        "version_aliases": aliases,
        "version_description": version_description,
        "labels": labels,
        "note": "serving 未配線。registry は版管理/lineage 目的（ADR 0002）",
    }
    if dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return plan

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    parent = _find_parent(aiplatform, display_name)
    model = aiplatform.Model.upload(
        display_name=display_name,
        artifact_uri=artifact_uri,
        serving_container_image_uri=image_uri,
        version_aliases=aliases,
        version_description=version_description,
        labels=labels,
        parent_model=parent,        # None なら新規モデル、あれば新バージョン
        is_default_version=True,
    )
    kind = "new version of" if parent else "new model"
    print(f"[register] {kind} {model.resource_name}  version={model.version_id}  aliases={aliases}")
    return model.resource_name


def _find_parent(aiplatform, display_name: str) -> str | None:
    models = aiplatform.Model.list(filter=f'display_name="{display_name}"')
    return models[0].resource_name if models else None


def _read_cv_score(competition: str, run_id: str, bucket: str, output_root: str) -> float | None:
    """metrics.json の cv_score を local 優先・無ければ GCS から読む（取れなくても登録は続行）。"""
    local = Path(output_root) / competition / run_id / "metrics.json"
    if local.exists():
        return _cv_from_text(local.read_text(encoding="utf-8"))
    gs = f"gs://{bucket}/runs/{competition}/{run_id}/metrics.json"
    res = subprocess.run(["gsutil", "cat", gs], capture_output=True, text=True, env=clean_env())
    if res.returncode == 0:
        return _cv_from_text(res.stdout)
    print(f"[register] WARN: metrics.json が取得できず cv_score 不明（{gs}）")
    return None


def _cv_from_text(text: str) -> float | None:
    try:
        val = json.loads(text).get("cv_score")
        return float(val) if val is not None else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _label_value(value: str) -> str:
    """GCP label values: lowercase letters, digits, '-', '_'; max 63 chars."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register a run's model into Vertex Model Registry")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-config", default="conf/project.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--image-uri", default=None)
    parser.add_argument("--artifact-uri", default=None,
                        help="既定: gs://<bucket>/runs/<comp>/<run_id>/model")
    parser.add_argument("--alias", action="append", default=None,
                        help="version alias（複数可）。既定 latest")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    register_from_run(
        config_path=args.config,
        run_id=args.run_id,
        project_config=args.project_config,
        project=args.project,
        region=args.region,
        bucket=args.bucket,
        image_uri=args.image_uri,
        artifact_uri=args.artifact_uri,
        aliases=args.alias,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
