"""LightGBM train_cv()。他モデルと同じシグネチャ。"""
import uuid
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold

from config import METRIC, N_FOLDS, OBJECTIVE, SEED
from pipelines.evaluate import cv_score
from utils.logger import log_run

_PARAMS: dict = {
    "objective": OBJECTIVE,
    "metric": METRIC,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "seed": SEED,
    "verbosity": -1,
}


def train_cv(
    X_train,
    y_train,
    params: dict | None = None,
    notes: str = "",
    *,
    n_folds: int | None = None,
    seed: int | None = None,
    max_folds: int | None = None,
    num_boost_round: int = 2000,
    early_stopping_rounds: int = 50,
    log_run_id: str | None = None,
) -> tuple[np.ndarray, list[lgb.Booster]]:
    n_folds = n_folds or N_FOLDS
    seed = seed or SEED
    lgb_params = {**_PARAMS, "seed": seed, **(params or {})}

    # multiclass: num_class 自動設定 + LightGBM の metric 名を合わせる
    if OBJECTIVE == "multiclass":
        if "num_class" not in lgb_params:
            lgb_params["num_class"] = int(y_train.nunique())
        if lgb_params.get("metric") == "logloss":
            lgb_params["metric"] = "multi_logloss"

    num_class = lgb_params.get("num_class", 1)
    splits = _splits(X_train, y_train, n_folds=n_folds, seed=seed)
    if max_folds is not None:
        splits = splits[:max_folds]

    # multiclass は (n_samples, n_classes)、それ以外は (n_samples,)
    oof = np.zeros((len(y_train), num_class)) if num_class > 1 else np.zeros(len(y_train))
    models: list[lgb.Booster] = []
    fold_scores: list[float] = []

    for fold, (tr_idx, val_idx) in enumerate(splits):
        X_tr, X_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

        model = lgb.train(
            lgb_params,
            lgb.Dataset(X_tr, label=y_tr),
            num_boost_round=num_boost_round,
            valid_sets=[lgb.Dataset(X_val, label=y_val)],
            callbacks=[
                lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False),
                lgb.log_evaluation(period=200),
            ],
        )
        oof[val_idx] = model.predict(X_val)
        models.append(model)

        score = cv_score(y_val.values, oof[val_idx])
        fold_scores.append(score)
        print(f"  [lgbm] fold {fold + 1}/{len(splits)}  {METRIC}={score:.5f}")

    _log(fold_scores, lgb_params, notes, run_id=log_run_id)
    return oof, models


def _splits(X, y, *, n_folds: int, seed: int):
    if OBJECTIVE == "regression":
        return list(KFold(n_splits=n_folds, shuffle=True, random_state=seed).split(X))
    return list(StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed).split(X, y))


def _log(fold_scores, params, notes, *, run_id: str | None = None):
    mean = float(np.mean(fold_scores))
    std = float(np.std(fold_scores))
    print(f"\n[lgbm] CV {METRIC} = {mean:.5f}  (std={std:.5f})")
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_lgbm_" + uuid.uuid4().hex[:4]
    log_run(run_id=run_id, cv_score=mean, params=params, notes=notes)
