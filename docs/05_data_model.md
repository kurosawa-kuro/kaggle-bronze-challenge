# 05 データモデル

## 設定

| ファイル | 種別 | 内容 |
|---|---|---|
| `env/config.yaml` | 非機密設定 | TARGET / OBJECTIVE / METRIC / N_FOLDS / SEED / パス |
| `env/secret.yaml` | ローカル秘密情報 | gitignore。Kaggle API トークン等 |

### env/config.yaml スキーマ

```yaml
target: "MedHouseVal"       # 目的変数列名
id_col: ~                   # ID 列名（なければ null）
objective: "regression"     # regression / binary / multiclass
metric: "rmse"              # rmse / auc / logloss / mape

n_folds: 5
seed: 42

data_raw: "data/raw"
data_interim: "data/interim"
experiments_db: "data/experiments.db"
```

## データファイル

| パス | 形式 | 説明 | gitignore |
|---|---|---|---|
| `data/raw/train.csv` | CSV | Kaggle 生データ（学習） | ✅ |
| `data/raw/test.csv` | CSV | Kaggle 生データ（テスト） | ✅ |
| `data/interim/train.parquet` | Parquet | 前処理済み学習データ | ✅ |
| `data/interim/test.parquet` | Parquet | 前処理済みテストデータ | ✅ |
| `data/experiments.db` | SQLite | 実験ログ | ✅ |
| `submission.csv` | CSV | Kaggle 提出ファイル | ✅ |

## 実験ログ（SQLite）

`data/experiments.db` の `experiments` テーブル:

```sql
CREATE TABLE experiments (
    run_id    TEXT PRIMARY KEY,   -- 例: 20260617_025414_lgbm_710b
    timestamp TEXT,               -- ISO 8601 UTC
    cv_score  REAL,               -- 小さいほど良い (rmse) or 大きいほど良い (auc)
    params    TEXT,               -- JSON 形式のハイパラ
    notes     TEXT                -- 実験メモ (例: "exp001: lgbm baseline")
);
```

DuckDB で集計する例:

```python
import duckdb
duckdb.sql("SELECT run_id, cv_score, notes FROM read_csv('data/experiments.db')")
# または make logs で表示
```

## 前処理・エンコーディング規約

- **数値列の null**: 学習データの中央値で埋める（テストにも同じ値を使う）
- **カテゴリ列の null**: `"__missing__"` で埋める
- **カテゴリエンコーディング**: OrdinalEncoder（`handle_unknown="use_encoded_value"`, `unknown_value=-1`）
- **fit は学習データのみ**: テストデータへの情報リークを防ぐ

## 関連タスク

- スキーマ変更・前処理の変更は task に目的・移行手順・検証方法を残す。
- 新コンペへの転用時は `env/config.yaml` を更新し `data/interim/` を削除してから `make run` を実行する。
