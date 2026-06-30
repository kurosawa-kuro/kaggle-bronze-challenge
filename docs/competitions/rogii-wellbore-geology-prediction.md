# rogii-wellbore-geology-prediction

> コピー元: `docs/competitions/_template.md`  
> Kaggle URL: https://www.kaggle.com/competitions/rogii-wellbore-geology-prediction  
> 参加期限:  
> 評価指標:  
> タスク種別: regression / binary / multiclass

## データ概要

| 項目 | 内容 |
|---|---|
| 学習行数 |  |
| テスト行数 |  |
| 特徴量数 |  |
| 目的変数 |  |
| 欠損の多い列 |  |
| カテゴリ列 |  |

## env/config.yaml 設定

```yaml
target: ""
id_col: ~
objective: regression   # regression / binary / multiclass
metric: rmse            # rmse / auc / logloss
n_folds: 5
seed: 42
```

## EDA メモ

- 目的変数の分布: （歪み・外れ値・対数変換の要否）
- 欠損パターン: （MCAR / MAR / MNAR の観察）
- 特徴量と目的変数の相関: （高相関列のメモ）
- リーク候補: （日付列・ID列・将来情報）

## 実験記録

| run_id | モデル | CV Score | 変更内容 | 備考 |
|---|---|---|---|---|
|  |  |  | ベースライン |  |

`make logs` で run_id を確認し、ここへ転記する。

## 特徴量エンジニアリング試行

| ファイル | 関数 | 結果 (CV) | 採用 |
|---|---|---|---|
|  |  |  |  |

FE を追加するたびに上の表を更新する。

## 提出記録

| 日付 | run_id | CV Score | Public LB | 備考 |
|---|---|---|---|---|
|  |  |  |  | 初提出 |

## 振り返り

- よかった点:
- 次に試すこと:
- 撤退基準: ブロンズ圏外かつ改善の見込みがない場合
