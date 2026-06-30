# California Housing（パイプライン検証用）

> 目的: Kaggle コンペ参加前のパイプライン動作確認  
> データソース: `sklearn.datasets.fetch_california_housing()`  
> 評価指標: RMSE  
> タスク種別: regression

Kaggle コンペではなく練習用データセット。`data/raw/` への CSV ダウンロードは不要。`load_data()` が自動でロードする。

## データ概要

| 項目 | 内容 |
|---|---|
| 学習行数 | 20,640 |
| 特徴量数 | 8 |
| 目的変数 | MedHouseVal（中央住宅価格、$100K 単位） |
| 欠損 | なし |
| カテゴリ列 | なし |

## env/config.yaml 設定

```yaml
target: "MedHouseVal"
id_col: ~
objective: regression
metric: rmse
n_folds: 5
seed: 42
```

## EDA メモ

- 目的変数 `MedHouseVal` は右歪み。外れ値（$500K キャップ）が存在する。
- `MedInc`（中央世帯収入）が最も目的変数と相関が高い。
- 緯度・経度列（`Latitude`, `Longitude`）は地理クラスター FE の候補。
- 欠損なし・カテゴリなしのためベースライン検証に最適。

## 実験記録

| run_id | モデル | CV Score (RMSE) | 変更内容 | 備考 |
|---|---|---|---|---|
| `20260615_*_lgbm_*` | LightGBM | 0.44498 | ベースライン | パイプライン初回検証 |
| `20260615_*_cat_*` | CatBoost | 0.44448 | ベースライン | catboost ベースライン |

`make logs` で最新の run_id を確認できる。

## 特徴量エンジニアリング試行

| ファイル | 関数 | 結果 (CV) | 採用 |
|---|---|---|---|
| — | — | — | ベースライン未実施 |

FE アイデア候補:
- `Latitude × Longitude` の格子セル（地域クラスター）
- `RoomsPerHousehold = AveRooms / AveOccup`
- `BedroomsPerRoom = AveBedrms / AveRooms`

## 提出記録

Kaggle コンペではないため提出なし。パイプライン動作確認のみ。

## 振り返り

- よかった点: パイプライン全体（ingest → featurize → train → score）を通しで検証できた。LightGBM / CatBoost 両方の切り替えも確認済み。
- 次に試すこと: 実際の Kaggle コンペに移行する（House Prices / Titanic 等）。移行時は `env/config.yaml` を更新し `data/interim/` を削除してから `make run`。
