"""Silver → Gold: 特徴量エンジニアリングのエントリポイント。
ベースライン特徴量を組み立てる。新しい FE は features/ に追加して run.py で呼ぶ。
"""
import pandas as pd

from config import TARGET
from pipelines.ingest import encode


def make_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """X_train, y_train, X_test を返す。"""
    y_train = train_df[TARGET]
    X_train = train_df.drop(columns=[TARGET])
    X_test = test_df.copy()

    X_train, X_test = encode(X_train, X_test)
    return X_train, y_train, X_test
