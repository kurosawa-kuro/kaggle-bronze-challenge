"""Deploy / teardown a servable model on a Vertex AI Endpoint（オンライン推論）。

ADR 0002 item 5。`make register-servable`（`infra/Dockerfile.serving` 付き登録）したモデルを
Endpoint にデプロイする。推論器は Batch と同じ `src/serving/predictor.py`。

⚠️ 常駐コスト: Endpoint にデプロイされたモデルは 24/7 課金される（ADR 0002 で「邪魔なら
最初に削る」側、`feedback_gcp_cost_policy`）。**使うときだけ deploy し、終わったら必ず
`teardown` で undeploy + Endpoint 削除すること**。本モジュールは自動デプロイしない設計
（CLI で明示実行 + dry-run 既定なし、teardown を用意）。Kaggle ブロンズでは基本不要。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def deploy(
    *,
    config_path: str,
    project_config: str = "env/project.yaml",
    project: str | None = None,
    region: str | None = None,
    model: str | None = None,
    machine_type: str | None = None,
    min_replica: int = 1,
    max_replica: int = 1,
    dry_run: bool = False,
) -> str | dict:
    """servable モデルを Endpoint にデプロイする（⚠️常駐コスト）。dry_run 時は plan を返す。"""
    project, region, competition = _resolve(config_path, project_config, project, region)
    model_ref = model or f"kaggle-{competition}"
    endpoint_display = f"kaggle-{competition}-endpoint"
    machine_type = machine_type or "n1-standard-2"

    plan = {
        "project": project, "region": region,
        "endpoint_display_name": endpoint_display,
        "model": model_ref,
        "machine_type": machine_type,
        "min_replica": min_replica, "max_replica": max_replica,
        "warning": "Endpoint デプロイは 24/7 常駐コスト。終わったら make endpoint-teardown",
    }
    if dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return plan

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    model_obj = _resolve_model(aiplatform, model_ref)
    endpoints = aiplatform.Endpoint.list(filter=f'display_name="{endpoint_display}"')
    endpoint = endpoints[0] if endpoints else aiplatform.Endpoint.create(display_name=endpoint_display)
    model_obj.deploy(
        endpoint=endpoint,
        deployed_model_display_name=f"{model_ref}-deployed",
        machine_type=machine_type,
        min_replica_count=min_replica,
        max_replica_count=max_replica,
        traffic_percentage=100,
        sync=True,
    )
    print(f"[deploy] {model_ref} -> {endpoint.resource_name}  (⚠️常駐コスト: 不要になったら teardown)")
    return endpoint.resource_name


def teardown(
    *,
    config_path: str,
    project_config: str = "env/project.yaml",
    project: str | None = None,
    region: str | None = None,
    dry_run: bool = False,
) -> str | dict:
    """Endpoint の全デプロイを undeploy し Endpoint を削除する（常駐コスト停止）。"""
    project, region, competition = _resolve(config_path, project_config, project, region)
    endpoint_display = f"kaggle-{competition}-endpoint"
    if dry_run:
        print(json.dumps({"action": "teardown", "endpoint_display_name": endpoint_display,
                          "project": project, "region": region}, indent=2, ensure_ascii=False))
        return {"endpoint_display_name": endpoint_display}

    from google.cloud import aiplatform

    aiplatform.init(project=project, location=region)
    endpoints = aiplatform.Endpoint.list(filter=f'display_name="{endpoint_display}"')
    if not endpoints:
        print(f"[deploy] teardown 対象なし（{endpoint_display}）")
        return endpoint_display
    for ep in endpoints:
        ep.undeploy_all()
        ep.delete(force=True)
        print(f"[deploy] torn down {ep.resource_name}")
    return endpoint_display


def _resolve(config_path, project_config, project, region):
    project_cfg = _load_yaml(Path(project_config))
    train_cfg = _load_yaml(Path(config_path))
    data_cfg = train_cfg.get("data", train_cfg)
    gcp_cfg = project_cfg.get("gcp", {})
    project = project or project_cfg.get("gcpProject") or gcp_cfg.get("project")
    region = region or project_cfg.get("gcpRegion") or gcp_cfg.get("region", "us-central1")
    if not project:
        raise SystemExit("[deploy] gcpProject が無い")
    return project, region, data_cfg["comp"]


def _resolve_model(aiplatform, model_ref: str):
    if model_ref.startswith("projects/"):
        return aiplatform.Model(model_ref)
    models = aiplatform.Model.list(filter=f'display_name="{model_ref}"')
    if not models:
        raise SystemExit(f"[deploy] model display_name={model_ref} が Registry に無い（make register-servable 済み?）")
    return models[0]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy / teardown a Vertex Endpoint（⚠️常駐コスト）")
    parser.add_argument("command", choices=["deploy", "teardown"])
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--model", default=None, help="display_name か model resource。既定 kaggle-<comp>")
    parser.add_argument("--machine-type", default=None)
    parser.add_argument("--min-replica", type=int, default=1)
    parser.add_argument("--max-replica", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "deploy":
        deploy(config_path=args.config, project_config=args.project_config,
               project=args.project, region=args.region, model=args.model,
               machine_type=args.machine_type, min_replica=args.min_replica,
               max_replica=args.max_replica, dry_run=args.dry_run)
    else:
        teardown(config_path=args.config, project_config=args.project_config,
                 project=args.project, region=args.region, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
