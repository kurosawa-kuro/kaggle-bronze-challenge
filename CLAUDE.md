# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際の最小ガイド。

## Source of Truth

- Project overview: `README.md`
- Documentation index: `docs/00_index.md`
- Requirements: `docs/01_requirements.md`
- Architecture: `docs/02_architecture.md`
- Test strategy: `docs/07_test_strategy.md`
- Task notes: `docs/tasks/`

## コマンド

```bash
make setup              # uv venv 作成 + 依存インストール
make run                # 現在の実験を実行 (run.py)
make exp EXP=<名前>     # 特定の実験を実行 (experiments/<名前>.py)
make logs               # SQLite の実験ログを表示
make clean              # submission.csv と __pycache__ を削除
```

## アーキテクチャ

- 実験エントリポイントは `run.py`。モデルと特徴量の import を変えるだけで切り替わる。
- モデルは `src/models/` 配下（lgbm / catboost_ / xgboost_ / ensemble）。全て同じシグネチャ。
- 特徴量は `src/features/` 配下。新アイデアは新ファイルを追加するだけ。既存ファイルは変更しない。
- データセット設定は `env/config.yaml`。コンペ切り替え時はここだけ変える。
- 実験ログは `data/experiments.db`（SQLite）に自動記録される。

## 作業ルール

- 推測でコードを書かない。コマンドを書いたら実際に実行して確認する。
- 仕様変更は連動する `docs/` を同じタイミングで直す。drift を作らない。
- 既存の関数・ユーティリティ・パターンを優先的に再利用する。
- `make run` が通ることが最低品質ゲート。
- Port/Adapter・型安全・本番 MLOps 水準の設計は持ち込まない。ノートブックファーストで速く回す。
- LLM / RAG / Deep Learning の提案はしない。LightGBM 主軸で解く。
