# 02 アーキテクチャ

## データフロー

```
data/raw/
  └─ train.csv / test.csv
        │
        ▼
preprocess.load_data()          → data/interim/train.parquet, test.parquet
        │
        ▼
features/base.make_features()   → X_train, y_train, X_test
  (+ features/xxx.add_*() で FE を追加)
        │
        ▼
models/lgbm.train_cv()          → oof, models  ← SQLite に cv_score を記録
  (lgbm / catboost_ / xgboost_ は同一シグネチャで差し替え可)
        │
        ▼
predict.make_submission()       → submission.csv
```

## 構成要素

| モジュール | パス | 役割 |
|---|---|---|
| データセット設定 | `env/config.yaml` | TARGET / OBJECTIVE / METRIC / N_FOLDS |
| 設定ローダー | `src/config.py` | config.yaml を読んで定数化 |
| データロード・エンコード | `src/preprocess.py` | `load_data()` + `_encode()` のみ。FE は持たない |
| 特徴量 | `src/features/` | `make_features()` / `add_*()` |
| メトリクス | `src/metrics.py` | `cv_score()` 全モデル共用 |
| LightGBM | `src/models/lgbm.py` | `train_cv()` |
| CatBoost | `src/models/catboost_.py` | `train_cv()` ← 同じシグネチャ |
| XGBoost | `src/models/xgboost_.py` | `train_cv()` ← 同じシグネチャ |
| アンサンブル | `src/models/ensemble.py` | `average(predictions)` |
| 実験ログ | `src/logger.py` | SQLite (`data/experiments.db`) に記録 |
| 推論・提出 | `src/predict.py` | `predict()` / `make_submission()` |
| 現在の実験 | `run.py` | `make run` が実行するファイル |
| 実験履歴 | `experiments/*.py` | 1 実験 = 1 ファイル。再実行可能な形で保存 |

## モデル切り替え

全モデルは同じシグネチャ:

```python
train_cv(X_train, y_train, params=None, notes="") -> tuple[np.ndarray, list]
```

`run.py` の import 1 行を変えるだけで切り替わる:

```python
from models.lgbm     import train_cv   # LightGBM
from models.catboost_ import train_cv  # CatBoost に切り替え
from models.xgboost_  import train_cv  # XGBoost に切り替え
```

## 特徴量追加

`src/features/` に新ファイルを追加する。既存ファイルは変更しない。

```python
# src/features/ratios.py
def add_ratio_features(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    X["rooms_per_age"] = X["AveRooms"] / X["HouseAge"]
    return X
```

run.py で呼び出す:

```python
from features.ratios import add_ratio_features
X_train = add_ratio_features(X_train)
X_test  = add_ratio_features(X_test)
```

## コンペ切り替え

`env/config.yaml` の 4 項目を変えるだけ。データを `data/raw/` に置いて `data/interim/` を削除すれば `make run` が動く。

## 境界・方針

- ソースは `src/` 配下（`PYTHONPATH=src` で import する）。
- 非機密の設定は `env/config.yaml`。秘密情報は置かない。
- データ（`data/raw/`, `data/interim/`, `data/experiments.db`）は gitignore。
- Port/Adapter・strict 型注釈・本番 MLOps 水準のアーキテクチャは持ち込まない。

## 関連タスク

- 構造変更・モジュール追加は `docs/tasks/active/` へ task を作ってから実施する。
- 確定した設計判断は task からこの文書へ昇格する。
