# playground-series-s6e6（Predicting Stellar Class）

> Kaggle URL: https://www.kaggle.com/competitions/playground-series-s6e6
> 参加期限: 2026-06-30
> 評価指標: Accuracy（提出は class 名ラベル）
> タスク種別: multiclass（3クラス: GALAXY / QSO / STAR）

## データ概要

| 項目 | 内容 |
|---|---|
| 学習行数 | 577,347 |
| テスト行数 | 247,435 |
| 特徴量数 | 10（id 除く） |
| 目的変数 | `class`（GALAXY / QSO / STAR） |
| 欠損 | なし |
| カテゴリ列 | `spectral_type`（M, K など）、`galaxy_population`（Red_Sequence など） |
| 参加チーム数 | 1,836（2026-06-17 時点） |

## conf/config.yaml 設定

```yaml
comp: playground-series-s6e6
target: class
id_col: id
objective: multiclass
metric: logloss        # LB は accuracy だが logloss を CV 指標として使用
n_folds: 5
seed: 42
```

## EDA メモ

- 目的変数: 3クラス（GALAXY 多数派、QSO / STAR が少数）
- 欠損なし、カテゴリ2列（OrdinalEncoding 済み）
- `id` 列はシーケンシャル整数 → 特徴量から除外すべき（現在は含まれたまま）
- LB は accuracy 評価だが CV は logloss → 乖離に注意
  - CV logloss 0.09326 → LB accuracy 0.95499 の相関は正常

## 実験記録

| run_id | モデル | CV logloss | LB accuracy | 変更内容 | 備考 |
|---|---|---|---|---|---|
| 20260617_064314_lgbm_a076 | LightGBM | 0.09326 | 0.95499 | ベースライン | id 列を特徴量に含む |

`make logs` で最新 run_id を確認できる。

## 特徴量エンジニアリング試行

| ファイル | 関数 | CV logloss | 採用 |
|---|---|---|---|
| — | ベースライン（FE なし） | 0.09326 | ✅ |

## 提出記録

| 日付 | run_id | CV logloss | LB accuracy | 備考 |
|---|---|---|---|---|
| 2026-06-17 | 20260617_064314_lgbm_a076 | 0.09326 | 0.95499 | 初提出・ベースライン |

## 次の打ち手

優先順位順:

1. **`id` 列を特徴量から除外** → `featurize.py` で ID_COL を drop
2. **Optuna チューニング** → num_leaves / min_child_samples / learning_rate
3. **FE**: `spectral_type` × `galaxy_population` の交差特徴、redshift のビニング
4. **CatBoost アンサンブル** → LightGBM + CatBoost の平均

## 振り返り

- よかった点: 初提出まで1日以内で完了。multiclass 対応がパイプラインに入った。
- 次に試すこと: 上記「次の打ち手」①から順番に。
- 撤退基準: LB accuracy が 0.97 未満かつ改善なし × 3回で撤退検討
