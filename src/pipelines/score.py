"""推論・提出ファイル生成（スコアリングパイプライン）。"""
from pathlib import Path

import numpy as np
import pandas as pd

from config import ID_COL, TARGET


def predict(X_test: pd.DataFrame, models: list) -> np.ndarray:
    """全 fold モデルの平均予測を返す。"""
    return np.mean([m.predict(X_test) for m in models], axis=0)


def make_submission(
    X_test: pd.DataFrame,
    models: list,
    out_path: str | Path = "submission.csv",
    original_test: pd.DataFrame | None = None,
) -> pd.DataFrame:
    preds = predict(X_test, models)

    if ID_COL and original_test is not None and ID_COL in original_test.columns:
        sub = pd.DataFrame({ID_COL: original_test[ID_COL].values, TARGET: preds})
    else:
        sub = pd.DataFrame({TARGET: preds})

    sub.to_csv(out_path, index=False)
    print(f"[score] submission saved → {out_path}  shape={sub.shape}")
    return sub
