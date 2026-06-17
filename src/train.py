"""LightGBM 5-fold CV ループ。config.py の値で挙動が変わる。"""
import uuid
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
from sklearn.metrics import mean_squared_error, roc_auc_score, log_loss
from sklearn.model_selection import KFold, StratifiedKFold

from config import METRIC, N_FOLDS, OBJECTIVE, SEED
from logger import log_run

_LGB_PARAMS: dict = {
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


def _cv_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if METRIC == "rmse":
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
    if METRIC == "auc":
        return float(roc_auc_score(y_true, y_pred))
    if METRIC == "logloss":
        return float(log_loss(y_true, y_pred))
    raise ValueError(f"未対応の metric: {METRIC}")


def train_cv(
    X_train,
    y_train,
    params: dict | None = None,
    notes: str = "",
) -> tuple[np.ndarray, list[lgb.Booster]]:
    """OOF 予測と学習済みモデルリストを返す。"""
    lgb_params = {**_LGB_PARAMS, **(params or {})}

    if OBJECTIVE == "regression":
        kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
        splits = list(kf.split(X_train))
    else:
        kf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
        splits = list(kf.split(X_train, y_train))

    oof = np.zeros(len(y_train))
    models: list[lgb.Booster] = []
    fold_scores: list[float] = []

    for fold, (tr_idx, val_idx) in enumerate(splits):
        X_tr, X_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

        ds_tr = lgb.Dataset(X_tr, label=y_tr)
        ds_val = lgb.Dataset(X_val, label=y_val, reference=ds_tr)

        model = lgb.train(
            lgb_params,
            ds_tr,
            num_boost_round=2000,
            valid_sets=[ds_val],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=200),
            ],
        )
        oof[val_idx] = model.predict(X_val)
        models.append(model)

        score = _cv_score(y_val.values, oof[val_idx])
        fold_scores.append(score)
        print(f"  fold {fold + 1}/{N_FOLDS}  {METRIC}={score:.5f}")

    cv_score = float(np.mean(fold_scores))
    print(f"\n[train] CV {METRIC} = {cv_score:.5f}  (std={np.std(fold_scores):.5f})")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    log_run(run_id=run_id, cv_score=cv_score, params=lgb_params, notes=notes)

    return oof, models
