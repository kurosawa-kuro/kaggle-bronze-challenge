"""ベースライン特徴量。生データをそのまま使う。
新しいFEアイデアは features/ に別ファイルで追加する。例:
  src/features/ratios.py  → add_ratio_features(X)
  src/features/aggs.py    → add_agg_features(X)
"""
import pandas as pd

from preprocess import _encode
from config import TARGET


def make_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """X_train, y_train, X_test を返す。"""
    y_train = train_df[TARGET]
    X_train = train_df.drop(columns=[TARGET])
    X_test = test_df.copy()

    X_train, X_test = _encode(X_train, X_test)
    return X_train, y_train, X_test
