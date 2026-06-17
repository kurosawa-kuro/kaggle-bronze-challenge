# 02 アーキテクチャ

## Databricks パターン準拠の構造

```
scripts/
  init_competition.py  ← make init の実体（download→正規化→分析→doc生成）
conf/                    ← 設定（コンペ切り替え時はここだけ変える）
  config.yaml
src/
  config.py              ← conf/config.yaml を定数化
  ports.py               ← Protocol 定義（ModelTrainer / FeatureTransformer）
  pipelines/             ← ML パイプラインステージ（Databricks パターン）
    ingest.py            ← Bronze→Silver: load_data() + encode()
    featurize.py         ← Silver→Gold: make_features()
    evaluate.py          ← cv_score() 全モデル共用
    score.py             ← predict() / make_submission()
  models/                ← モデル別 train_cv()（全て同一シグネチャ）
    lgbm.py
    catboost_.py
    xgboost_.py
    ensemble.py
  features/              ← add_*() FE 関数群（1アイデア=1ファイル）
  utils/
    logger.py            ← SQLite 実験ログ
notebooks/               ← 実験スクリプト（1実験=1ファイル）
  exp001_lgbm_base.py
  exp002_catboost_base.py
  exp003_ensemble_lgbm_cat.py
data/
  <comp>/                ← コンペごとに分離（再ダウンロード不要でコンペ切り替え可）
    raw/                 ← Bronze layer（Kaggle 生データ、gitignore）
    interim/             ← Silver layer（前処理済み parquet、gitignore）
    features/            ← Gold layer（特徴量 parquet、gitignore）
  experiments.db         ← 実験ログ SQLite（全コンペ共通）
run.py                   ← 現在の実験エントリポイント
```

## データフロー

```
data/raw/（Bronze）
  └─ train.csv / test.csv
        │
        ▼  pipelines/ingest.load_data() + encode()
        │
data/interim/（Silver）
  └─ train.parquet / test.parquet
        │
        ▼  pipelines/featurize.make_features()
        │  + features/*.add_*()（FE 追加時）
        │
[Gold: X_train, y_train, X_test]
        │
        ▼  models/lgbm.train_cv()（同一シグネチャで差し替え可）
        │
[oof, models] → utils/logger → data/experiments.db
        │
        ▼  pipelines/score.make_submission()
        │
submission.csv
```

## 構成要素

| モジュール | パス | 役割 |
|---|---|---|
| データセット設定 | `conf/config.yaml` | TARGET / OBJECTIVE / METRIC / N_FOLDS |
| 設定ローダー | `src/config.py` | config.yaml を読んで定数化 |
| データロード・エンコード | `src/pipelines/ingest.py` | `load_data()` + `encode()`（FE は持たない） |
| 特徴量エンジニアリング | `src/pipelines/featurize.py` | `make_features()`（FE 関数を組み立てる） |
| 評価メトリクス | `src/pipelines/evaluate.py` | `cv_score()` 全モデル共用 |
| スコアリング | `src/pipelines/score.py` | `predict()` / `make_submission()` |
| LightGBM | `src/models/lgbm.py` | `train_cv()` |
| CatBoost | `src/models/catboost_.py` | `train_cv()` ← 同じシグネチャ |
| XGBoost | `src/models/xgboost_.py` | `train_cv()` ← 同じシグネチャ |
| アンサンブル | `src/models/ensemble.py` | `average(predictions)` |
| FE 関数群 | `src/features/` | `add_*()` 関数（1アイデア=1ファイル） |
| 実験ログ | `src/utils/logger.py` | SQLite (`data/experiments.db`) に記録 |
| Protocol | `src/ports.py` | `ModelTrainer` / `FeatureTransformer` |
| 現在の実験 | `run.py` | `make run` が実行するファイル |
| 実験履歴 | `notebooks/*.py` | 1 実験 = 1 ファイル。再実行可能 |

## Protocol（軽量インタフェース定義）

`src/ports.py` に 2 つの Protocol を定義する。  
DI・Adapter クラス・Composition Root は持たない。既存コードの変更も不要。

```python
# src/ports.py
class ModelTrainer(Protocol):
    def train_cv(self, X_train, y_train, params, notes) -> tuple[np.ndarray, list]: ...

class FeatureTransformer(Protocol):
    def __call__(self, X: pd.DataFrame) -> pd.DataFrame: ...
```

**ModelTrainer が保証すること**
- 全モデル（lgbm / catboost_ / xgboost_）が同じシグネチャを持つ
- シグネチャが変わると型チェッカーが検出する

**FeatureTransformer が保証すること**
- `add_*()` 関数が必ず `pd.DataFrame` を返す
- in-place 変更禁止（必ず `X.copy()` を返す）

## モデル切り替え

`run.py` の import 1 行を変えるだけで切り替わる:

```python
from models.lgbm      import train_cv   # LightGBM
from models.catboost_  import train_cv  # CatBoost に切り替え
from models.xgboost_   import train_cv  # XGBoost に切り替え
```

新モデルを追加するときは `src/models/` に新ファイルを作り、`ModelTrainer` Protocol を満たすシグネチャにする。

## 特徴量追加

`src/features/` に新ファイルを追加する。既存ファイルは変更しない。  
`FeatureTransformer` Protocol に準拠すること（`X.copy()` して返す）。

```python
# src/features/ratios.py
def add_ratio_features(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()                         # ← in-place 禁止
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

`make init COMP=<slug>` が download・ファイル正規化・config.yaml 下書き表示・competition doc 生成を1コマンドで行う（`scripts/init_competition.py`）。

## 境界・方針

- ソースは `src/` 配下（`PYTHONPATH=src` で import する）。
- 非機密の設定は `conf/config.yaml`。秘密情報は置かない（`conf/secret.yaml` は gitignore）。
- データ（`data/raw/`, `data/interim/`, `data/features/`, `data/experiments.db`）は gitignore。
- DI・Composition Root・strict 型注釈・本番 MLOps 水準のアーキテクチャは持ち込まない。
- インタフェース契約のみ `src/ports.py` の Protocol で明文化する。

## 関連タスク

- 構造変更・モジュール追加は `docs/tasks/active/` へ task を作ってから実施する。
- 確定した設計判断は task からこの文書へ昇格する。
