"""Optuna で LightGBM ハイパーパラメータを探索する（40 trial）。
使い方: make nb NB=optuna_lgbm
結果の best_params を run.py の train_cv(params={...}) に貼る。
"""
import sys; sys.path.insert(0, "src")

import numpy as np
import lightgbm as lgb
import optuna
from sklearn.model_selection import KFold, StratifiedKFold

from config import METRIC, N_FOLDS, OBJECTIVE, SEED
from pipelines.ingest import load_data
from pipelines.featurize import make_features
from pipelines.evaluate import cv_score

optuna.logging.set_verbosity(optuna.logging.WARNING)

N_TRIALS = 40

train_df, test_df = load_data()
X_train, y_train, _ = make_features(train_df, test_df)

if OBJECTIVE == "regression":
    splits = list(KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X_train))
else:
    splits = list(StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED).split(X_train, y_train))

BASE_PARAMS = {
    "objective": OBJECTIVE,
    "metric": METRIC,
    "bagging_freq": 5,
    "seed": SEED,
    "verbosity": -1,
}


def objective(trial: optuna.Trial) -> float:
    params = {
        **BASE_PARAMS,
        "num_leaves": trial.suggest_int("num_leaves", 31, 255),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "lambda_l1": trial.suggest_float("lambda_l1", 1e-8, 10.0, log=True),
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-8, 10.0, log=True),
    }
    if OBJECTIVE == "multiclass":
        params["num_class"] = int(y_train.nunique())
        if params.get("metric") == "logloss":
            params["metric"] = "multi_logloss"

    fold_scores = []
    for tr_idx, val_idx in splits:
        X_tr, X_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]
        model = lgb.train(
            params,
            lgb.Dataset(X_tr, label=y_tr),
            num_boost_round=500,
            valid_sets=[lgb.Dataset(X_val, label=y_val)],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50, verbose=False),
                lgb.log_evaluation(period=9999),
            ],
        )
        fold_scores.append(cv_score(y_val.values, model.predict(X_val)))

    return float(np.mean(fold_scores))


study = optuna.create_study(
    direction="minimize",
    sampler=optuna.samplers.TPESampler(seed=SEED),
)
study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

best = study.best_params
print(f"\n{'='*50}")
print(f"Best CV {METRIC} : {study.best_value:.5f}  (前回: 0.09215)")
print(f"{'='*50}")
print("run.py の train_cv(params={...}) に貼るパラメータ:")
print("{")
for k, v in best.items():
    if isinstance(v, float):
        print(f'    "{k}": {v:.6f},')
    else:
        print(f'    "{k}": {v},')
print("}")
