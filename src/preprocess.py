"""データロード・null埋め・エンコーディング。
特徴量エンジニアリングは src/features/ に分離している。
Kaggle コンペ転用時: load_data() を差し替えるだけ。
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

from config import DATA_INTERIM, TARGET


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(train_df, test_df) を返す。

    California Housing モード: sklearn から取得し train/test を 8:2 分割する。
    Kaggle コンペ転用時: data/raw/train.csv と data/raw/test.csv を読む。
    """
    raw_train = DATA_INTERIM / "train.parquet"
    raw_test = DATA_INTERIM / "test.parquet"

    if raw_train.exists():
        return pd.read_parquet(raw_train), pd.read_parquet(raw_test)

    return _load_california_housing()


def _load_california_housing() -> tuple[pd.DataFrame, pd.DataFrame]:
    from sklearn.datasets import fetch_california_housing
    from sklearn.model_selection import train_test_split

    data = fetch_california_housing(as_frame=True)
    df = data.frame

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    test_df = test_df.drop(columns=[TARGET])

    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    train_df.to_parquet(DATA_INTERIM / "train.parquet", index=False)
    test_df.to_parquet(DATA_INTERIM / "test.parquet", index=False)
    print(f"[preprocess] California Housing: train={len(train_df)}  test={len(test_df)}")
    return train_df, test_df


def _encode(
    X_train: pd.DataFrame, X_test: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """null 埋め + OrdinalEncoding。features/ から呼ばれる共通処理。"""
    cat_cols = X_train.select_dtypes(exclude=np.number).columns.tolist()
    num_cols = X_train.select_dtypes(include=np.number).columns.tolist()

    for col in num_cols:
        med = X_train[col].median()
        X_train[col] = X_train[col].fillna(med)
        X_test[col] = X_test[col].fillna(med)

    for col in cat_cols:
        X_train[col] = X_train[col].fillna("__missing__")
        X_test[col] = X_test[col].fillna("__missing__")

    if cat_cols:
        enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        X_train[cat_cols] = enc.fit_transform(X_train[cat_cols])
        X_test[cat_cols] = enc.transform(X_test[cat_cols])

    return X_train, X_test
