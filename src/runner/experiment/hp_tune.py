"""Submit a Vertex AI Hyperparameter Tuning job (Vizier) for the train.py contract.

同一コンテナ(`-m runner.experiment.train`)を trial worker にし、Vizier が探索パラメータを
`--<name>=<value>` で渡す（train.py が parse_known_args で拾い model.params 上書き）。
train.py は `--hp-metric-tag cv_score` で評価値を hypertune 報告する。並列 trial は
parallel_trial_count で制御。Optuna(1マシン) に対し、これは Vizier によるマネージド並列探索。
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from runner.experiment.vertex_run import _image_uri, _label_value, _load_yaml

METRIC_TAG = "cv_score"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a Vertex Hyperparameter Tuning job")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--image-uri", default=None)
    parser.add_argument("--max-trials", type=int, default=20)
    parser.add_argument("--parallel-trials", type=int, default=4)
    parser.add_argument("--machine-type", default=None)
    parser.add_argument("--smoke", action="store_true", help="few folds/rounds per trial")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    pcfg = _load_yaml(Path(args.project_config))
    tcfg = _load_yaml(Path(args.config))
    data_cfg = tcfg.get("data", tcfg)
    competition = data_cfg["comp"]
    metric = data_cfg["metric"]

    gcp = pcfg.get("gcp", {})
    project = pcfg.get("gcpProject") or gcp.get("project")
    region = pcfg.get("gcpRegion") or gcp.get("region", "us-central1")
    bucket = pcfg.get("gcsBucket")
    machine = args.machine_type or pcfg.get("vertexMachineType", "n1-standard-4")
    service_account = pcfg.get("vertexServiceAccount")
    image_uri = args.image_uri or pcfg.get("imageUri")
    if not image_uri and project:
        image_uri = _image_uri(pcfg, project=project, region=region)
    if not (project and bucket and image_uri):
        raise SystemExit("[hpt] missing project / bucket / image_uri")

    config_b64 = base64.b64encode(Path(args.config).read_bytes()).decode("ascii")
    container_args = [
        "--config-b64", config_b64,
        "--run-id", args.run_id,            # trial 間共有（ephemeral、GCS 出力しない）
        "--input-uri", f"gs://{bucket}/data/{competition}/raw",
        "--hp-metric-tag", METRIC_TAG,
    ]
    if args.smoke:
        container_args.append("--smoke")
    worker_pool_specs = [{
        "machine_spec": {"machine_type": machine},
        "replica_count": 1,
        "container_spec": {
            "image_uri": image_uri,
            "command": ["python", "-m", "runner.experiment.train"],
            "args": container_args,
        },
    }]
    goal = "maximize" if metric == "auc" else "minimize"

    plan = {
        "project": project, "region": region,
        "display_name": f"kaggle-{competition}-{args.run_id}-hpt",
        "metric": {METRIC_TAG: goal},
        "max_trial_count": args.max_trials,
        "parallel_trial_count": args.parallel_trials,
        "machine_type": machine,
        "worker_pool_specs": worker_pool_specs,
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    from google.cloud import aiplatform
    from google.cloud.aiplatform import hyperparameter_tuning as hpt

    parameter_spec = {
        "learning_rate": hpt.DoubleParameterSpec(min=0.01, max=0.2, scale="log"),
        "num_leaves": hpt.IntegerParameterSpec(min=31, max=512, scale="linear"),
        "min_child_samples": hpt.IntegerParameterSpec(min=5, max=100, scale="linear"),
        "feature_fraction": hpt.DoubleParameterSpec(min=0.5, max=1.0, scale="linear"),
        "bagging_fraction": hpt.DoubleParameterSpec(min=0.5, max=1.0, scale="linear"),
        "lambda_l1": hpt.DoubleParameterSpec(min=1e-8, max=10.0, scale="log"),
        "lambda_l2": hpt.DoubleParameterSpec(min=1e-8, max=10.0, scale="log"),
    }
    labels = {"purpose": "kaggle-bronze", "comp": _label_value(competition), "run_id": _label_value(args.run_id)}

    aiplatform.init(project=project, location=region, staging_bucket=f"gs://{bucket}")
    custom_job = aiplatform.CustomJob(
        display_name=f"kaggle-{competition}-{args.run_id}-trial",
        worker_pool_specs=worker_pool_specs,
        labels=labels,
    )
    hpt_job = aiplatform.HyperparameterTuningJob(
        display_name=plan["display_name"],
        custom_job=custom_job,
        metric_spec={METRIC_TAG: goal},
        parameter_spec=parameter_spec,
        max_trial_count=args.max_trials,
        parallel_trial_count=args.parallel_trials,
        labels=labels,
    )
    run_kwargs = {"service_account": service_account} if service_account else {}
    hpt_job.run(sync=False, **run_kwargs)  # trial 完了は待たない
    hpt_job.wait_for_resource_creation()   # 作成(RPC)完了だけ待つ→resource_name 確定・プロセス終了で消えない
    print(f"[hpt] submitted {hpt_job.resource_name}")
    print(f"[hpt] {args.max_trials} trials (parallel {args.parallel_trials}) on {machine}, metric {METRIC_TAG} ({goal})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
