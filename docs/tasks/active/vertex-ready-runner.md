# Vertex-ready 実験ランナーの実装

## Goal

同一 `train.py` を local / Vertex Custom Job で実行し、同一の run_id 成果物
（`outputs/runs/{competition}/{run_id}/`）を出す実験契約を実体化する。
決定は `docs/adr/0001-vertex-ready-experiment-runner.md`、契約は `docs/02_architecture.md`「実行モデル」。

## Context

ローカル単機では 5fold / CatBoost / seed 平均 / 複数 config 並列 / overnight が詰まる。
最初から Vertex 前提で組む。GCP は Custom Job + GCS + Artifact Registry に絞る
（Feature Store / Pipelines 本格運用 / Endpoint / Model Registry / Monitoring は使わない）。

破綻条件は「投入までが面倒になること」。CLI を 1 コマンドに保つことを品質ゲートにする。

## Scope

含む:
- `run.py` → config 駆動の `train.py`（`--config`）への移行。local / Vertex 共通、Vertex を知らない純粋学習コード
- run_id 成果物契約の生成（config snapshot / metrics.json / oof.parquet / test_pred.parquet / feature_importance.csv / submission.csv / log.txt）
- `vertex_run.py`（Custom Job 投入のみ）/ `collect.py`（GCS 回収）/ `submit.py`（整形＋提出）
- `configs/*.yaml`（`model` / `cv` / `seeds` / `runtime`）
- Makefile: `smoke` / `train-local` / `train-vertex` / `collect` / `submit`
- 学習コンテナ（Artifact Registry）と GCS バケットレイアウト `gs://<bucket>/runs/{competition}/{run_id}/`
- 連動ドキュメント更新: `04_workflows.md`（新コマンド）, `05_data_model.md`（config スキーマ / run_id レイアウト）, `CLAUDE.md` コマンド表

含まない:
- Vertex Pipelines / Endpoint / Model Registry / Monitoring / Feature Store

## Skeleton

ビジネスロジックを入れる前に、空シグネチャ + 成果物パス生成だけで配線を固定する
（`.claude/skills/skeleton-first` 準拠）:
- `train.py --config` がダミー成果物を `outputs/runs/{comp}/{run_id}/` に書く
- `vertex_run.py` が `make train-local` と同じ引数面で Custom Job を組み立てる（dry-run 可）
- `collect.py` が `gs://.../runs/{comp}/{run_id}/` ↔ `outputs/runs/...` を 1:1 で対応づける

## Plan

未確定の設計判断（着手前に決める）:
- [ ] config スキーマ: 現行 flat（comp/target/...）に `model`/`cv`/`seeds`/`runtime` を足すか、ネスト構成へ移すか
- [ ] `run_id` 採番規則（timestamp 不可の制約あり → コマンド側で採番して引数で渡す）
- [ ] SQLite ログと run_id 成果物の責務分担（横断インデックス vs 正本実体）の確定
- [ ] GCS バケット名・リージョン・Artifact Registry リポジトリ名の決定（secret / project 設定の置き場所）
- [ ] Doppler 経由の GCP 認証マッピング（Kaggle トークンと同じ要領）

実装順:
- [ ] skeleton 配線（上記）
- [ ] `train.py` を local full で緑にする（既存 pipelines/models を再利用、挙動を変えない）
- [ ] run_id 成果物の生成
- [ ] `make smoke` / `train-local`
- [ ] 学習コンテナ + Artifact Registry push
- [ ] `vertex_run.py` + `make train-vertex`（最小 Custom Job で 1 run）
- [ ] `collect.py` + `make collect`
- [ ] `submit.py` + `make submit` 経路の整理
- [ ] 連動ドキュメント更新

## Acceptance Criteria

- `make smoke CONFIG=...` が 1fold をローカルで実行し成果物を出す
- `make train-local CONFIG=...` と `make train-vertex CONFIG=...` が **同一レイアウトの run_id 成果物**を出す
- `make collect RUN_ID=...` が GCS から `outputs/runs/...` を再現する
- 既存 `make run`／既存 CV スコアが回帰しない（または明示的に `train.py` へ移行済み）
- `04_workflows.md` / `05_data_model.md` / `CLAUDE.md` が新コマンドと drift していない

## Verification

- `make smoke CONFIG=configs/lgbm_baseline.yaml`
- `make train-local CONFIG=configs/lgbm_baseline.yaml` → `outputs/runs/<comp>/<run_id>/` を確認
- `make train-vertex CONFIG=configs/catboost_seed_avg.yaml` → Vertex ログ + GCS 成果物
- `make collect RUN_ID=latest` → ローカルと一致

## Notes

- 推測でコードを書かない。コマンドは実際に実行して確認する（CLAUDE.md）。
- GCP コストは「豪華にしない」。Kaggle 実験を 1 コマンドで外に投げられる状態だけを守る。
