"""軽量 Protocol 定義。モデルと特徴量変換の契約を明文化する。
既存コードの変更は不要 — 全モデル・全 FE がすでにこの Protocol を満たしている。
"""
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd


@runtime_checkable
class ModelTrainer(Protocol):
    """全モデルが満たすべきインタフェース。
    lgbm.py / catboost_.py / xgboost_.py はこの Protocol に適合する。
    """

    def train_cv(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        params: dict | None,
        notes: str,
    ) -> tuple[np.ndarray, list]: ...


@runtime_checkable
class FeatureTransformer(Protocol):
    """FE 追加関数が満たすべきインタフェース。
    features/base.py の make_features() および features/*.add_*() はこれに適合する。
    呼び出し元: X_new = transformer(X)
    - 引数の X を in-place で変更してはならない（必ず X.copy() を返す）
    - 返り値は必ず pd.DataFrame
    """

    def __call__(self, X: pd.DataFrame) -> pd.DataFrame: ...
