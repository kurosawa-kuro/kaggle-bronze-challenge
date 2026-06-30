# 05 データモデル

## 設定ファイル

| ファイル | 内容 |
|---|---|
| `env/config.yaml` | 旧 `make run` と default config 用の flat schema |
| `configs/*.yaml` | `runner.experiment.train` 用の実験 config |
| `env/project.yaml` | repo path、GCP project / region / bucket / image、BQ dataset、コスト設定 |
| `env/secret.yaml` | gitignore。Kaggle token / Discord webhook 等 |

## `env/config.yaml`

flat schema:

```yaml
comp: "titanic"
target: "Survived"
id_col: "PassengerId"
objective: "binary"
metric: "auc"
n_folds: 5
seed: 42
```

`src/config.py` は `KBC_CONFIG_PATH` が未指定ならこのファイルを読む。

## `configs/*.yaml`

nested schema:

```yaml
data:
  comp: "playground-series-s6e6"
  target: "class"
  id_col: "id"
  objective: "multiclass"
  metric: "logloss"

model:
  name: "lgbm"
  params:
    learning_rate: 0.05
    num_leaves: 63

cv:
  n_folds: 5
  seed: 42

seeds: [42, 777, 2026]

runtime:
  output_root: "outputs/runs"
  num_boost_round: 2000
  early_stopping_rounds: 50
  smoke_n_folds: 2
  smoke_max_folds: 1
  smoke_num_boost_round: 20
```

補足:

- `runner.experiment.train` は full run では `seeds` を横断し、OOF / test prediction / feature importance を平均する。
- smoke では `cv.seed` 単発。
- `experiments_db` が残っている config は旧互換の名残で、現行 logger は BigQuery を使う。
- `model.name` は現状 `lgbm` のみ runner 対応。

## `env/project.yaml`

主要キー:

```yaml
gcp:
  project: mlops-dev-a
  account: kurokawa81toshifumi@gmail.com
  region: us-central1
gcpProject: mlops-dev-a
gcpRegion: us-central1
artifactRegistryRepo: kaggle
imageName: kaggle-bronze-challenge
imageTag: latest
imageUri:
gcsBucket: mlops-dev-a-kaggle-bronze-runs
bqDataset: kaggle_ops
jpyPerUsd: 150
vertexMachineType: n2-standard-16
vertexServiceAccount:
```

`imageUri` が空なら `{region}-docker.pkg.dev/{project}/{repo}/{imageName}:{imageTag}` を runner が組み立てる。

## データレイヤー

| レイヤー | パス | 形式 | 内容 | Git |
|---|---|---|---|---|
| Bronze | `data/<comp>/raw/train.csv` | CSV | Kaggle 学習データ | ignore |
| Bronze | `data/<comp>/raw/test.csv` | CSV | Kaggle テストデータ | ignore |
| Silver | `data/<comp>/interim/train.parquet` | Parquet | load cache | ignore |
| Silver | `data/<comp>/interim/test.parquet` | Parquet | load cache | ignore |
| Gold | `data/<comp>/features/` | Parquet | 将来の特徴量 cache | ignore |
| Vertex input | `gs://<bucket>/data/<comp>/raw/` | CSV | Vertex job が取得する raw data | GCS |

`pipelines.ingest.load_data()` は `data/<comp>/interim/*.parquet` があれば優先し、なければ raw CSV、なければ California Housing fallback を使う。

## run_id 成果物

local 正本:

```
outputs/runs/<competition>/<run_id>/
  config.yaml
  metrics.json
  oof.parquet
  test_pred.parquet
  feature_importance.csv
  submission.csv
  log.txt
  model/booster_NNN.txt   # seed×fold の全 booster
  model/manifest.json     # boosters 一覧・推論方法・objective/num_class/feature_names
```

`model/` は `make register-model RUN_ID=<id>` が Vertex Model Registry（`kaggle-<comp>` に版を積む）へ登録する成果物。

Vertex 実行時:

```
gs://<bucket>/runs/<competition>/<run_id>/
  same files
```

`metrics.json` の代表フィールド:

```json
{
  "run_id": "exp001_lgbm",
  "competition": "playground-series-s6e6",
  "model": "lgbm",
  "metric": "logloss",
  "cv_score": 0.08763,
  "seeds": [42, 777, 2026],
  "n_seeds": 3,
  "seed_scores": [{"seed": 42, "cv_score": 0.0879}],
  "n_folds_requested": 5,
  "n_folds_trained": 5,
  "smoke": false,
  "created_at": "2026-06-30T00:00:00+00:00"
}
```

## BigQuery: experiments

Dataset は `env/project.yaml` の `bqDataset`（既定 `kaggle_ops`）。  
`src/utils/logger.py` が `CREATE TABLE IF NOT EXISTS` を実行する。ただし dataset 自体は事前に存在している必要がある。

```sql
CREATE TABLE IF NOT EXISTS kaggle_ops.experiments (
  run_id      STRING,
  recorded_at TIMESTAMP,
  cv_score    FLOAT64,
  metric      STRING,
  competition STRING,
  params      STRING,
  notes       STRING,
  source      STRING
);
```

`log_run()` は BigQuery 記録に失敗しても学習を止めない。

## BigQuery: cost_estimates

`src/runner/costs.py` は現状 `kaggle_ops.cost_estimates` を使う。

主要カラム:

| カラム | 内容 |
|---|---|
| `recorded_at` | 記録時刻 |
| `service` | `aiplatform` 等 |
| `resource_type` | `custom_job` 等 |
| `resource_id` | GCP resource id |
| `detail` | machine type + spot 情報 |
| `region` | GCP region |
| `usage_qty` / `usage_unit` | 使用量。Vertex は hour |
| `unit_price_usd` / `est_usd` / `est_jpy` | 概算単価・費用 |
| `start_time` / `end_time` | job 実行時間 |
| `labels` | purpose / run_id / comp |
| `run_id` / `competition` | JOIN 用 |
| `source` | `estimate` |

## 前処理・エンコーディング

`pipelines.ingest.encode()` の規約:

- 数値列 null は学習データの中央値で埋める
- カテゴリ列 null は `"__missing__"` で埋める
- カテゴリ列は `OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)`
- fit は学習データのみ

`pipelines.featurize.make_features()`:

- `TARGET` を y として分離
- `ID_COL` は X から除外
- 文字列 target は `LabelEncoder` で数値化し、submission 時に元ラベルへ戻す

## Git 管理

Git 管理しない:

- `data/*/`
- `outputs/`
- `submission.csv`
- `*.db`, `*.sqlite*`
- `env/secret.yaml`
- `.venv/`

Git 管理する:

- `configs/*.yaml`
- `docs/`
- `src/`
- `infra/Dockerfile`
- `env/project.yaml`
