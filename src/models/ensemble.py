"""複数モデルの予測を結合する。"""
import numpy as np


def average(predictions: list[np.ndarray], weights: list[float] | None = None) -> np.ndarray:
    """単純平均 or 重み付き平均。"""
    if weights is None:
        return np.mean(predictions, axis=0)
    w = np.array(weights, dtype=float)
    w /= w.sum()
    return sum(p * wi for p, wi in zip(predictions, w))
