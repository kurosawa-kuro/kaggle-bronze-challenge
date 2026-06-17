# kaggle-bronze-challenge

Kaggle コンペティションでブロンズメダルを安定して取るための  
LightGBM 主軸・表形式データ特化パイプライン。

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| 言語 | Python 3.12 |
| 主モデル | LightGBM / CatBoost / XGBoost |
| フレームワーク | scikit-learn |
| 実験管理 | SQLite (`data/experiments.db`) |
| 分析 | DuckDB |
| 仮想環境 | uv |
| 実行環境 | WSL Ubuntu |

## セットアップ

```bash
make setup    # uv venv 作成 + 依存インストール
make run      # 現在の実験を実行 (run.py)
make logs     # 実験ログを表示
```

## 実験の回し方

```bash
# モデルを変えるとき → run.py の import 1行を変える
# from models.lgbm import train_cv
# from models.catboost_ import train_cv   ← これに変える

make run

# 特定の実験を再実行
make exp EXP=exp002_catboost_base
```

## コンペ切り替え

`env/config.yaml` の 3 行だけ変える:

```yaml
target: "SalePrice"     # 目的変数名
id_col: "Id"            # ID 列名（なければ null）
objective: "regression" # regression / binary / multiclass
metric: "rmse"          # rmse / auc / logloss
```

次に `data/interim/` を削除し `data/raw/` に新しいデータを置いて `make run`。

## ディレクトリ構成

```
src/
  config.py          ← env/config.yaml を定数化
  preprocess.py      ← load_data() + _encode()
  metrics.py         ← cv_score() 全モデル共用
  logger.py          ← SQLite に実験結果を記録
  predict.py         ← submission.csv 生成
  models/
    lgbm.py          ← LightGBM  train_cv()
    catboost_.py     ← CatBoost  train_cv()
    xgboost_.py      ← XGBoost   train_cv()
    ensemble.py      ← average()
  features/
    base.py          ← ベースライン特徴量
    (追加FEはここにファイルを足す)
experiments/
  exp001_lgbm_base.py
  exp002_catboost_base.py
  exp003_ensemble_lgbm_cat.py
run.py               ← 現在の実験
env/
  config.yaml        ← データセット設定（非機密）
data/
  raw/               ← Kaggle 生データ（gitignore）
  interim/           ← 前処理済み parquet（gitignore）
  experiments.db     ← 実験ログ SQLite（gitignore）
```

## ドキュメント

詳細は [`docs/00_index.md`](docs/00_index.md) を参照。
