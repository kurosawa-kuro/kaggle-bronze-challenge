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

# 学習 image を Artifact Registry へ push
make gcp-bootstrap
make build-push

# Vertex Custom Job へ投入
make train-vertex CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm

# GCS の成果物を outputs/runs/ に回収
make collect CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001_lgbm
```

GCP 設定は `conf/project.yaml` の `gcpProject` / `gcpRegion` / `gcsBucket` / Artifact Registry 項目に置く。ローカル投入は ADC、Vertex コンテナ内はアタッチされた Service Account を使う。

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
