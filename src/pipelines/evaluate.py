"""モデル評価メトリクス。全モデルで共用する。"""
import numpy as np
from sklearn.metrics import log_loss, mean_squared_error, roc_auc_score

from config import METRIC


def cv_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if METRIC == "rmse":
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
    if METRIC == "auc":
        return float(roc_auc_score(y_true, y_pred))
    if METRIC == "logloss":
        return float(log_loss(y_true, y_pred))
    raise ValueError(f"未対応の metric: {METRIC}")
