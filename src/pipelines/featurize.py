"""Silver → Gold: 特徴量エンジニアリングのエントリポイント。
ベースライン特徴量を組み立てる。新しい FE は features/ に追加して run.py で呼ぶ。
"""
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from config import ID_COL, TARGET
from pipelines.ingest import encode

# multiclass 時に make_features() が設定する。score.py が参照して class 名に戻す。
LABEL_CLASSES: list[str] | None = None


def make_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """X_train, y_train, X_test を返す。"""
    global LABEL_CLASSES

    y_train = train_df[TARGET]
    X_train = train_df.drop(columns=[TARGET])
    X_test = test_df.copy()

    # ID列は予測に不要なため除外（submission では original_test から取得）
    for col in [ID_COL]:
        if col and col in X_train.columns:
            X_train = X_train.drop(columns=[col])
        if col and col in X_test.columns:
            X_test = X_test.drop(columns=[col])

    # 文字列ターゲット（multiclass）はラベルエンコードして整数に変換する
    if not pd.api.types.is_numeric_dtype(y_train):
        le = LabelEncoder()
        y_train = pd.Series(le.fit_transform(y_train), index=y_train.index, name=TARGET)
        LABEL_CLASSES = le.classes_.tolist()
    else:
        LABEL_CLASSES = None

    X_train, X_test = encode(X_train, X_test)
    return X_train, y_train, X_test
