# ADR 0001: GCP/Vertex を Kaggle 並列実験ランナーとして最初から前提にする

- Status: Accepted
- Date: 2026-06-30
- Supersedes: `01_requirements.md` 旧記述「本番 MLOps 水準のアーキテクチャ（… Vertex AI 等は使わない）」

## Context

ブロンズ取得の実験スループットがローカル単機で詰まる:

- 5fold 学習が重い
- CatBoost が遅い
- seed 平均を複数回したい
- 複数 config を並列実行したい
- ローカル PC を占有したくない
- overnight で実験を投げたい

後から Vertex 対応を足すより、最初から「Vertex 前提の実験契約」で組む方が安い。
Vertex を **ML 本番基盤**として使うのではなく、**Kaggle ブロンズ用の並列実験ランナー**として使うのが本質。

## Decision

同じ `train.py` を **ローカルでも Vertex でも動かし、同一成果物を出す**ことを契約にする。
Vertex を使うことが目的ではなく、「Vertex に投げてもローカルと同じ run_id 成果物が出る」ことが目的。

### 使う GCP 要素（絞る）

- Vertex AI Custom Job（カスタム学習コードの外部実行）
- GCS（成果物の保存・回収）
- Artifact Registry（学習コンテナ）
- config 別実験 / run_id 管理 / OOF・test_pred・submission 保存

### 使わない

- Feature Store
- Vertex Pipelines の本格運用
- Endpoint
- Model Registry
- Monitoring

### 実行分担

| 環境 | 役割 |
|---|---|
| local | EDA・1fold smoke test・小さい特徴量検証・submission 生成確認 |
| Vertex | 5fold full / CatBoost / seed 平均 / 複数 config 並列 / overnight / OOF・pred・metrics 保存 |
| Kaggle | 最終 Notebook 化・submission 提出・LB 確認 |

### 破綻条件と対策

破綻条件は 1 つ:「Vertex に投げるまでが面倒になること」。
`docker build / push / gcloud ai custom-jobs create / gsutil cp / ログ確認 / run_id どこ` を手で叩く状態は逆に足を引っ張る。

対策として **CLI UX を契約に含める**。1 コマンドで外に投げられる状態を品質ゲートにする:

```
make smoke       CONFIG=configs/lgbm_baseline.yaml       # 1fold ローカル確認
make train-local CONFIG=configs/lgbm_baseline.yaml       # full ローカル
make train-vertex CONFIG=configs/catboost_seed_avg.yaml  # Vertex へ投入
make collect     RUN_ID=latest                           # GCS から成果物回収
make submit      RUN_ID=latest                           # submission 整形・提出
```

### Vertex 固有コードを学習処理に混ぜない

```
train.py        = 純粋な Kaggle 学習（ローカル / Vertex 共通）
vertex_run.py   = Vertex へ投げるだけ
collect.py      = GCS / 成果物回収
submit.py       = submission 整形・提出
```

## Consequences

- `01_requirements.md`: 非対象から Vertex を外し、制約付き対象へ移す。
- `02_architecture.md`: 「実行モデル（Vertex-ready 実験契約）」を追加する。
- 実装は `docs/tasks/active/vertex-ready-runner.md` で追跡する。
- 引き続き持ち込まないもの: Port/Adapter の多層化、本番 MLOps 水準の抽象、Endpoint/Model Registry/Monitoring。
- リスク受容: GCP を豪華にしない。Kaggle 実験を 1 コマンドで外に投げられる状態だけを守る。
