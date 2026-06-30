# 02 アーキテクチャ

## 現在の構造

```
Makefile
env/
  config.yaml             # 旧 run 経路 / default config
  project.yaml            # repo path + GCP project / bucket / image / BQ / cost 設定
  secret.yaml             # gitignore。Kaggle token / Discord webhook 等
configs/
  lgbm_baseline.yaml      # runner.experiment.train 用 config
  lgbm_deep.yaml
infra/
  Dockerfile              # Vertex 用学習 image
  Dockerfile.serving      # Vertex 推論コンテナ（Batch Prediction / Endpoint 用）
scripts/
  init_competition.py
src/
  config.py               # flat / nested config を定数化。KBC_CONFIG_PATH 対応
  ports.py                # 軽量 Protocol
  runner/                 # 責務別サブパッケージ（python -m runner.<group>.<name>）
    run.py                # 旧 `make run` の実体（legacy）
    experiment/           # 学習・探索を「回す」
      train.py            # local / Vertex 共通の config 駆動学習 runner
      vertex_run.py       # Vertex Custom Job submitter
      tune.py             # Optuna tuning
      sweep.py            # 複数 config を Custom Job に fan-out
      hp_tune.py          # Vertex Hyperparameter Tuning submitter
    model/                # モデルの「登録〜配信」ライフサイクル
      register.py         # Vertex Model Registry 登録
      pipeline.py         # Vertex Pipelines (KFP): train -> register の DAG
      batch_predict.py    # Vertex Batch Prediction 投入
      deploy.py           # Vertex Endpoint deploy/teardown（⚠️常駐コスト）
    ops/                  # 周辺運用
      collect.py          # GCS run_id 成果物を local に回収
      submit.py           # run_id の submission.csv を Kaggle 提出
      costs.py            # Vertex job 概算コストを BigQuery に記録
  serving/
    predictor.py          # Vertex 推論コンテナ本体（LightGBM seed-bag, stdlib HTTP）
  pipelines/
    ingest.py             # load_data() + encode()
    featurize.py          # make_features()
    evaluate.py           # cv_score()
    score.py              # predict() / make_submission()
  models/
    lgbm.py
    catboost_.py
    xgboost_.py
    ensemble.py
  features/
  utils/
    artifact_store.py     # GCS directory upload/download
    bq.py                 # bq CLI helper
    logger.py             # BigQuery experiments logger
notebooks/
data/                     # gitignore
outputs/runs/<comp>/<run_id>/  # gitignore
```

エントリポイントは `src/runner/` に集約する。Makefile の `PYRUN` は `PYTHONPATH=src .venv/bin/python -m runner.<name>` を使う。  
外部 CLI（`gcloud`, `bq`, `kaggle`）には `PYTHONPATH=src` を渡さない。`src/utils` が CLI 側の `utils` import を shadow して壊すため、`utils.bq.clean_env()` や `runner.ops.submit` で環境変数を除去する。

## 実行モデル

```
local
  make smoke / train-local / tune
      │
      ▼
src/runner/train.py
  ├─ config 読み込み（--config or --config-b64）
  ├─ optional GCS input staging（--input-uri）
  ├─ pipelines.ingest / featurize
  ├─ models.lgbm.train_cv
  ├─ seed 平均
  ├─ run_id 成果物生成
  ├─ BigQuery experiments log
  └─ optional GCS upload（--output-uri）

Vertex
  make train-vertex / sweep / hp-tune
      │
      ▼
src/runner/vertex_run.py or hp_tune.py
      │
      ▼
Vertex AI Custom Job / HyperparameterTuningJob
      │
      ▼
python -m runner.experiment.train
```

## データフロー

```
Kaggle download / make init
  │
  ▼
data/<comp>/raw/train.csv, test.csv
  │
  ├─ local: pipelines.ingest.load_data()
  │
  └─ Vertex: make stage-data
        gs://<bucket>/data/<comp>/raw/
          │
          ▼
        runner.experiment.train --input-uri

pipelines.ingest.encode()
  │
  ▼
pipelines.featurize.make_features()
  │
  ▼
models.lgbm.train_cv()
  │
  ├─ utils.logger.log_run() → BigQuery <bqDataset>.experiments
  └─ runner.experiment.train → outputs/runs/<comp>/<run_id>/
                         └─ Vertex 時は gs://<bucket>/runs/<comp>/<run_id>/
```

## 構成要素

