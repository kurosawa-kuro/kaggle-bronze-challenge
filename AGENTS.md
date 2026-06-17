# AGENTS.md

AI コーディングエージェント共通の作業ガイド。

## プロジェクト概要

- **目的**: Kaggle 表形式コンペでブロンズメダルを安定取得する
- **主要技術**: Python 3.12 / LightGBM / CatBoost / XGBoost / scikit-learn / SQLite / DuckDB
- **実行環境**: WSL Ubuntu / uv 仮想環境

## セットアップ / 主要コマンド

```bash
make setup              # uv venv + 依存インストール
make run                # 現在の実験実行 (run.py)
make exp EXP=<名前>     # 特定の実験を実行
make logs               # 実験ログ表示
make clean              # 生成物削除
```

## ディレクトリ規約

| パス | 役割 |
|------|------|
| `src/models/` | モデルごとに 1 ファイル。全て `train_cv()` シグネチャを統一する |
| `src/features/` | FE アイデアごとに 1 ファイル。既存ファイルを変更せず追加する |
| `src/preprocess.py` | `load_data()` と `_encode()` のみ持つ。FE は持たない |
| `experiments/` | 1 実験 = 1 ファイル。再実行可能な形で保存する |
| `env/config.yaml` | コンペ切り替え時に変える唯一のファイル |
| `data/raw/` | Kaggle 生データ（gitignore） |
| `data/interim/` | 前処理済み parquet（gitignore） |
| `data/experiments.db` | 実験ログ SQLite（gitignore） |

## コーディング規約

- 新モデルを追加するときは `src/models/` に新ファイルを作り、`train_cv()` シグネチャを合わせる
- 新 FE を追加するときは `src/features/` に新ファイルを作り、`add_*(X) -> pd.DataFrame` を export する
- 既存ファイルへの副作用を持ち込まない
- Port/Adapter・strict 型注釈・本番 MLOps 水準の設計は持ち込まない
- LLM / RAG / Deep Learning のコードは追加しない

## ドキュメント

設計・仕様・運用は `docs/` 配下を参照。更新規約と権威順位は `docs/00_index.md` に従う。
