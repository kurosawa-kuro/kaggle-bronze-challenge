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
  runner/                ← CLI エントリポイント群（python -m runner.X / PYTHONPATH=src）
    train.py             ← config 駆動の実験ランナー（local / Vertex 共通）
    vertex_run.py        ← Vertex Custom Job 投入
    collect.py           ← GCS から run_id 成果物回収
    submit.py            ← submission を Kaggle 提出
    costs.py             ← コスト概算ロガー（BigQuery）
    run.py               ← 旧・実験エントリポイント（make run）
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
    bq.py                ← BigQuery 共通ヘルパ（bq CLI 経由、costs/logger 共有）
    logger.py            ← 実験ログ → BigQuery (kaggle_ops.experiments)
notebooks/               ← 実験スクリプト（1実験=1ファイル）
  exp001_lgbm_base.py
  exp002_catboost_base.py
  exp003_ensemble_lgbm_cat.py
data/
  <comp>/                ← コンペごとに分離（再ダウンロード不要でコンペ切り替え可）
    raw/                 ← Bronze layer（Kaggle 生データ、gitignore）
    interim/             ← Silver layer（前処理済み parquet、gitignore）
    features/            ← Gold layer（特徴量 parquet、gitignore）
outputs/
  runs/<comp>/<run_id>/  ← run_id 成果物（config/metrics/oof/test_pred/submission/log）
```

> エントリポイントは `src/runner/` パッケージに集約し `python -m runner.<name>`（`PYTHONPATH=src`）で実行する。
> 注意: `gcloud`/`bq`/`kaggle` 等の外部 Python CLI に `PYTHONPATH=src` を渡すと、それらが import する `utils` を本リポの `src/utils` が shadow して壊れる。よって PYTHONPATH はグローバル export せず runner 実行時のみ付与し、外部 CLI を呼ぶ subprocess では PYTHONPATH を除去する（`Makefile` の `PYRUN`、`runner/costs.py`・`runner/submit.py` の `_clean_env`）。

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

## 実行モデル（Vertex-ready 実験契約）

> 決定: `docs/adr/0001-vertex-ready-experiment-runner.md` ／ 実装追跡: `docs/tasks/active/vertex-ready-runner.md`
> 本節は **目標契約**。下記の `train.py` / `vertex_run.py` / `collect.py` / `submit.py` と `make` ターゲットはタスク完了時に実体化する。

同一の学習コードを **ローカルでも Vertex Custom Job でも実行し、同一の run_id 成果物を出す**。
Vertex を本番基盤としてではなく、**並列実験ランナー**として使う。

### 実行分担

```
local   = 思考・1fold smoke・小さい特徴量検証・submission 生成確認
Vertex  = 5fold full / CatBoost / seed 平均 / 複数 config 並列 / overnight
Kaggle  = 最終 Notebook 化・submission 提出・LB 確認
```

### 学習コードと Vertex 固有コードの分離

Vertex 固有コードを学習処理に混ぜない。これを破ると後から詰まる。

| ファイル | 役割 |
|---|---|
| `train.py` | 純粋な Kaggle 学習。`--config` 駆動。local / Vertex 共通（Vertex を知らない） |
| `vertex_run.py` | Custom Job として `train.py` を投入するだけ |
| `collect.py` | GCS から run_id 成果物を回収する |
| `submit.py` | submission を整形し Kaggle へ提出する |

### run_id 成果物契約（local / Vertex で同一）

```
outputs/runs/{competition}/{run_id}/
  config.yaml            ← 投入に使った config のスナップショット
  metrics.json           ← cv_score / fold scores / seed 別スコア
  oof.parquet            ← out-of-fold 予測
  test_pred.parquet      ← test 予測（seed 平均後）
  feature_importance.csv
  submission.csv
  log.txt
```

- ローカル実行・Vertex 実行のどちらでも上記レイアウトを生成する。
- Vertex 実行時は `gs://<bucket>/runs/{competition}/{run_id}/` に同じ構造で保存し、`collect.py` で `outputs/runs/...` へ落とす。
- 既存の SQLite 実験ログ（`data/experiments.db`）は引き続き「軽量な横断インデックス」として残し、run_id 成果物が「正本の実体」を持つ。

### データ配送（Vertex）

`data/` はイメージに含めない（`.dockerignore` で除外）。`make stage-data` で `data/<comp>/raw` を `gs://<bucket>/data/<comp>/raw` へ上げ、コンテナ内 `train.py --input-uri` が起動時に取得して `data/<comp>/raw` へ展開する。Kaggle 認証を Vertex に持ち込まないための分離。

### config 駆動

`conf/config.yaml`（コンペ切替の最小設定）に加え、実験単位の config を `configs/*.yaml` に置き、`train.py --config configs/xxx.yaml` で投入する。
config には `model` / `cv` / `seeds` / `runtime`（`mode: local|vertex`, `machine_type`, `timeout_hours`）を持たせる。具体スキーマは実装タスクで確定する。

### CLI UX（品質ゲート）

投入までの手間が増えると Vertex は逆効果になる。1 コマンドで完結させる:

```bash
make smoke        CONFIG=configs/lgbm_baseline.yaml       # 1fold ローカル確認
make train-local  CONFIG=configs/lgbm_baseline.yaml       # full ローカル
make train-vertex CONFIG=configs/catboost_seed_avg.yaml   # Vertex へ投入
make collect      RUN_ID=latest                           # GCS から回収
make submit       RUN_ID=latest                           # 整形して提出
```

## 境界・方針

- ソースは `src/` 配下（`PYTHONPATH=src` で import する）。
- 非機密の設定は `conf/config.yaml`。秘密情報は置かない（`conf/secret.yaml` は gitignore）。GCP 認証情報も同様に gitignore / secret manager 管理。
- データ（`data/raw/`, `data/interim/`, `data/features/`, `data/experiments.db`）と `outputs/runs/` は gitignore。
- DI・Composition Root・strict 型注釈の過度な抽象は持ち込まない。非DL/GPU の Vertex/GCP マネージド機能はフル活用する（Custom Job / HP Tuning / Model Registry / Pipelines / Batch Prediction / Endpoint）。tabular メタデータの正本は BigQuery `kaggle_ops`、blob は GCS、学習投入は aiplatform SDK（ADR 0002 が 0001 を supersede）。
- インタフェース契約のみ `src/ports.py` の Protocol で明文化する。

## 関連タスク

- 構造変更・モジュール追加は `docs/tasks/active/` へ task を作ってから実施する。
- 確定した設計判断は task からこの文書へ昇格する。