| モジュール | 役割 |
|---|---|
| `src/runner/experiment/train.py` | config 駆動の学習 runner。現状 `model.name=lgbm` のみ対応 |
| `src/runner/experiment/vertex_run.py` | Custom Job spec 作成・投入。config は base64 で渡すため新 config でも image rebuild 不要 |
| `src/runner/experiment/sweep.py` | 複数 config を非ブロッキング `.submit()` で並列投入 |
| `src/runner/experiment/tune.py` | Optuna による単一マシン HPO。`best_params.json`, `best_config.yaml`, `trials.csv` を生成 |
| `src/runner/experiment/hp_tune.py` | Vertex Hyperparameter Tuning（Vizier）を投入 |
| `src/runner/ops/costs.py` | Vertex Custom Job の start/end と machine type から概算コストを BigQuery に記録 |
| `src/runner/model/register.py` | `gs://<bucket>/runs/<comp>/<run_id>/model` を Vertex Model Registry に登録。`kaggle-<comp>` に版を積む（`latest` alias）。serving 未配線 |
| `src/runner/model/pipeline.py` | Vertex Pipelines (KFP v2)。既存イメージを container component にして `train` → `register` の DAG を compile + 投入。`--dry-run` で compile のみ |
| `src/runner/model/batch_predict.py` | 登録モデル（`--serving-image` 付き）に対し Vertex Batch Prediction を投入。`--dry-run` で plan のみ |
| `src/runner/model/deploy.py` | servable モデルを Vertex Endpoint に deploy / teardown。⚠️常駐コストのため自動デプロイしない設計、終了後 teardown 必須 |
| `src/runner/ops/collect.py` | GCS の run_id 成果物を local に回収 |
| `src/runner/ops/submit.py` | run_id の submission.csv を Kaggle に提出 |
| `src/serving/predictor.py` | 推論コンテナ本体。`model/`(booster+manifest) を読み全 booster 平均を返す。stdlib HTTP で `/health` `/predict` を提供（新 infra lib なし） |
| `src/utils/logger.py` | CV 結果を BigQuery `<bqDataset>.experiments` に記録。失敗しても学習は止めない |
| `src/utils/artifact_store.py` | GCS prefix と local directory の 1:1 upload/download |
| `src/utils/bq.py` | `bq` CLI 経由の最小 BigQuery helper |

## run_id 成果物契約

local / Vertex ともに同じレイアウトを正本とする。

```
outputs/runs/<competition>/<run_id>/
  config.yaml
  metrics.json
  oof.parquet
  test_pred.parquet
  feature_importance.csv
  submission.csv
  log.txt
  model/
    booster_NNN.txt       # seed×fold の全 booster
    manifest.json         # boosters 一覧・推論方法・objective/num_class/feature_names
```

Vertex 実行時は `gs://<bucket>/runs/<competition>/<run_id>/` に同じ内容を upload し、`make collect RUN_ID=<id>` で local に回収する。`model/` は `make register-model RUN_ID=<id>` が Vertex Model Registry へ登録する成果物。

## config 配送

- local 実行: `--config configs/foo.yaml`
- Vertex Custom Job / sweep / HPT: submitter が config YAML を base64 化し、`runner.experiment.train --config-b64 ...` へ渡す

これにより config 追加・変更だけなら Docker image の rebuild は不要。`src/` や依存を変えた場合のみ `make build-push` が必要。

## Protocol

`src/ports.py` は軽量なインタフェース定義のみを持つ。DI container や adapter 層は持たない。

- `ModelTrainer`: `train_cv(X_train, y_train, params, notes) -> tuple[np.ndarray, list]`
- `FeatureTransformer`: `pd.DataFrame -> pd.DataFrame`

現実の `models.lgbm.train_cv` は runner 用に optional keyword（`n_folds`, `seed`, `max_folds`, `num_boost_round`, `log_run_id` 等）を追加している。

## GCP 境界

- GCS: raw data staging と run_id artifact storage
- Artifact Registry: 学習 image
- Vertex Custom Job: full training / sweep jobs
- Vertex Hyperparameter Tuning: Vizier HPO
- Vertex Model Registry: run モデルの版管理 / lineage（`make register-model`。serving は未配線）
- Vertex Pipelines (KFP): `train` → `register` の DAG（`make pipeline`。compile 検証済み、実 run は image 再 push が前提）
- Vertex Batch Prediction: 推論コンテナ（`infra/Dockerfile.serving`）で登録したモデルにバッチ推論（`make batch-predict`。推論器はローカル Docker 実証済み、実 job は serving image push が前提）
- Vertex Endpoint: servable モデルのオンライン推論（`make endpoint-deploy` / `endpoint-teardown`）。⚠️常駐コストのため**コードのみ実装・自動デプロイしない**設計
- BigQuery: experiments / cost_estimates
- Cloud Billing Budget: 実請求ガードレール

Custom Job / HP Tuning / Model Registry / Pipelines / Batch Prediction / Endpoint(deploy コード) まで実装済み。Endpoint の実デプロイと Monitoring は常駐コスト・稼働 Endpoint 前提のため意図的に未実行（ADR 0002 の「邪魔なら最初に削る」側。Kaggle ブロンズでは基本不要）。推論コンテナは Batch / Endpoint 共用。

## 境界・注意

- `data/`, `outputs/`, `submission.csv`, DB ファイルは gitignore。
- `data/` は Docker image に入れない。Vertex では `make stage-data` → `--input-uri` で取得する。
- Kaggle token は Vertex に持ち込まない。提出は local の Kaggle CLI で行う。
- `runner.experiment.train` の config runner は現状 LightGBM のみ対応。CatBoost / XGBoost を config runner で使うには追加実装が必要。
