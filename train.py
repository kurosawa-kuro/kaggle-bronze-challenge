"""Config-driven experiment runner shared by local and Vertex Custom Jobs."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, "src")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Kaggle experiment")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-uri", default=None, help="Optional gs:// destination for run artifacts")
    parser.add_argument("--smoke", action="store_true", help="Run one quick CV fold")
    parser.add_argument("--dry-run", action="store_true", help="Write dummy artifacts without training")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        run(
            config_path=Path(args.config),
            run_id=args.run_id,
            output_uri=args.output_uri,
            smoke=args.smoke,
            dry_run=args.dry_run,
        )
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    return 0


def run(
    *,
    config_path: Path,
    run_id: str | None = None,
    output_uri: str | None = None,
    smoke: bool = False,
    dry_run: bool = False,
) -> Path:
    config_path = config_path.resolve()
    cfg = _load_yaml(config_path)
    data_cfg = cfg.get("data", cfg)
    model_cfg = cfg.get("model", {"name": "lgbm", "params": {}})
    cv_cfg = cfg.get("cv", {})
    runtime_cfg = cfg.get("runtime", {})

    competition = data_cfg["comp"]
    run_id = run_id or _make_run_id(model_cfg.get("name", "model"))
    output_root = Path(runtime_cfg.get("output_root", "outputs/runs"))
    run_dir = output_root / competition / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_path = run_dir / "log.txt"
    with log_path.open("w", encoding="utf-8") as log_fp, _tee_stdout(log_fp):
        print(f"[train] run_id={run_id}")
        print(f"[train] config={config_path}")
        print(f"[train] output={run_dir}")
        _write_config_snapshot(config_path, run_dir)
        if dry_run:
            _write_dummy_artifacts(run_dir, cfg, run_id, competition)
        else:
            _train_lgbm(
                cfg=cfg,
                config_path=config_path,
                run_dir=run_dir,
                run_id=run_id,
                smoke=smoke,
            )

    if output_uri:
        from utils.artifact_store import GcsPrefix, upload_directory

        uploaded = upload_directory(run_dir, GcsPrefix.parse(output_uri))
        print(f"[train] uploaded {len(uploaded)} artifacts to {output_uri}")
    return run_dir


def _train_lgbm(*, cfg: dict[str, Any], config_path: Path, run_dir: Path, run_id: str, smoke: bool) -> None:
    os.environ["KBC_CONFIG_PATH"] = str(config_path)
    from pipelines.ingest import load_data
    from pipelines.featurize import make_features
    from pipelines.score import make_submission, predict
    from models.lgbm import train_cv
    from pipelines.evaluate import cv_score

    model_cfg = cfg.get("model", {})
    if model_cfg.get("name", "lgbm") != "lgbm":
        raise ValueError("train.py currently supports model.name=lgbm")

    cv_cfg = cfg.get("cv", {})
    runtime_cfg = cfg.get("runtime", {})
    n_folds = int(runtime_cfg.get("smoke_n_folds", 2)) if smoke else int(cv_cfg.get("n_folds", 5))
    max_folds = int(runtime_cfg.get("smoke_max_folds", 1)) if smoke else None
    num_boost_round = int(runtime_cfg.get("smoke_num_boost_round", 20)) if smoke else int(runtime_cfg.get("num_boost_round", 2000))
    early_stopping_rounds = int(runtime_cfg.get("early_stopping_rounds", 50))

    train_df, test_df = load_data()
    X_train, y_train, X_test = make_features(train_df, test_df)
    oof, models = train_cv(
        X_train,
        y_train,
        params=model_cfg.get("params", {}),
        notes=f"{run_id} via train.py",
        n_folds=n_folds,
        seed=int(cv_cfg.get("seed", 42)),
        max_folds=max_folds,
        num_boost_round=num_boost_round,
        early_stopping_rounds=early_stopping_rounds,
        log_run_id=run_id,
    )

    trained_mask = _trained_mask(oof)
    metrics = {
        "run_id": run_id,
        "competition": cfg.get("data", cfg)["comp"],
        "model": model_cfg.get("name", "lgbm"),
        "metric": cfg.get("data", cfg)["metric"],
        "cv_score": cv_score(y_train.loc[trained_mask].to_numpy(), oof[trained_mask]),
        "n_folds_requested": n_folds,
        "n_folds_trained": int(max_folds or n_folds),
        "smoke": smoke,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    _write_oof(run_dir / "oof.parquet", y_train, oof, trained_mask)
    preds = predict(X_test, models)
    _write_predictions(run_dir / "test_pred.parquet", preds)
    _write_feature_importance(run_dir / "feature_importance.csv", models, X_train.columns)
    make_submission(X_test, models, out_path=run_dir / "submission.csv", original_test=test_df)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _make_run_id(model_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{model_name}"


def _write_config_snapshot(config_path: Path, run_dir: Path) -> None:
    shutil.copyfile(config_path, run_dir / "config.yaml")


def _write_dummy_artifacts(run_dir: Path, cfg: dict[str, Any], run_id: str, competition: str) -> None:
    metrics = {
        "run_id": run_id,
        "competition": competition,
        "model": cfg.get("model", {}).get("name", "dummy"),
        "metric": cfg.get("data", cfg).get("metric"),
        "cv_score": None,
        "dry_run": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame({"row_id": [0], "target": [0.0], "trained": [False]}).to_parquet(run_dir / "oof.parquet", index=False)
    pd.DataFrame({"row_id": [0], "prediction": [0.0]}).to_parquet(run_dir / "test_pred.parquet", index=False)
    pd.DataFrame({"feature": [], "importance": []}).to_csv(run_dir / "feature_importance.csv", index=False)
    pd.DataFrame({"id": [0], "target": [0.0]}).to_csv(run_dir / "submission.csv", index=False)
    print("[train] dry-run artifacts written")


def _trained_mask(oof: np.ndarray) -> np.ndarray:
    if oof.ndim == 1:
        return oof != 0
    return oof.sum(axis=1) != 0


def _write_oof(path: Path, y_train: pd.Series, oof: np.ndarray, trained_mask: np.ndarray) -> None:
    if oof.ndim == 1:
        df = pd.DataFrame({"row_id": y_train.index, "target": y_train.to_numpy(), "prediction": oof, "trained": trained_mask})
    else:
        df = pd.DataFrame(oof, columns=[f"pred_{i}" for i in range(oof.shape[1])])
        df.insert(0, "target", y_train.to_numpy())
        df.insert(0, "row_id", y_train.index)
        df["trained"] = trained_mask
    df.to_parquet(path, index=False)


def _write_predictions(path: Path, preds: np.ndarray) -> None:
    if preds.ndim == 1:
        df = pd.DataFrame({"row_id": range(len(preds)), "prediction": preds})
    else:
        df = pd.DataFrame(preds, columns=[f"pred_{i}" for i in range(preds.shape[1])])
        df.insert(0, "row_id", range(len(preds)))
    df.to_parquet(path, index=False)


def _write_feature_importance(path: Path, models: list[Any], feature_names: pd.Index) -> None:
    importances = []
    for model in models:
        if hasattr(model, "feature_importance"):
            importances.append(model.feature_importance())
    if importances:
        values = np.mean(importances, axis=0)
        df = pd.DataFrame({"feature": feature_names, "importance": values}).sort_values("importance", ascending=False)
    else:
        df = pd.DataFrame({"feature": feature_names, "importance": 0.0})
    df.to_csv(path, index=False)


class _Tee:
    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


@contextlib.contextmanager
def _tee_stdout(log_fp: Any):
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = _Tee(old_stdout, log_fp)
    sys.stderr = _Tee(old_stderr, log_fp)
    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


if __name__ == "__main__":
    raise SystemExit(main())
