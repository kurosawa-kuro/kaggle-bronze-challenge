# 04 ワークフロー

## セットアップ

```bash
make setup    # uv venv 作成 + 依存インストール（初回のみ）
make run      # California Housing で動作確認
make smoke CONFIG=configs/lgbm_baseline.yaml  # Vertex-ready runner の短時間確認
```

## 新コンペ参加フロー

```bash
# 1コマンドで: download → ファイル正規化 → config.yaml 下書き表示 → competition doc 生成
make init COMP=<competition-slug>

# → 表示された config.yaml 下書きを conf/config.yaml にコピーして編集
vim conf/config.yaml

# 古いキャッシュを削除してベースラインを実行
rm -rf data/interim/ data/features/ && make run
```

`make init` が行うこと:

| ステップ | 内容 |
|---|---|
| ① download | `data/raw/` にデータを展開 |
| ② 正規化 | バラバラなファイル名を `train.csv` / `test.csv` に統一 |
| ③ 分析 | TARGET 候補・ID 候補・欠損率を表示し `conf/config.yaml` の下書きを提示 |
| ④ doc 生成 | `docs/competitions/<slug>.md` を `_template.md` から作成 |

rules 未同意エラーが出た場合は `https://www.kaggle.com/c/<slug>/rules` でルールに同意してから再実行。

## 実験フロー（日常）

```bash
# 現在の実験を実行
make run

# config 駆動の実験をローカル実行（outputs/runs/<comp>/<run_id>/ に成果物）
make train-local CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# 特定のノートブック実験を再実行（履歴を再実行したいとき）
make nb NB=exp001_lgbm_base
make nb NB=exp002_catboost_base

# 実験ログを確認
make logs
```

## モデルを切り替える

`run.py` の import を 1 行変えるだけ:

```python
# LightGBM → CatBoost に切り替え
from models.catboost_ import train_cv
```

試した実験は `notebooks/` にコピーして保存する:

```bash
cp run.py notebooks/exp002_catboost_base.py
```

## 特徴量を追加する

```bash
# 1. src/features/ に新ファイルを作る（既存ファイルは変更しない）
touch src/features/ratios.py

# 2. add_*() 関数を実装する（X.copy() して返すこと ← FeatureTransformer Protocol）

# 3. run.py に追加する
# from features.ratios import add_ratio_features
# X_train = add_ratio_features(X_train)
# X_test  = add_ratio_features(X_test)

# 4. 実行して CV スコアを比較
make run
```

## アンサンブル実験

```bash
make nb NB=exp003_ensemble_lgbm_cat
```

## Vertex-ready 実験フロー

`train.py --config` は local / Vertex Custom Job 共通の学習入口。学習成果物は同じ run_id レイアウトに保存する。

```bash
# 1 fold だけ短時間で確認
make smoke CONFIG=configs/lgbm_baseline.yaml RUN_ID=smoke_lgbm

# ローカル full run
make train-local CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# 学習 image を Artifact Registry へ push（初回 / コード変更時）
make gcp-bootstrap
make build-push

# コンペデータを GCS へ上げる（初回 / データ更新時）。コンテナは train.py --input-uri で取得する
make stage-data

# Vertex Custom Job へ投入
make train-vertex CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# GCS の成果物を outputs/runs/ に回収
make collect CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# 概算コストを BigQuery に記録 → 当月累計を確認
make cost-record CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
make cost
```

コスト可視化は2層: **予算アラート**（Cloud Billing, ¥5000 予算で ¥1000/¥2500/¥4500/¥5000 通知＝実請求のガードレール）と **概算ロガー**（`make cost-record` が完了ジョブの machine×時間×Spot 割を `kaggle_ops.cost_estimates`(BigQuery) に記録、`make cost` で当月累計を ¥1000/¥5000 と比較）。概算は即時、実請求の真値は Billing Export（後追い）。方針: 月¥1000未満は増強自由・¥5000まで承認・超過前に相談。

GCP 設定は `conf/project.yaml` の `gcpProject` / `gcpRegion` / `gcsBucket` / Artifact Registry 項目に置く。ローカル投入は ADC、Vertex コンテナ内はアタッチされた Service Account を使う。

データ配送: `.dockerignore` で `data/` はイメージに含めない。`make stage-data` で `data/<comp>/raw` を `gs://<bucket>/data/<comp>/raw` へ上げ、コンテナ内 `train.py --input-uri` が起動時に取得する（Kaggle 認証を Vertex に持ち込まない）。`train.py` 変更時はイメージ再 push が必要。

## HPO・並列スイープ（GCP レバレッジ）

```bash
# seed 平均: config の seeds:[42,777,2026] を train.py が横断平均（full run のみ）

# 複数 config を並列 Vertex ジョブに fan-out（非ブロッキング）
make sweep CONFIGS="configs/lgbm_baseline.yaml configs/lgbm_deep.yaml" TAG=exp01

# Optuna 探索（1マシン）→ best_params.json / best_config.yaml / trials.csv
make tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=tune01 N_TRIALS=30
# best で最終学習: make tune ... FINAL=--final（または best_config.yaml を train-local）

# Vertex Hyperparameter Tuning（Vizier 並列探索）
make hp-tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=hpt01 MAX_TRIALS=20 PARALLEL=4
```

- **スケール HPO は Vertex 純正の HP Tuning（Vizier）**で行う。Ray クラスタ / MLflow は使わない（実験トラッキングは BigQuery `kaggle_ops` に統一。ADR 0002）。
- config はイメージにベイクせず base64 でコンテナへ渡す（`train.py --config-b64`）ので、新 config を sweep/hp-tune しても**再ビルド不要**。`train.py` のコード変更時のみ `make build-push`。
- 注意: 並列 HPT を大きいマシン（n2-standard-16）で回すと `custom_model_training_n2_cpus` quota に当たることがある（quota 増申請 or マシン/並列を絞る）。

## 最終提出前チェック

```bash
make run           # CV スコアを最終確認
make logs          # 実験一覧を確認し最良 run_id を特定

# run_id 成果物から提出（既定の提出経路）
make submit CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm MSG="exp001 lgbm baseline"

# 旧 root submission.csv から直接提出する場合
make submit-legacy COMP=<competition-name> MSG="exp001 lgbm baseline cv=0.44498"
```

## 作業終了

- 実験の観察・考察は `docs/tasks/active/` の task の `Notes` に残す。
- 確定した知見（FE パターン等）は `docs/tasks/active/` から `docs/` 本体へ昇格する。
- 実験ファイルは `notebooks/` に保存して再現可能な状態を維持する。
