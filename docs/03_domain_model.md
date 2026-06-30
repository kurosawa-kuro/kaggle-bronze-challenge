# 03 ドメインモデル

## 用語

| 用語 | 意味 |
|---|---|
| Competition | Kaggle コンペ。path / GCS prefix / run_id 成果物の単位 |
| Config | `configs/*.yaml` の実験設定。data / model / cv / seeds / runtime を持つ |
| Target | 目的変数。`data.target` または `env/config.yaml` の `target` |
| Fold | CV の分割単位。regression は KFold、それ以外は StratifiedKFold |
| Seed | CV 分割とモデル乱数の種。full run では `seeds` による seed 平均を行う |
| OOF | Out-of-Fold 予測。CV score と分析に使う |
| CV Score | OOF から計算する主指標。Public LB より優先する |
| Run | 1 回の実験実行。`run_id` で識別する |
| run_id | 成果物・BQ ログ・コストログを JOIN する識別子 |
| Run Artifact | `outputs/runs/<comp>/<run_id>/` と GCS `runs/<comp>/<run_id>/` の成果物一式 |
| Sweep | 複数 config を複数 Vertex Custom Job として並列投入する実験 |
| Tune | Optuna による単一マシン HPO |
| HP Tuning | Vertex Hyperparameter Tuning（Vizier）による managed HPO |
| Cost Estimate | Vertex job の概算コスト。BigQuery `kaggle_ops.cost_estimates` に記録 |
| Submission | Kaggle へ提出する `submission.csv`。通常は run artifact 内のものを使う |

## 実験ライフサイクル

```
新コンペ参加
  │
  ▼
make init COMP=<slug>
  │
  ▼
env/config.yaml / configs/*.yaml を調整
  │
  ▼
make smoke
  │
  ▼
make train-local RUN_ID=<id>
  │
  ├─ outputs/runs/<comp>/<run_id>/ を確認
  └─ BigQuery experiments を確認（make logs）
  │
  ▼
重い実験が必要なら:
  make gcp-bootstrap
  make stage-data
  make build-push
  make train-vertex RUN_ID=<id>
  make collect RUN_ID=<id>
  make cost-record RUN_ID=<id>
  │
  ▼
改善ループ:
  ├─ feature / params を変えて train-local
  ├─ make sweep CONFIGS="..." TAG=<tag>
  ├─ make tune RUN_ID=<id>
  └─ make hp-tune RUN_ID=<id>
  │
  ▼
make submit RUN_ID=<id> MSG=<msg>
```

## Run の状態

| 状態 | 代表コマンド | 成果 |
|---|---|---|
| Planned | config 作成 | `configs/*.yaml` |
| SmokeChecked | `make smoke` | 1 fold 相当の軽量 artifact |
| LocalTrained | `make train-local` | local artifact + BQ experiment |
| Staged | `make stage-data` | GCS raw data |
| Submitted | `make train-vertex` / `make sweep` / `make hp-tune` | Vertex job 作成 |
| Collected | `make collect` | GCS artifact を local に回収 |
| CostRecorded | `make cost-record` | BigQuery cost estimate |
| SubmittedToKaggle | `make submit` | Kaggle submission |

## CV と提出の関係

```
CV Score（主指標）
  ├─ CV 最良 run_id
  └─ Public LB 良好 run_id
        │
        ▼
Kaggle で最終提出候補を選択
        │
        ▼
Private LB で最終順位確定
```

- Public LB に引きずられない。まず CV を見る。
- Public LB と CV が大きく乖離する場合はリーク、分布差、過学習を疑う。
- seed 平均は full run の安定化策。smoke では `cv.seed` 単発。

## 実験ログと成果物の責務

| 対象 | 正本 | 目的 |
|---|---|---|
| config / oof / prediction / submission / log | run artifact（local + GCS） | 再現・提出・分析 |
| cv_score / params / notes | BigQuery `<bqDataset>.experiments` | 横断比較 |
| job cost | BigQuery `kaggle_ops.cost_estimates` | run_id 単位の費用把握 |

## 関連タスク

- 新しい状態・用語・ルールは task に背景を残してから反映する。
- 未実装の構想はこの文書で実装済み用語として扱わない。
