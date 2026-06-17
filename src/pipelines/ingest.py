"""Bronze → Silver: データロードと基本エンコーディング。
Kaggle コンペ転用時は load_data() だけ差し替える。
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

from config import DATA_INTERIM, DATA_RAW, TARGET


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(train_df, test_df) を返す。

    1. data/<comp>/interim/train.parquet があれば即返す（キャッシュ）
    2. data/<comp>/raw/train.csv があれば Kaggle CSV モード
    3. いずれもなければ California Housing（練習用）
    """
    if (DATA_INTERIM / "train.parquet").exists():
        return (
            pd.read_parquet(DATA_INTERIM / "train.parquet"),
            pd.read_parquet(DATA_INTERIM / "test.parquet"),
        )

    if (DATA_RAW / "train.csv").exists():
        return _load_from_csv()

    return _load_california_housing()


def _load_from_csv() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kaggle コンペモード: data/<comp>/raw/train.csv を読む"""
    train_df = pd.read_csv(DATA_RAW / "train.csv")
    test_df = pd.read_csv(DATA_RAW / "test.csv")
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    train_df.to_parquet(DATA_INTERIM / "train.parquet", index=False)
    test_df.to_parquet(DATA_INTERIM / "test.parquet", index=False)
    print(f"[ingest] Kaggle CSV: train={len(train_df)}  test={len(test_df)}")
    return train_df, test_df


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
    print(f"[ingest] California Housing: train={len(train_df)}  test={len(test_df)}")
    return train_df, test_df


def encode(
    X_train: pd.DataFrame, X_test: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """null 埋め + OrdinalEncoding。fit は学習データのみ（リーク防止）。"""
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
