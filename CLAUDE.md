# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際の最小ガイド。

## Source of Truth

- Project overview: `README.md`
- Documentation index: `docs/00_index.md`
- Requirements: `docs/01_requirements.md`
- Architecture: `docs/02_architecture.md`
- Test strategy: `docs/07_test_strategy.md`
- Current feature spec: `SPEC.md`（着手前の実装スペック。公式 spec-driven）
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
make stage-data                    # data/<comp>/raw を GCS へ上げる（Vertex 投入の前提）
make train-vertex CONFIG=<path> RUN_ID=<id>  # Vertex Custom Job へ投入（n2-standard-16 + Spot 既定。on-demand は SPOT=）
make sweep CONFIGS="a.yaml b.yaml" TAG=exp01  # 複数 config を並列 Custom Job に fan-out（非ブロッキング）
make tune CONFIG=<path> RUN_ID=<id> N_TRIALS=30  # Optuna 探索（1マシン）→ best_params.json/best_config.yaml
make hp-tune CONFIG=<path> RUN_ID=<id> MAX_TRIALS=20 PARALLEL=4  # Vertex HP Tuning（Vizier 並列探索）
make collect CONFIG=<path> RUN_ID=<id|latest> # GCS から run_id 成果物回収
make register-model CONFIG=<path> RUN_ID=<id> # run_id のモデルを Vertex Model Registry に登録（版＋latest alias）
make pipeline CONFIG=<path> RUN_ID=<id> [DRY=--dry-run] # Vertex Pipelines (KFP) で train→register の DAG を投入（DRY で compile のみ）
make build-push-serving            # 推論コンテナ（infra/Dockerfile.serving）を Artifact Registry へ push
make register-servable CONFIG=<path> RUN_ID=<id> # 実 serving image 付きでモデル登録（Batch/Endpoint 可能に）
make batch-predict CONFIG=<path> RUN_ID=<id> SRC=gs://.../instances.jsonl [DRY=--dry-run] # Vertex Batch Prediction 投入
make endpoint-deploy CONFIG=<path> [DRY=--dry-run]   # ⚠️常駐コスト: servable モデルを Vertex Endpoint へデプロイ
make endpoint-teardown CONFIG=<path> [DRY=--dry-run] # Endpoint を undeploy+削除して常駐コストを止める
make cost-record CONFIG=<path> RUN_ID=<id>  # 完了ジョブの概算コストを BigQuery に記録
make cost                          # 当月の概算コスト累計を表示（¥1000/¥5000 しきい値）
make cost-notify                   # 当月概算サマリを Discord へ送信（webhook は conf/secret.yaml）
make submit CONFIG=<path> RUN_ID=<id> MSG=<msg> # run_id 成果物を Kaggle へ提出
make submit-legacy COMP=<slug> MSG=<msg> # root の submission.csv を Kaggle へ提出
make nb NB=<名前>                 # 特定のノートブックを実行 (notebooks/<名前>.py)
make logs                         # BigQuery (kaggle_ops.experiments) の実験ログを表示
make download COMP=<slug>         # データのみダウンロード（zip展開なし）
make clean                        # submission.csv と __pycache__ を削除
```

## アーキテクチャ

構造・データフロー・モジュール責務・Vertex 実行契約は正本の `docs/02_architecture.md` を参照する。ここには重複させない（コードと Makefile から読めない方針だけを以下に置く）。

## 開発フロー（公式 Explore → Plan → Implement → Commit）

Claude Code 公式の基本ワークフローに従う（出典: code.claude.com/docs/en/best-practices）。

1. **Explore** — plan モードで関連ファイルを読む。先にコードを書かない。
2. **Plan** — 中規模以上の作業は着手前に SPEC を書く。`write-spec` スキルでインタビュー → リポジトリ直下の `SPEC.md` に**自己完結したスペック**（関係するファイル/インターフェースを名指し・スコープ外を明記・末尾に E2E 検証ステップ）を作る。`SPEC.md` は「今着手する1機能」を持ち、完了後は確定内容を `docs/` へ昇格して上書きする。
3. **Implement** — スペックができたら**新しいセッション**で `execute-task` により実行する。
4. **Commit** — 検証が通ってから、説明的なメッセージでコミットする。

例外（公式どおり）: typo・log 追加・変数リネームなどスコープが小さく明確な修正は plan/spec を省いて直接行う。

## 作業ルール

- 推測でコードを書かない。コマンドを書いたら実際に実行して確認する。
- 仕様変更は連動する `docs/` を同じタイミングで直す。drift を作らない。
- 既存の関数・ユーティリティ・パターンを優先的に再利用する。
- `make run` が通ることが最低品質ゲート。
- Vertex-ready runner を触る場合は `make smoke CONFIG=configs/lgbm_baseline.yaml` も確認する。
- 非DL/GPU の Vertex/GCP マネージド機能はフル活用する（ADR 0002）。Model Registry / Pipelines / Batch Prediction / Endpoint 等を採用し、邪魔・無駄と分かったら後で削る。
- tabular メタデータ（実験 run / HP trial / sweep / cost）の正本は **BigQuery `kaggle_ops` に統一**。新しい infra lib を足さない（`bq` CLI 経由）。モデル等 blob は GCS、学習投入は aiplatform SDK。
- 過度な Port/Adapter 多層化は持ち込まない。速く回すことを優先する。
- LLM / RAG / Deep Learning / GPU の提案はしない。LightGBM 主軸で解く。
