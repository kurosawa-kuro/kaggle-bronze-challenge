# 04 ワークフロー

## セットアップ

```bash
make setup
make smoke CONFIG=configs/lgbm_baseline.yaml RUN_ID=smoke_check
```

`make run` は旧手動実験経路の確認用。通常の再現可能な実験は `make smoke` / `make train-local` を使う。

## 新コンペ参加フロー

```bash
make init COMP=<competition-slug>
vim env/config.yaml
cp env/config.yaml configs/<competition>_lgbm_baseline.yaml  # 必要に応じて nested schema に整える
rm -rf data/<competition>/interim data/<competition>/features
make smoke CONFIG=configs/<competition>_lgbm_baseline.yaml RUN_ID=smoke01
```

`make init` は Kaggle download、ファイル名正規化、config 下書き表示、competition doc 生成を行う。rules 未同意エラーは Kaggle の rules ページで同意してから再実行する。

## 日常の実験

```bash
# 旧・手動編集型 baseline
make run

# config 駆動 smoke
make smoke CONFIG=configs/lgbm_baseline.yaml RUN_ID=smoke_lgbm

# config 駆動 full local run
make train-local CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# 実験ログ（BigQuery experiments）
make logs
```

`runner.experiment.train` は現状 `model.name: lgbm` のみ対応。CatBoost / XGBoost は `models/` に実装があるが、config runner から切り替える経路はまだない。

## 特徴量を追加する

```bash
touch src/features/ratios.py
```

`add_*()` 関数は `X.copy()` して返す。使う場合は `pipelines/featurize.py` または旧 `runner.run` / notebook 実験に組み込む。試した実験は `notebooks/` へ保存する。

## Vertex-ready 実験

初回または GCP リソース未作成時:

```bash
make gcp-bootstrap
```

`gcp-bootstrap` は Vertex / Artifact Registry / GCS の最小リソースを作る。BigQuery dataset（既定 `kaggle_ops`）は実験ログ・コストログで使うため、未作成なら別途作成しておく。

データ・コードを準備:

```bash
# data/<comp>/raw を GCS へ upload
make stage-data

# src/ や requirements を変えた時だけ image rebuild/push
make build-push
```

Vertex Custom Job へ投入:

```bash
make train-vertex CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
```

既定は Spot。on-demand にしたい場合:

```bash
make train-vertex CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm SPOT=
```

回収とコスト記録:

```bash
make collect CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
make cost-record CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
make cost
```

## 複数 config の並列 sweep

```bash
make sweep CONFIGS="configs/lgbm_baseline.yaml configs/lgbm_deep.yaml" TAG=exp01
```

- 各 config は別 run_id（例: `lgbm_baseline_exp01`）として非ブロッキングに投入される。
- config は base64 で job に渡すため、config 追加だけなら `make build-push` は不要。
- `src/` や依存を変えた場合は image rebuild が必要。

dry-run:

```bash
PYTHONPATH=src .venv/bin/python -m runner.experiment.sweep \
  --configs configs/lgbm_baseline.yaml configs/lgbm_deep.yaml \
  --tag exp01 --image-uri <image> --dry-run
```

## HPO

Optuna（単一マシン）:

```bash
make tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=tune01 N_TRIALS=30
make tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=tune01 N_TRIALS=30 FINAL=--final
```

成果物:

```
outputs/runs/<comp>/<run_id>/
  best_params.json
  best_config.yaml
  trials.csv
```

Vertex Hyperparameter Tuning（Vizier）:

```bash
make hp-tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=hpt01 MAX_TRIALS=20 PARALLEL=4
```

quota に当たる場合は `vertexMachineType` や `PARALLEL` を下げる。

## モデル登録（Vertex Model Registry）

```bash
make register-model CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
```

- `gs://<bucket>/runs/<comp>/<run_id>/model`（train が保存した booster 群）を `kaggle-<comp>` に 1 バージョンとして登録する。
- 同じ `kaggle-<comp>` が既にあれば新バージョンを積み、`latest` alias を最新へ移す。
- serving / Endpoint は未配線。registry は版管理・lineage 目的。

