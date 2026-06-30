# 01 要件

## 目的

Kaggle の表形式コンペでブロンズメダル圏を狙う。  
LightGBM を主軸に、48 時間以内に初回提出できる実験パイプラインを持ち、重い実験は Vertex AI に逃がして反復速度を落とさない。

## 現在の実装スコープ

### 対象

- 表形式データを扱う Kaggle コンペへの参加・提出
- `make init` による新コンペ初期化
- `pipelines/` と `models/` による前処理 → 学習 → 推論 → 提出ファイル生成
- `src/runner/train.py` による config 駆動の実験実行
- local / Vertex Custom Job で同じ runner を使い、同じ run_id 成果物を出す実験契約
- GCS へのデータ staging と run_id 成果物 upload / collect
- Artifact Registry へ学習コンテナを push し Vertex Custom Job へ投入
- seed 平均、複数 config sweep、Optuna tuning、Vertex Hyperparameter Tuning
- BigQuery `kaggle_ops` への実験ログと概算コスト記録
- 学習済みモデルの Vertex Model Registry 登録（`kaggle-<comp>` に版を積む）
- Vertex Pipelines (KFP) による `train` → `register` の DAG 実行
- 推論コンテナ（`infra/Dockerfile.serving`）と Vertex Batch Prediction
- Vertex Endpoint への deploy / teardown コード（⚠️常駐コストのため実デプロイは手動・任意）
- Kaggle CLI による run_id 成果物からの提出

### 非対象

- 画像・音声・テキスト主体の Deep Learning コンペ
- LLM / RAG を使うアプローチ
- GPU 前提の大規模学習
- Ray / Spark / MLflow サーバなど、ブロンズ狙いに対して運用面が重い基盤
- Google Colab での動作保証
- DI / Composition Root / Adapter 層などの本格アプリケーション設計

### ADR 上の方向性

ADR 0002 で、非 DL/GPU の Vertex/GCP マネージド機能を活用する方針を採用している。  
ただし、**現在コードで実体化済みなのは Custom Job / Hyperparameter Tuning / Model Registry / Pipelines(KFP) / Batch Prediction（推論コンテナ込み）/ GCS / Artifact Registry / BigQuery ログ・コスト記録**である（Pipelines は compile 検証済み・実 run は image 再 push 前提、Batch は推論器をローカル Docker 実証済み・実 job は serving image push 前提）。Endpoint は deploy/teardown コードまで実装済み（dry-run 検証）だが、**常駐コストのため実デプロイはしない**運用。Monitoring は稼働 Endpoint 前提のため未実装（いずれも ADR 0002 の「邪魔なら削る」側）。

## 制約・方針

| 区分 | 内容 |
|---|---|
| 目標水準 | ブロンズ取得。過剰なシルバー・ゴールド狙いの複雑化は避ける |
| モデル選択 | `runner.experiment.train` は現状 LightGBM のみ。CatBoost / XGBoost は既存 `models/` にあるが、config runner への統合は未完 |
| 実験入口 | `PYTHONPATH=src python -m runner.experiment.train --config ...` |
| 旧実験入口 | `make run` は `runner.run` を実行する手動編集型の旧経路 |
| 実験管理 | run_id 成果物を GCS / `outputs/runs/` に保存し、tabular メタデータは BigQuery に記録 |
| コスト管理 | `make cost-record` / `make cost` / `make cost-notify` で概算コストを BigQuery と Discord に連携 |
| 実行環境 | local = smoke / EDA / 小実験、Vertex = full run / seed 平均 / sweep / HPO |
| データ配送 | `data/` は Docker image に含めない。`make stage-data` で GCS に置き、Vertex job が `--input-uri` で取得 |
| UX | `make smoke`, `train-local`, `stage-data`, `train-vertex`, `collect`, `submit` を品質ゲートにする |
| GCP 認証 | ローカルは ADC / gcloud、Vertex 内はアタッチ Service Account |

## 技術スタック

| 領域 | 採用 |
|---|---|
| アルゴリズム | LightGBM 主軸、CatBoost / XGBoost は既存モデル実装あり |
| 前処理 | pandas / scikit-learn `OrdinalEncoder` |
| CV | KFold / StratifiedKFold |
| HPO | Optuna（単一マシン）/ Vertex Hyperparameter Tuning（Vizier） |
| 実験ログ | BigQuery `<bqDataset>.experiments` |
| コストログ | BigQuery `kaggle_ops.cost_estimates` |
| 成果物 | local `outputs/runs/<comp>/<run_id>/` / GCS `gs://<bucket>/runs/<comp>/<run_id>/` |
| コンテナ | `infra/Dockerfile`, `uv pip install`, Artifact Registry |
| CLI | Makefile + `src/runner/*` |
| Kaggle | kaggle CLI。Doppler の `ML_KAGGLE_TOKEN` を `KAGGLE_API_TOKEN` にマッピング |

## ユースケース

| ID | ユースケース | 成功条件 |
|---|---|---|
| UC-001 | 新規コンペを初期化する | `make init COMP=<slug>` で raw data / config 下書き / competition doc が作られる |
| UC-002 | ベースラインをローカルで確認する | `make smoke` が 1 fold 相当の成果物を作る |
| UC-003 | full 実験を再現可能に残す | `make train-local RUN_ID=<id>` が run_id 成果物と BigQuery 実験ログを作る |
| UC-004 | 重い実験を Vertex に投げる | `make stage-data && make build-push && make train-vertex RUN_ID=<id>` で Custom Job が作成される |
| UC-005 | 複数 config を並列で回す | `make sweep CONFIGS="..." TAG=<tag>` が非ブロッキングに複数 Custom Job を投入する |
| UC-006 | HPO を行う | `make tune` または `make hp-tune` で best params / trial 情報を得る |
| UC-007 | コストを確認する | `make cost-record RUN_ID=<id>` 後に `make cost` で当月概算を確認できる |
| UC-008 | 提出する | `make submit CONFIG=<cfg> RUN_ID=<id> MSG=<msg>` が run_id の `submission.csv` を Kaggle に提出する |

## 関連タスク

- 要件追加・変更は `docs/tasks/active/` または `docs/tasks/backlog/` に task として記録する。
- 実装後、確定した要件だけをこの文書へ反映する。
