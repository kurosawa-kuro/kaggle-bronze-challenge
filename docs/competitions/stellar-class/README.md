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

## env/config.yaml 設定

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
| 20260617_110427_lgbm_9130 | LightGBM | 0.08763 | 0.95812 | Optuna 40trial best |

`make logs` で全 run_id を確認できる。

## Optuna チューニング結果

**Best CV logloss: 0.08763**（40 trial、num_boost_round=500）

```python
BEST_PARAMS = {
    "num_leaves": 158,
    "min_child_samples": 40,
    "learning_rate": 0.042387,
    "feature_fraction": 0.638674,
    "bagging_fraction": 0.980003,
    "lambda_l1": 1.918585,
    "lambda_l2": 1e-8,
}
```

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

| ファイル | 内容 | CV logloss | 採用 | 結果 |
|---|---|---|---|---|
| — | ベースライン（FE なし） | 0.09326 | ✅ | — |
| `src/features/stellar.py` | 色指数(u-g,g-r,r-i,i-z) + 交差特徴 + redshift ビニング | 0.08833 | ❌ | Optuna params は 10 特徴量向け。16 特徴量になり乖離 |

## CatBoost アンサンブル試行記録

**結論: 未チューニング CatBoost はブレンドに使えない**

| 試行 | OOF logloss | 備考 |
|---|---|---|
| CatBoost デフォルト（1000 iter） | 0.10274 | early stopping 未作動。収束不足 |
| LGBM + CatBoost 50:50 ブレンド | 0.09232 | LGBM 単体（0.08763）より悪化 |

- `catboost_.py` のバグ修正済み: `models.append(model)` 抜けていた
- CatBoost を使うには Optuna チューニングが必須（LGBM と同様）

## 提出記録

| 日付 | CV logloss | LB accuracy | 備考 |
|---|---|---|---|
| 2026-06-17 | 0.09326 | 0.95499 | 初提出・ベースライン |
| 2026-06-17 | 0.09215 | 0.95553 | id 列除外 |
| 2026-06-17 | 0.08763 | **0.95812** | Optuna 40trial best ← **現在ベスト** |

## 現状のパイプライン設定（run.py）

```python
# LGBM Optuna best params（exp003 相当）
BEST_PARAMS = {
    "num_leaves": 158, "min_child_samples": 40,
    "learning_rate": 0.042387, "feature_fraction": 0.638674,
    "bagging_fraction": 0.980003, "lambda_l1": 1.918585, "lambda_l2": 1e-8,
}
```

## 次の打ち手（残課題）

1. ~~`id` 列を特徴量から除外~~ ✅ LB +0.00054
2. ~~Optuna チューニング~~ ✅ LB +0.00259
3. ~~FE 試行（色指数・交差特徴）~~ ❌ Optuna 再チューニングが必要なため中断
4. CatBoost アンサンブル → **Optuna チューニング後でないと逆効果**（2h）
5. ROGII 本命コンペへ移行 ← **推奨**（CAPM 都合）

## 振り返り

- よかった点: 初提出まで1日以内。multiclass・Optuna・CatBoost バグ修正をパイプラインに取り込んだ
- 学んだこと: FE を追加したら Optuna を再チューニングすること。CatBoost はデフォルト params では LGBM に大差で負ける
- 撤退基準: LB accuracy 0.97 未満かつ改善なし × 3回
