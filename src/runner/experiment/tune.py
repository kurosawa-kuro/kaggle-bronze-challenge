"""Optuna hyperparameter tuning for LightGBM (single-machine, e.g. one big Vertex VM).

CV を目的関数に Optuna で best params を探索し、run_id 成果物に best_params.json /
best_config.yaml / trials.csv を残す。--final で best params の最終学習（seed 平均）まで実行。

並列 trial の分散は Phase2（Vertex Hyperparameter Tuning / Vizier）に委ねる。ここは
1 マシン上での探索（ローカル i7 より大きい Vertex マシンで回すと速い）。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _direction(metric: str) -> str:
    return "maximize" if metric == "auc" else "minimize"


def _search_space(trial) -> dict[str, Any]:
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 31, 512),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "lambda_l1": trial.suggest_float("lambda_l1", 1e-8, 10.0, log=True),
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-8, 10.0, log=True),
    }


def run(*, config_path: Path, run_id: str, n_trials: int, smoke: bool, final: bool) -> Path:
    config_path = config_path.resolve()
    cfg = _load_yaml(config_path)
    cv_cfg = cfg.get("cv", {})
    runtime_cfg = cfg.get("runtime", {})
    competition = cfg.get("data", cfg)["comp"]
    metric = cfg.get("data", cfg)["metric"]

    output_root = Path(runtime_cfg.get("output_root", "outputs/runs"))
    run_dir = output_root / competition / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # config.py / models が OBJECTIVE/METRIC を読めるよう、import 前に設定パスを渡す
    os.environ["KBC_CONFIG_PATH"] = str(config_path)
    import optuna
    from models.lgbm import train_cv
    from pipelines.evaluate import cv_score
    from pipelines.featurize import make_features
    from pipelines.ingest import load_data

    n_folds = int(runtime_cfg.get("smoke_n_folds", 2)) if smoke else int(cv_cfg.get("n_folds", 5))
    max_folds = int(runtime_cfg.get("smoke_max_folds", 1)) if smoke else None
    num_boost_round = (
        int(runtime_cfg.get("smoke_num_boost_round", 20)) if smoke
        else int(runtime_cfg.get("tune_num_boost_round", runtime_cfg.get("num_boost_round", 2000)))
    )
    early_stopping_rounds = int(runtime_cfg.get("early_stopping_rounds", 50))
    seed = int(cv_cfg.get("seed", 42))

    train_df, test_df = load_data()
    X_train, y_train, _ = make_features(train_df, test_df)

    def objective(trial) -> float:
        params = {**cfg.get("model", {}).get("params", {}), **_search_space(trial)}
        oof, _ = train_cv(
            X_train, y_train, params=params, notes=f"{run_id} tune trial {trial.number}",
            n_folds=n_folds, seed=seed, max_folds=max_folds,
            num_boost_round=num_boost_round, early_stopping_rounds=early_stopping_rounds,
            log_run_id=f"{run_id}_t{trial.number}",
        )
        mask = oof.sum(axis=1) != 0 if oof.ndim > 1 else oof != 0
        return cv_score(y_train.loc[mask].to_numpy(), oof[mask])

    study = optuna.create_study(direction=_direction(metric))
    study.optimize(objective, n_trials=n_trials)

    best_params = {**cfg.get("model", {}).get("params", {}), **study.best_params}
    (run_dir / "best_params.json").write_text(
        json.dumps({"best_value": study.best_value, "metric": metric, "n_trials": n_trials,
                    "best_params": best_params}, indent=2, ensure_ascii=False), encoding="utf-8")
    study.trials_dataframe().to_csv(run_dir / "trials.csv", index=False)

    # base config に best params を上書きした最終 config を書き出す（再現・最終学習用）
    best_cfg = {**cfg, "model": {**cfg.get("model", {}), "params": best_params}}
    best_config_path = run_dir / "best_config.yaml"
    best_config_path.write_text(yaml.safe_dump(best_cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"[tune] best {metric}={study.best_value:.5f}  -> {run_dir}/best_params.json")

    if final:
        from runner.experiment.train import run as train_run
        train_run(config_path=best_config_path, run_id=f"{run_id}_final", smoke=smoke)
        print(f"[tune] final seed-averaged run: {run_id}_final")
    else:
        print(f"[tune] 最終学習: make train-local CONFIG={best_config_path} RUN_ID={run_id}_final")
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optuna tuning for LightGBM")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--n-trials", type=int, default=30)
    parser.add_argument("--smoke", action="store_true", help="few folds/rounds for a quick check")
    parser.add_argument("--final", action="store_true", help="run best-params seed-averaged training after search")
    args = parser.parse_args(argv)
    run(config_path=Path(args.config), run_id=args.run_id, n_trials=args.n_trials,
        smoke=args.smoke, final=args.final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
