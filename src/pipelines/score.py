"""推論・提出ファイル生成（スコアリングパイプライン）。"""
from pathlib import Path

import numpy as np
import pandas as pd

import pipelines.featurize as _featurize

from config import ID_COL, OBJECTIVE, TARGET


def predict(X_test: pd.DataFrame, models: list) -> np.ndarray:
    """全 fold モデルの平均予測を返す。multiclass は (n_test, n_classes) を返す。"""
    return np.mean([m.predict(X_test) for m in models], axis=0)


def make_submission(
    X_test: pd.DataFrame,
    models: list,
    out_path: str | Path = "submission.csv",
    original_test: pd.DataFrame | None = None,
) -> pd.DataFrame:
    preds = predict(X_test, models)

    # multiclass: argmax で class インデックスを取り、元のラベル名に戻す
    if OBJECTIVE == "multiclass" and _featurize.LABEL_CLASSES is not None:
        pred_labels = [_featurize.LABEL_CLASSES[i] for i in np.argmax(preds, axis=1)]
        target_col = {TARGET: pred_labels}
    else:
        target_col = {TARGET: preds}

    # ID列: original_test → X_test の順に探す
    id_vals = None
    if ID_COL:
        if original_test is not None and ID_COL in original_test.columns:
            id_vals = original_test[ID_COL].values
        elif ID_COL in X_test.columns:
            id_vals = X_test[ID_COL].values

    if id_vals is not None:
        sub = pd.DataFrame({ID_COL: id_vals, **target_col})
    else:
        sub = pd.DataFrame(target_col)

    sub.to_csv(out_path, index=False)
    print(f"[score] submission saved → {out_path}  shape={sub.shape}")
    return sub