## パイプライン（Vertex Pipelines / KFP）

`train` → `register` を 1 つの DAG として投入する。

```bash
# compile のみ（コスト無し・DAG 検証）
make pipeline CONFIG=configs/lgbm_baseline.yaml RUN_ID=pipe01 DRY=--dry-run

# 実投入（full 学習ジョブが走る。src を変えたら先に make build-push）
make build-push
make pipeline CONFIG=configs/lgbm_baseline.yaml RUN_ID=pipe01
```

- 既存の学習イメージを container component として使うため、新規の component イメージは不要。
- config は base64 でパイプラインパラメータとして渡す（イメージ非依存）。
- ingest/featurize/train/score の細分化はしない（train.py 内で完結。GCS 往復を避ける）。

## バッチ推論（Vertex Batch Prediction）

推論コンテナ（`infra/Dockerfile.serving` = `src/serving/predictor.py`、LightGBM seed-bag 平均）で
登録したモデルにバッチ推論する。

```bash
# 1) 推論イメージを push
make build-push-serving

# 2) 実 serving 付きでモデル登録（version を積み、Batch/Endpoint 可能に）
make register-servable CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# 3) Batch Prediction 投入（instances.jsonl は feature 順の配列を 1 行 1 instance で）
make batch-predict CONFIG=configs/lgbm_baseline.yaml RUN_ID=bp01 \
  SRC=gs://<bucket>/batch_input/instances.jsonl DRY=--dry-run   # まず dry-run
```

- 推論器（`/health` `/predict`）はローカル Docker で実証済み。`make register-servable` 無しの
  プレースホルダ登録モデルは Batch には使えない。
- Endpoint（オンライン）は Batch と推論コンテナを共用する（下記）。

## オンライン推論（Vertex Endpoint）⚠️常駐コスト

```bash
make endpoint-deploy CONFIG=configs/lgbm_baseline.yaml DRY=--dry-run  # まず plan 確認
make endpoint-deploy CONFIG=configs/lgbm_baseline.yaml               # 実デプロイ（24/7 課金開始）
# ... 推論を使ったら必ず ...
make endpoint-teardown CONFIG=configs/lgbm_baseline.yaml             # undeploy + Endpoint 削除
```

- **Endpoint にデプロイされたモデルは 24/7 課金される**（`feedback_gcp_cost_policy`）。Kaggle ブロンズでは基本不要。使うときだけ deploy し、終わったら即 teardown。
- `make register-servable`（実 serving image）済みのモデルが前提。
- Monitoring は稼働 Endpoint 前提のため未実装。

## コスト確認

```bash
make cost-record CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
make cost
make cost-notify
```

- `cost-record` は完了済み Vertex Custom Job の start/end から概算 JPY を算出し、BigQuery `kaggle_ops.cost_estimates` に記録する。
- `cost` は当月概算を ¥1000 watch / ¥5000 相談ラインと並べて表示する。
- Discord webhook は `env/secret.yaml` の `discordWebhookUrl` または `DISCORD_WEBHOOK_URL`。

## 提出

通常経路:

```bash
make submit CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm MSG="exp001 lgbm baseline"
```

旧 root `submission.csv` を直接出す場合:

```bash
make submit-legacy COMP=<competition-slug> MSG="legacy submission"
```

## よく使う確認コマンド

```bash
make -n train-vertex CONFIG=configs/lgbm_baseline.yaml RUN_ID=check
PYTHONPATH=src .venv/bin/python -m runner.experiment.vertex_run --config configs/lgbm_baseline.yaml --run-id check --dry-run
find outputs/runs/<comp>/<run_id> -maxdepth 1 -type f -printf '%f\n' | sort
```

## 作業終了

- 実験の観察・考察は `docs/tasks/active/` の task の Notes に残す。
- 確定した仕様は `docs/` 本体へ反映する。
- 再現したい実験は `configs/` と `notebooks/` に残す。
