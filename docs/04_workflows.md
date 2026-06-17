# 04 ワークフロー

## セットアップ

```bash
make setup    # uv venv 作成 + 依存インストール（初回のみ）
make run      # California Housing で動作確認
```

## 新コンペ参加フロー

```bash
# 1. env/config.yaml を更新（TARGET / ID_COL / OBJECTIVE / METRIC）
# 2. data/raw/ にコンペのデータを配置
# 3. 古いキャッシュを削除
rm -rf data/interim/

# 4. ベースラインを実行
make run
```

## 実験フロー（日常）

```bash
# 現在の実験を実行
make run

# 特定の実験を実行（履歴を再実行したいとき）
make exp EXP=exp001_lgbm_base
make exp EXP=exp002_catboost_base

# 実験ログを確認
make logs
```

## モデルを切り替える

`run.py` の import を 1 行変えるだけ:

```python
# LightGBM → CatBoost に切り替え
from models.catboost_ import train_cv
```

試した実験は `experiments/` にコピーして保存する:

```bash
cp run.py experiments/exp002_catboost_base.py
```

## 特徴量を追加する

```bash
# 1. src/features/ に新ファイルを作る（既存ファイルは変更しない）
touch src/features/ratios.py

# 2. add_*() 関数を実装する

# 3. run.py に追加する
# X_train = add_ratio_features(X_train)
# X_test  = add_ratio_features(X_test)

# 4. 実行して CV スコアを比較
make run
```

## アンサンブル実験

```bash
make exp EXP=exp003_ensemble_lgbm_cat
```

## 最終提出前チェック

```bash
make run           # CV スコアを最終確認
make logs          # 実験一覧を確認し最良 run_id を特定
ls submission.csv  # 提出ファイルを確認
```

## 作業終了

- 実験の観察・考察は `docs/tasks/active/` の task の `Notes` に残す。
- 確定した知見（FE パターン等）は `docs/tasks/active/` から `docs/` 本体へ昇格する。
- 実験ファイルは `experiments/` に保存して再現可能な状態を維持する。
