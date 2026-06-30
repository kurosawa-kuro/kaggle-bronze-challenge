# ADR 0002: 非DL/GPU の Vertex/GCP マネージド機能をフル活用する

- Status: Accepted
- Date: 2026-06-30
- Supersedes: ADR 0001 の「使わない」節（Feature Store / Vertex Pipelines / Endpoint / Model Registry / Monitoring を不採用とした判断）

## Context

ADR 0001 は Vertex を「並列実験ランナー」に絞り、Registry / Pipelines / Endpoint / Monitoring /
Feature Store を「常駐コスト・運用増だけで実験スループットに寄与しない」として不採用にした。

その後の方針転換: **このリポはフル Vertex 前提で進める**。DL / GPU 系を除く Vertex / GCP の
マネージド機能は最初からフル活用し、運用上邪魔・無駄と判明したものを後で削る（採用してから
削る方向。最初から絞らない）。理由:

- 実験記録・モデル版管理・オーケストレーションを GCP ネイティブに寄せ、ローカル単機 / SQLite
  依存から脱する。
- ライフサイクル（記録 → 登録 → オーケストレーション → 配信 → 監視）を最初から配線しておく方が、
  後付けより安い。

## Decision

### 1. 採用する（非DL/GPU の Vertex/GCP 機能はフル活用）

- Vertex AI Custom Job（学習投入。既存）
- Vertex AI Hyperparameter Tuning / Vizier（既存）
- **Vertex AI Model Registry**（学習済みモデルの版・alias 管理）← 実装済み（`src/runner/register.py` / `make register-model`。`kaggle-<comp>` に版を積む。serving は未配線）
- **Vertex AI Pipelines (KFP)**（ingest → featurize → train → score の DAG 化）
- **Vertex AI Batch Prediction**（バッチ推論）
- Endpoint / Model Monitoring（配信・監視。⚠️常駐コスト系。下記コスト方針で監視し、邪魔なら最初に削る）

### 2. データ/メタデータの正本は BigQuery に統一（infra lib 最小化）

tabular なメタデータ（実験 run・HP trial・sweep 結果・コスト）は **すべて BigQuery
（`kaggle_ops` データセット）に統一**する。理由:

- `costs.py` は既に `bq` CLI サブプロセスで BQ に書いており、**新しい Python infra lib を足さずに**
  実験記録を BQ に寄せられる（`google-cloud-bigquery` すら不要）。
- 既存 `cost_estimates` テーブルが `run_id` 列を持つため、実験スコアとコストを `run_id` で JOIN できる。
- このため **Vertex AI Experiments / ML Metadata は実験トラッキングの正本としては採用しない**。
  BQ がトラッキングを兼ね、costs と JOIN でき、infra を増やさないため（フル Vertex 方針への例外ではなく、
  「BQ 統一」の帰結）。Pipelines を導入し Experiments への自動記録が出た場合は、必要なら BQ への
  小さな exporter を足す。

### 3. infra の床（これ以上は削れない / BQ に入れない）

| 種別 | 置き場 | 理由 |
|---|---|---|
| 全 tabular メタデータ（run / trial / sweep / cost） | **BigQuery**（`kaggle_ops`） | row。run_id で JOIN 可能 |
| モデルバイナリ・oof/preds/submission | **GCS** | BQ は blob ストアではない |
| 学習投入・Vizier HP Tuning | **aiplatform SDK** | BQ は compute API ではない。投入専用に限定 |

### コスト方針

`feedback_gcp_cost_policy` に従う。Endpoint / Feature Store / Monitoring など**常駐コスト系**は当月概算
（`make cost`）で監視し、課金が見えたら最初に削る候補とする。月¥5000 を超える前に相談。

## Consequences

- ADR 0001 は Superseded（「使わない」節を本 ADR が反転）。実験ランナーとしての契約（同一 `train.py` が
  ローカル / Vertex 同一成果物）は維持する。
- `SPEC.md` の Out of scope から Pipelines / Endpoint / Model Registry / Monitoring / Feature Store を外す。
  Ray / 分散 Optuna は引き続きスコープ外（単機 + Vizier で足りる規模のため）。
- `CLAUDE.md` の「本番 MLOps 水準の設計は持ち込まない」を撤回し、「非DL Vertex 機能はフル活用」に置換。
  **DL / GPU / LLM / RAG を持ち込まない方針は維持**（LightGBM 主軸）。
- 実験記録は SQLite (`src/utils/logger.py`) を廃し、BigQuery `kaggle_ops.experiments` へ移す。
