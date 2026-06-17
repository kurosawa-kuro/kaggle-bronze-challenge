# Predicting Stellar Class（playground-series-s6e6）

> Kaggle URL: https://www.kaggle.com/competitions/playground-series-s6e6
> 参加期限: 2026-06-30
> 評価指標: Accuracy（提出は class 名ラベル）
> タスク種別: multiclass（3クラス: GALAXY / QSO / STAR）
> 用途: **パイプライン練習用**（Playground Series → メダル対象外の可能性あり）

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
- `id` 列はシーケンシャル整数 → 特徴量から除外済み（exp002〜）
- LB は accuracy 評価だが CV は logloss → 乖離に注意
  - CV logloss 0.09326 → LB accuracy 0.95499 の相関は正常

## 実験記録

| run_id | モデル | CV logloss | LB accuracy | 変更内容 |
|---|---|---|---|---|
| 20260617_064314_lgbm_a076 | LightGBM | 0.09326 | 0.95499 | ベースライン（id 列含む） |
| 20260617_071002_lgbm_2684 | LightGBM | 0.09215 | 0.95553 | id 列除外 |
| — | LightGBM | — | — | Optuna チューニング（実行中） |

`make logs` で全 run_id を確認できる。

## Optuna チューニング結果

> 実行中 — 完了後に記録する

探索空間:

| パラメータ | 探索範囲 |
|---|---|
| num_leaves | 31〜255 |
| min_child_samples | 5〜100 |
| learning_rate | 0.01〜0.3（log scale） |
| feature_fraction | 0.5〜1.0 |
| bagging_fraction | 0.5〜1.0 |
| lambda_l1 | 1e-8〜10（log scale） |
| lambda_l2 | 1e-8〜10（log scale） |

## 特徴量エンジニアリング試行

| ファイル | 内容 | CV logloss | 採用 |
|---|---|---|---|
| — | ベースライン（FE なし） | 0.09326 | ✅ |

## 提出記録

| 日付 | CV logloss | LB accuracy | 備考 |
|---|---|---|---|
| 2026-06-17 | 0.09326 | 0.95499 | 初提出・ベースライン |
| 2026-06-17 | 0.09215 | 0.95553 | id 列除外 |

## 次の打ち手

1. ~~`id` 列を特徴量から除外~~ ✅ CV 0.09326 → 0.09215
2. ~~Optuna チューニング~~ ⏳ 実行中
3. FE: `spectral_type` × `galaxy_population` 交差特徴、redshift ビニング
4. CatBoost アンサンブル（LightGBM + CatBoost の平均）

## 振り返り

- よかった点: 初提出まで1日以内で完了。multiclass 対応がパイプラインに入った。
- 撤退基準: LB accuracy が 0.97 未満かつ改善なし × 3回で撤退検討
