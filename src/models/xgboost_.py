"""XGBoost train_cv()。lgbm.py と同じシグネチャ。"""
import uuid
from datetime import datetime, timezone

import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold

from config import METRIC, N_FOLDS, OBJECTIVE, SEED
from pipelines.evaluate import cv_score
from utils.logger import log_run

_OBJECTIVE_MAP = {
    "regression": "reg:squarederror",
    "binary": "binary:logistic",
    "multiclass": "multi:softprob",
}
_METRIC_MAP = {
    "rmse": "rmse",
    "auc": "auc",
    "logloss": "logloss",
}


def train_cv(
    X_train, y_train, params: dict | None = None, notes: str = ""
) -> tuple[np.ndarray, list]:
    import xgboost as xgb

    base_params = {
        "objective": _OBJECTIVE_MAP[OBJECTIVE],
        "eval_metric": _METRIC_MAP.get(METRIC, "rmse"),
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "seed": SEED,
    }
    merged = {**base_params, **(params or {})}

    splits = _splits(X_train, y_train)
    oof = np.zeros(len(y_train))
    models = []
    fold_scores: list[float] = []

    for fold, (tr_idx, val_idx) in enumerate(splits):
        X_tr, X_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

        dtrain = xgb.DMatrix(X_tr, label=y_tr)
        dval = xgb.DMatrix(X_val, label=y_val)

        model = xgb.train(
            merged,
            dtrain,
            num_boost_round=2000,
            evals=[(dval, "val")],
            early_stopping_rounds=50,
            verbose_eval=200,
        )
        oof[val_idx] = model.predict(dval)
        models.append(model)

        score = cv_score(y_val.values, oof[val_idx])
        fold_scores.append(score)
        print(f"  [xgboost] fold {fold + 1}/{N_FOLDS}  {METRIC}={score:.5f}")

    _log(fold_scores, merged, notes)
    return oof, models


def _splits(X, y):
    if OBJECTIVE == "regression":
        return list(KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X))
    return list(StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X, y))


def _log(fold_scores, params, notes):
    mean = float(np.mean(fold_scores))
    std = float(np.std(fold_scores))
    print(f"\n[xgboost] CV {METRIC} = {mean:.5f}  (std={std:.5f})")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_xgb_" + uuid.uuid4().hex[:4]
    log_run(run_id=run_id, cv_score=mean, params=params, notes=notes)
