"""Compile + submit a Vertex AI Pipeline (KFP v2): train -> register.

ADR 0002 item 3。既存の学習イメージをそのままコンテナコンポーネントとして使い、
`runner.experiment.train` → `runner.model.register` を 1 つの DAG（Vertex Pipelines）にする。

altitude（粗さの方針）:
- ingest / featurize / train / score は `train.py` 内で完結しているため、本パイプラインは
  「学習 → モデル登録」の粗い DAG に留める。コンポーネント間で featurized データを GCS 経由で
  受け渡す細分化は、ブロンズ規模では GCS 往復が増えるだけなので採用しない。
- serving / Endpoint は未配線。

config は base64 でパイプラインパラメータとして渡す（イメージにベイクしない）。

注: KFP の container_component は注釈の実型を解釈するため、このモジュールでは
`from __future__ import annotations`（注釈の文字列化）を使わない。
"""
import argparse
import base64
import json
import re
import tempfile
from pathlib import Path

import yaml


def build_and_run(
    *,
    config_path: str,
    run_id: str,
    project_config: str = "env/project.yaml",
    project: str | None = None,
    region: str | None = None,
    bucket: str | None = None,
    image_uri: str | None = None,
    input_uri: str | None = None,
    dry_run: bool = False,
) -> str | dict:
    """train→register の Vertex Pipeline をコンパイルし、非ブロッキング投入する。
    dry_run 時はコンパイルのみ行い plan dict を返す（API 非呼び出し）。"""
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
        raise SystemExit(f"[pipeline] missing required settings: {', '.join(missing)}")

    output_uri = f"gs://{bucket}/runs/{competition}/{run_id}"
    input_uri = input_uri or f"gs://{bucket}/data/{competition}/raw"
    config_b64 = base64.b64encode(Path(config_path).read_bytes()).decode("ascii")
    pipeline_root = f"gs://{bucket}/pipeline_root"

    from kfp import compiler, dsl

    image = image_uri  # container_component に焼き込む

    @dsl.container_component
    def train_op(config_b64: str, run_id: str, output_uri: str, input_uri: str):
        return dsl.ContainerSpec(
            image=image,
            command=["python", "-m", "runner.experiment.train"],
            args=["--config-b64", config_b64, "--run-id", run_id,
                  "--output-uri", output_uri, "--input-uri", input_uri],
        )

    @dsl.container_component
    def register_op(config_b64: str, run_id: str):
        return dsl.ContainerSpec(
            image=image,
            command=["python", "-m", "runner.model.register"],
            args=["--config-b64", config_b64, "--run-id", run_id],
        )

    @dsl.pipeline(name="kaggle-train-register", pipeline_root=pipeline_root)
    def _pipeline(config_b64: str, run_id: str, output_uri: str, input_uri: str):
        train = train_op(config_b64=config_b64, run_id=run_id,
                         output_uri=output_uri, input_uri=input_uri)
        register_op(config_b64=config_b64, run_id=run_id).after(train)

    template = Path(tempfile.gettempdir()) / f"kaggle_pipeline_{_label_value(run_id)}.json"
    compiler.Compiler().compile(pipeline_func=_pipeline, package_path=str(template))
    print(f"[pipeline] compiled DAG (train -> register) -> {template}")

    parameter_values = {
        "config_b64": config_b64, "run_id": run_id,
        "output_uri": output_uri, "input_uri": input_uri,
    }
    labels = {
        "purpose": "kaggle-bronze",
        "comp": _label_value(competition),
        "run_id": _label_value(run_id),
    }
    plan = {
        "project": project, "region": region,
        "display_name": f"kaggle-{competition}-{run_id}",
        "pipeline_root": pipeline_root,
        "image": image,
        "template_path": str(template),
        "parameter_values": {**parameter_values, "config_b64": "<base64 omitted>"},
        "labels": labels,
    }
    if dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return plan

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region, staging_bucket=f"gs://{bucket}")
    job = aiplatform.PipelineJob(
        display_name=f"kaggle-{competition}-{run_id}",
        template_path=str(template),
        pipeline_root=pipeline_root,
        parameter_values=parameter_values,
        enable_caching=False,
        labels=labels,
    )
    job.submit()  # 非ブロッキング投入
    print(f"[pipeline] submitted {job.resource_name}")
    return job.resource_name


def _label_value(value: str) -> str:
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
    parser = argparse.ArgumentParser(description="Compile + submit a Vertex Pipeline (train -> register)")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--image-uri", default=None)
    parser.add_argument("--input-uri", default=None)
    parser.add_argument("--dry-run", action="store_true", help="compile のみ。投入しない")
    args = parser.parse_args(argv)

    build_and_run(
        config_path=args.config,
        run_id=args.run_id,
        project_config=args.project_config,
        project=args.project,
        region=args.region,
        bucket=args.bucket,
        image_uri=args.image_uri,
        input_uri=args.input_uri,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
