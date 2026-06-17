"""LightGBM train_cv()。他モデルと同じシグネチャ。"""
import uuid
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold

from config import METRIC, N_FOLDS, OBJECTIVE, SEED
from logger import log_run
from metrics import cv_score

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
    X_train, y_train, params: dict | None = None, notes: str = ""
) -> tuple[np.ndarray, list[lgb.Booster]]:
    lgb_params = {**_PARAMS, **(params or {})}

    splits = _splits(X_train, y_train)
    oof = np.zeros(len(y_train))
    models: list[lgb.Booster] = []
    fold_scores: list[float] = []

    for fold, (tr_idx, val_idx) in enumerate(splits):
        X_tr, X_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

        model = lgb.train(
            lgb_params,
            lgb.Dataset(X_tr, label=y_tr),
            num_boost_round=2000,
            valid_sets=[lgb.Dataset(X_val, label=y_val)],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=200),
            ],
        )
        oof[val_idx] = model.predict(X_val)
        models.append(model)

        score = cv_score(y_val.values, oof[val_idx])
        fold_scores.append(score)
        print(f"  [lgbm] fold {fold + 1}/{N_FOLDS}  {METRIC}={score:.5f}")

    _log(fold_scores, lgb_params, notes)
    return oof, models


def _splits(X, y):
    if OBJECTIVE == "regression":
        return list(KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X))
    return list(StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X, y))


def _log(fold_scores, params, notes):
    mean = float(np.mean(fold_scores))
    std = float(np.std(fold_scores))
    print(f"\n[lgbm] CV {METRIC} = {mean:.5f}  (std={std:.5f})")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_lgbm_" + uuid.uuid4().hex[:4]
    log_run(run_id=run_id, cv_score=mean, params=params, notes=notes)
