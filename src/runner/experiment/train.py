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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Kaggle experiment")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--config-b64", default=None,
                        help="base64 of the config YAML (Vertex 用: config をイメージにベイクせず引数で渡す)")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-uri", default=None, help="Optional gs:// destination for run artifacts")
    parser.add_argument("--input-uri", default=None, help="Optional gs:// source for raw data (staged into data/<comp>/raw)")
    parser.add_argument("--smoke", action="store_true", help="Run one quick CV fold")
    parser.add_argument("--dry-run", action="store_true", help="Write dummy artifacts without training")
    parser.add_argument("--hp-metric-tag", default=None,
                        help="set to report cv_score to Vertex hypertune under this tag (HP Tuning trials)")
    # Vertex Hyperparameter Tuning は探索パラメータを --<name>=<value> で付与する。
    # 既知フラグ以外をここで拾い model.params 上書きにする。
    args, extras = parser.parse_known_args(argv)
    args.param_overrides = _parse_overrides(extras)
    return args


def _parse_overrides(extras: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    i = 0
    while i < len(extras):
        tok = extras[i]
        if not tok.startswith("--"):
            i += 1
            continue
        key = tok[2:]
        if "=" in key:
            key, val = key.split("=", 1)
            i += 1
        elif i + 1 < len(extras) and not extras[i + 1].startswith("--"):
            val = extras[i + 1]
            i += 2
        else:
            val = "true"
            i += 1
        out[key] = _cast(val)
    return out


def _cast(value: str) -> Any:
    for caster in (int, float):
        try:
            return caster(value)
        except ValueError:
            continue
    return value


def _resolve_config(args: argparse.Namespace) -> Path:
    """--config-b64 が来たら一時ファイルに展開してそのパスを返す（イメージ非依存）。"""
    if args.config_b64:
        import base64
        import tempfile

        content = base64.b64decode(args.config_b64)
        tmp = tempfile.NamedTemporaryFile("wb", suffix=".yaml", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)
    return Path(args.config)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        run(
            config_path=_resolve_config(args),
            run_id=args.run_id,
            output_uri=args.output_uri,
            input_uri=args.input_uri,
            smoke=args.smoke,
            dry_run=args.dry_run,
            param_overrides=args.param_overrides,
            hp_metric_tag=args.hp_metric_tag,
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
    input_uri: str | None = None,
    smoke: bool = False,
    dry_run: bool = False,
    param_overrides: dict[str, Any] | None = None,
    hp_metric_tag: str | None = None,
) -> Path:
    config_path = config_path.resolve()
    cfg = _load_yaml(config_path)
    if param_overrides:
        # Vertex HP Tuning が渡す探索パラメータで model.params を上書き
        model = cfg.setdefault("model", {})
        model["params"] = {**model.get("params", {}), **param_overrides}
        print(f"[train] param overrides: {param_overrides}")
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
        if input_uri and not dry_run:
            from config import DATA_RAW
            from utils.artifact_store import GcsPrefix, download_directory

            staged = download_directory(GcsPrefix.parse(input_uri), DATA_RAW)
            print(f"[train] staged {len(staged)} input files from {input_uri} -> {DATA_RAW}")
        if dry_run:
            _write_dummy_artifacts(run_dir, cfg, run_id, competition)
        else:
            cv = _train_lgbm(
                cfg=cfg,
                config_path=config_path,
                run_dir=run_dir,
                run_id=run_id,
                smoke=smoke,
            )
            if hp_metric_tag:
                _report_hp_metric(hp_metric_tag, cv)

    if output_uri:
        from utils.artifact_store import GcsPrefix, upload_directory

        uploaded = upload_directory(run_dir, GcsPrefix.parse(output_uri))
        print(f"[train] uploaded {len(uploaded)} artifacts to {output_uri}")
    return run_dir


def _train_lgbm(*, cfg: dict[str, Any], config_path: Path, run_dir: Path, run_id: str, smoke: bool) -> float:
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

    default_seed = int(cv_cfg.get("seed", 42))
    seeds = [default_seed] if smoke else [int(s) for s in (cfg.get("seeds") or [default_seed])]

    train_df, test_df = load_data()
    X_train, y_train, X_test = make_features(train_df, test_df)

    # seed ごとに CV 学習し、oof / test 予測を seed 横断で平均（seed bagging）
    oof_per_seed: list[np.ndarray] = []
    all_models: list[Any] = []
    seed_scores: list[dict[str, Any]] = []
    for sd in seeds:
        oof_s, models_s = train_cv(
            X_train,
            y_train,
            params=model_cfg.get("params", {}),
            notes=f"{run_id} seed={sd} via train.py",
            n_folds=n_folds,
            seed=sd,
            max_folds=max_folds,
            num_boost_round=num_boost_round,
            early_stopping_rounds=early_stopping_rounds,
            log_run_id=f"{run_id}_s{sd}" if len(seeds) > 1 else run_id,
        )
        mask_s = _trained_mask(oof_s)
        seed_scores.append({"seed": sd, "cv_score": cv_score(y_train.loc[mask_s].to_numpy(), oof_s[mask_s])})
        oof_per_seed.append(oof_s)
        all_models.extend(models_s)

    oof = np.mean(oof_per_seed, axis=0)
    trained_mask = _trained_mask(oof)
    metrics = {
        "run_id": run_id,
        "competition": cfg.get("data", cfg)["comp"],
        "model": model_cfg.get("name", "lgbm"),
        "metric": cfg.get("data", cfg)["metric"],
        "cv_score": cv_score(y_train.loc[trained_mask].to_numpy(), oof[trained_mask]),
        "seeds": seeds,
        "n_seeds": len(seeds),
        "seed_scores": seed_scores,
        "n_folds_requested": n_folds,
        "n_folds_trained": int(max_folds or n_folds),
        "smoke": smoke,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    # all_models は seed×fold 全モデル → predict/make_submission の平均が seed 平均になる
    _write_oof(run_dir / "oof.parquet", y_train, oof, trained_mask)
    preds = predict(X_test, all_models)
    _write_predictions(run_dir / "test_pred.parquet", preds)
    _write_feature_importance(run_dir / "feature_importance.csv", all_models, X_train.columns)
    make_submission(X_test, all_models, out_path=run_dir / "submission.csv", original_test=test_df)
    _write_models(run_dir / "model", all_models, meta={
        "objective": cfg.get("data", cfg).get("objective"),
        "num_class": int(oof.shape[1]) if oof.ndim > 1 else 1,
        "metric": cfg.get("data", cfg)["metric"],
        "competition": cfg.get("data", cfg)["comp"],
        "run_id": run_id,
        "seeds": seeds,
        "n_folds_trained": int(max_folds or n_folds),
        "feature_names": list(map(str, X_train.columns)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return float(metrics["cv_score"])


def _report_hp_metric(tag: str, value: float) -> None:
    """Vertex Hyperparameter Tuning(Vizier) に trial の評価値を報告する。"""
    try:
        import hypertune

        hypertune.HyperTune().report_hyperparameter_tuning_metric(
            hyperparameter_metric_tag=tag, metric_value=value, global_step=1,
        )
        print(f"[train] reported hp metric {tag}={value:.6f}")
    except Exception as exc:  # noqa: BLE001 - 報告失敗で学習結果は壊さない
        print(f"[train] hp metric report skipped: {exc}")


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


def _write_models(model_dir: Path, models: list[Any], *, meta: dict[str, Any]) -> None:
    """学習済み booster を保存（Vertex Model Registry 登録 = runner.model.register の成果物）。

    seed×fold の全 booster を保存し、推論は全 booster の平均（pipelines.score.predict と同じ）。
    `manifest.json` が boosters の一覧と推論方法・メタを持つ。
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for i, model in enumerate(models):
        if hasattr(model, "save_model"):
            fname = f"booster_{i:03d}.txt"
            model.save_model(str(model_dir / fname))
            saved.append(fname)
    manifest = {
        "model_type": "lightgbm-seedbag",
        "framework": "lightgbm",
        "n_boosters": len(saved),
        "boosters": saved,
        "predict": "mean over boosters (proba for classification)",
        **meta,
    }
    (model_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[train] saved {len(saved)} boosters -> {model_dir}")


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
