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
make smoke CONFIG=<path>           # train.py --config の短時間確認
make train-local CONFIG=<path> RUN_ID=<id>   # outputs/runs/<comp>/<run_id>/ に成果物生成
make gcp-bootstrap                 # 最小 GCP API / Artifact Registry repo / GCS bucket を作成
make build-push                    # 学習 image を Artifact Registry へ push
make train-vertex CONFIG=<path> RUN_ID=<id>  # Vertex Custom Job へ投入
make collect CONFIG=<path> RUN_ID=<id|latest> # GCS から run_id 成果物回収
make submit CONFIG=<path> RUN_ID=<id> MSG=<msg> # run_id 成果物を Kaggle へ提出
make submit-legacy COMP=<slug> MSG=<msg> # root の submission.csv を Kaggle へ提出
make nb NB=<名前>                 # 特定のノートブックを実行 (notebooks/<名前>.py)
make logs                         # SQLite の実験ログを表示
make download COMP=<slug>         # データのみダウンロード（zip展開なし）
make clean                        # submission.csv と __pycache__ を削除
```

## アーキテクチャ（Databricks パターン準拠）

```
scripts/
  init_competition.py   ← make init の実体（download→正規化→分析→doc生成）
conf/config.yaml        ← コンペ切り替え時はここだけ変える
configs/*.yaml          ← train.py --config 用の実験設定
train.py                ← local / Vertex 共通の config 駆動実験ランナー
vertex_run.py           ← Vertex Custom Job 投入のみ
collect.py              ← GCS の run_id 成果物を outputs/runs/ に回収
submit.py               ← run_id 成果物の submission.csv を Kaggle 提出
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
outputs/
  runs/<comp>/<run_id>/ ← config/metrics/oof/test_pred/feature_importance/submission/log
```

## 作業ルール

- 推測でコードを書かない。コマンドを書いたら実際に実行して確認する。
- 仕様変更は連動する `docs/` を同じタイミングで直す。drift を作らない。
- 既存の関数・ユーティリティ・パターンを優先的に再利用する。
- `make run` が通ることが最低品質ゲート。
- Vertex-ready runner を触る場合は `make smoke CONFIG=configs/lgbm_baseline.yaml` も確認する。
- Port/Adapter・型安全・本番 MLOps 水準の設計は持ち込まない。ノートブックファーストで速く回す。
- LLM / RAG / Deep Learning の提案はしない。LightGBM 主軸で解く。
