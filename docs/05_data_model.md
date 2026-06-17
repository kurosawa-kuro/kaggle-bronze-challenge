# 05 データモデル

## 設定

| ファイル | 種別 | 内容 |
|---|---|---|
| `conf/config.yaml` | 非機密設定 | COMP / TARGET / OBJECTIVE / METRIC / N_FOLDS / SEED |
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

experiments_db: "data/experiments.db"  # 全コンペ共通
```

データパス（`data_raw` 等）は `src/config.py` が `comp` から自動導出するため config.yaml への記載不要。

## データレイヤー（Databricks Medallion）

コンペごとに `data/<comp>/` 以下に分離して保持する。再ダウンロード不要でコンペを切り替えられる。

| レイヤー | パス | 形式 | 内容 | gitignore |
|---|---|---|---|---|
| **Bronze** | `data/<comp>/raw/train.csv` | CSV | Kaggle 生データ（学習） | ✅ |
| **Bronze** | `data/<comp>/raw/test.csv` | CSV | Kaggle 生データ（テスト） | ✅ |
| **Silver** | `data/<comp>/interim/train.parquet` | Parquet | null 埋め・エンコード済み学習データ | ✅ |
| **Silver** | `data/<comp>/interim/test.parquet` | Parquet | null 埋め・エンコード済みテストデータ | ✅ |
| **Gold** | `data/<comp>/features/` | Parquet | 特徴量エンジニアリング済みデータ（将来利用） | ✅ |
| — | `data/experiments.db` | SQLite | 実験ログ（全コンペ共通） | ✅ |
| — | `submission.csv` | CSV | Kaggle 提出ファイル | ✅ |

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
import duckdb, sqlite3, pandas as pd
conn = sqlite3.connect("data/experiments.db")
df = pd.read_sql("SELECT * FROM experiments ORDER BY timestamp DESC", conn)
duckdb.sql("SELECT run_id, cv_score, notes FROM df ORDER BY cv_score")
# または make logs で直近 10 件を表示
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
