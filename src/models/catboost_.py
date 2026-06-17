"""CatBoost train_cv()。lgbm.py と同じシグネチャ。"""
import uuid
from datetime import datetime, timezone

import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold

from config import METRIC, N_FOLDS, OBJECTIVE, SEED
from pipelines.evaluate import cv_score
from utils.logger import log_run

_LOSS_MAP = {
    "regression": "RMSE",
    "binary": "Logloss",
    "multiclass": "MultiClass",
}


def train_cv(
    X_train, y_train, params: dict | None = None, notes: str = ""
) -> tuple[np.ndarray, list]:
    from catboost import CatBoostClassifier, CatBoostRegressor

    base_params = {
        "iterations": 1000,
        "learning_rate": 0.05,
        "depth": 6,
        "early_stopping_rounds": 50,
        "random_seed": SEED,
        "verbose": 200,
    }
    merged = {**base_params, **(params or {})}

    loss_fn = _LOSS_MAP[OBJECTIVE]
    ModelCls = CatBoostRegressor if OBJECTIVE == "regression" else CatBoostClassifier

    splits = _splits(X_train, y_train)
    n_classes = int(y_train.nunique()) if OBJECTIVE == "multiclass" else 1
    oof = np.zeros((len(y_train), n_classes)) if n_classes > 1 else np.zeros(len(y_train))
    models = []
    fold_scores: list[float] = []

    for fold, (tr_idx, val_idx) in enumerate(splits):
        X_tr, X_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

        model = ModelCls(loss_function=loss_fn, **merged)
        model.fit(X_tr, y_tr, eval_set=(X_val, y_val))
        models.append(model)

        # multiclass は predict_proba で確率を取得（log_loss に必要）
        if OBJECTIVE == "multiclass":
            oof[val_idx] = model.predict_proba(X_val)
        else:
            oof[val_idx] = model.predict(X_val).flatten()

        score = cv_score(y_val.values, oof[val_idx])
        fold_scores.append(score)
        print(f"  [catboost] fold {fold + 1}/{N_FOLDS}  {METRIC}={score:.5f}")

    _log(fold_scores, merged, notes)
    return oof, models


def _splits(X, y):
    if OBJECTIVE == "regression":
        return list(KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X))
    return list(StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X, y))


def _log(fold_scores, params, notes):
    mean = float(np.mean(fold_scores))
    std = float(np.std(fold_scores))
    print(f"\n[catboost] CV {METRIC} = {mean:.5f}  (std={std:.5f})")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_cat_" + uuid.uuid4().hex[:4]
    log_run(run_id=run_id, cv_score=mean, params=params, notes=notes)
