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
make setup                        # uv venv 作成 + 依存インストール
make init COMP=<slug>             # 新コンペ初期化（download→正規化→config下書き→doc生成）
make run                          # 現在の実験を実行 (run.py)
make nb NB=<名前>                 # 特定のノートブックを実行 (notebooks/<名前>.py)
make logs                         # SQLite の実験ログを表示
make download COMP=<slug>         # データのみダウンロード（zip展開なし）
make submit COMP=<slug> MSG=<msg> # Kaggle へ提出
make clean                        # submission.csv と __pycache__ を削除
```

## アーキテクチャ（Databricks パターン準拠）

```
scripts/
  init_competition.py   ← make init の実体（download→正規化→分析→doc生成）
conf/config.yaml        ← コンペ切り替え時はここだけ変える
src/
  pipelines/
    ingest.py           ← Bronze→Silver: データロード + エンコーディング
    featurize.py        ← Silver→Gold: 特徴量エンジニアリング
    evaluate.py         ← cv_score() 全モデル共用
    score.py            ← 推論・submission.csv 生成
  models/               ← lgbm / catboost_ / xgboost_ / ensemble（同一シグネチャ）
  features/             ← add_*() FE 関数群（新アイデアはここにファイル追加）
  utils/logger.py       ← SQLite 実験ログ
  config.py             ← conf/config.yaml を定数化
  ports.py              ← ModelTrainer / FeatureTransformer Protocol
notebooks/              ← 実験スクリプト（1実験=1ファイル）
data/
  <comp>/               ← コンペごとに分離（例: data/titanic/）
    raw/                ← Bronze layer（Kaggle 生データ）
    interim/            ← Silver layer（前処理済み parquet）
    features/           ← Gold layer（特徴量 parquet）
  experiments.db        ← 全コンペ共通
```

## 作業ルール

- 推測でコードを書かない。コマンドを書いたら実際に実行して確認する。
- 仕様変更は連動する `docs/` を同じタイミングで直す。drift を作らない。
- 既存の関数・ユーティリティ・パターンを優先的に再利用する。
- `make run` が通ることが最低品質ゲート。
- Port/Adapter・型安全・本番 MLOps 水準の設計は持ち込まない。ノートブックファーストで速く回す。
- LLM / RAG / Deep Learning の提案はしない。LightGBM 主軸で解く。
