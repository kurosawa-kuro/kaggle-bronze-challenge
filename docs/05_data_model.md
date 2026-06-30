# 05 データモデル

## 設定

| ファイル | 種別 | 内容 |
|---|---|---|
| `conf/config.yaml` | 非機密設定 | COMP / TARGET / OBJECTIVE / METRIC / N_FOLDS / SEED |
| `configs/*.yaml` | 実験設定 | data / model / cv / runtime を含む `train.py --config` 用設定 |
| `conf/project.yaml` | ローカル project 設定 | repoRoot と GCP project / region / bucket / image 設定 |
| `conf/secret.yaml` | ローカル秘密情報 | gitignore。Kaggle API トークン等 |

### conf/config.yaml スキーマ

```yaml
comp: "titanic"                 # コンペ識別子。パスに使用: data/<comp>/raw/ など
target: "Survived"              # 目的変数列名
id_col: "PassengerId"           # ID 列名（なければ null）
objective: "binary"             # regression / binary / multiclass
metric: "auc"                   # rmse / auc / logloss / mape

n_folds: 5
seed: 42
```

> 実験ログは BigQuery `<bqDataset>.experiments` に統一（ADR 0002）。旧 `experiments_db`（SQLite）設定は廃止。

データパス（`data_raw` 等）は `src/config.py` が `comp` から自動導出するため config.yaml への記載不要。

### configs/*.yaml スキーマ

```yaml
data:
  comp: "titanic"
  target: "Survived"
  id_col: "PassengerId"
  objective: "binary"
  metric: "auc"

model:
  name: "lgbm"
  params:
    learning_rate: 0.05
    num_leaves: 63

cv:
  n_folds: 5
  seed: 42

runtime:
  output_root: "outputs/runs"
  num_boost_round: 2000
  early_stopping_rounds: 50
  smoke_n_folds: 2
  smoke_max_folds: 1
  smoke_num_boost_round: 20
```

`src/config.py` は旧 `conf/config.yaml` の flat schema と、新しい `configs/*.yaml` の nested schema の両方を読む。`train.py` は `KBC_CONFIG_PATH` を設定してから既存 pipeline/model を import する。

## データレイヤー（Databricks Medallion）

コンペごとに `data/<comp>/` 以下に分離して保持する。再ダウンロード不要でコンペを切り替えられる。

| レイヤー | パス | 形式 | 内容 | gitignore |
|---|---|---|---|---|
| **Bronze** | `data/<comp>/raw/train.csv` | CSV | Kaggle 生データ（学習） | ✅ |
| **Bronze** | `data/<comp>/raw/test.csv` | CSV | Kaggle 生データ（テスト） | ✅ |
| **Silver** | `data/<comp>/interim/train.parquet` | Parquet | null 埋め・エンコード済み学習データ | ✅ |
| **Silver** | `data/<comp>/interim/test.parquet` | Parquet | null 埋め・エンコード済みテストデータ | ✅ |
| **Gold** | `data/<comp>/features/` | Parquet | 特徴量エンジニアリング済みデータ（将来利用） | ✅ |
| — | BigQuery `<bqDataset>.experiments` | BQ テーブル | 実験ログ（全コンペ共通、run_id で cost_estimates と JOIN 可） | — |
| — | `submission.csv` | CSV | Kaggle 提出ファイル | ✅ |
| — | `outputs/runs/<comp>/<run_id>/` | mixed | run_id 成果物一式 | ✅ |

## run_id 成果物

local / Vertex Custom Job ともに同じレイアウトを正本とする。

```
outputs/runs/<competition>/<run_id>/
  config.yaml
  metrics.json
  oof.parquet
  test_pred.parquet
  feature_importance.csv
  submission.csv
  log.txt
```

Vertex 実行時は同じ内容を `gs://<bucket>/runs/<competition>/<run_id>/` に upload し、`collect.py` がローカルの `outputs/runs/` へ 1:1 で再現する。

## 実験ログ（BigQuery）

BigQuery `<bqDataset>.experiments`（`conf/project.yaml` の `bqDataset`、既定 `kaggle_ops`）。
`src/utils/logger.py` が初回 `CREATE TABLE IF NOT EXISTS` で自動作成し、`log_run()` で 1 run = 1 行を記録する。
`gcpProject` 未設定 / オフライン時は no-op（ローカル smoke を止めない）。

```sql
CREATE TABLE IF NOT EXISTS kaggle_ops.experiments (
    run_id      STRING,      -- 例: 20260617_025414_lgbm_710b
    recorded_at TIMESTAMP,   -- UTC
    cv_score    FLOAT64,     -- 小さいほど良い (rmse) or 大きいほど良い (auc)
    metric      STRING,      -- rmse / auc / logloss / mape
    competition STRING,      -- comp slug
    params      STRING,      -- JSON 形式のハイパラ
    notes       STRING,      -- 実験メモ
    source      STRING       -- 記録経路（例: cv）
);
```

run_id でコスト概算と JOIN（「このスコアを出した実験は ¥いくら使ったか」）:

```sql
SELECT e.run_id, e.cv_score, ROUND(SUM(c.est_jpy), 1) AS est_jpy
FROM kaggle_ops.experiments e
LEFT JOIN kaggle_ops.cost_estimates c USING (run_id)
GROUP BY e.run_id, e.cv_score
ORDER BY e.cv_score;
-- または make logs で直近 10 件を表示
```

## 前処理・エンコーディング規約（pipelines/ingest.py）

- **数値列の null**: 学習データの中央値で埋める（テストにも同じ値を使う）
- **カテゴリ列の null**: `"__missing__"` で埋める
- **カテゴリエンコーディング**: OrdinalEncoder（`handle_unknown="use_encoded_value"`, `unknown_value=-1`）
- **fit は学習データのみ**: テストデータへの情報リークを防ぐ
- 実装: `src/pipelines/ingest.encode()`

## 関連タスク

- スキーマ変更・前処理の変更は task に目的・移行手順・検証方法を残す。
- 新コンペへの転用時は `conf/config.yaml` を更新し `data/interim/` と `data/features/` を削除してから `make run` を実行する。
- Vertex-ready runner では `configs/*.yaml` を増やして `make smoke` → `make train-local` → `make train-vertex` の順に確認する。
