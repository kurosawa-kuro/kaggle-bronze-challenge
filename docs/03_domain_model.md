# 03 ドメインモデル

## 用語

| 用語 | 意味 |
|---|---|
| **Competition（コンペ）** | 参加する Kaggle コンペティション。表形式データが対象 |
| **Target** | 予測する目的変数。`env/config.yaml` の `target` で指定 |
| **Fold** | CV（交差検証）の分割単位。デフォルト 5-fold |
| **OOF（Out-of-Fold）** | 各 fold で学習に使わなかったデータへの予測値。全サンプル分を結合したものが CV スコアの計算に使われる |
| **CV Score** | OOF 全体に対するスコア（RMSE / AUC / logloss 等）。Public LB の代理指標として使う |
| **Public LB** | Kaggle が公開するリーダーボード。テストデータの一部（20-30%）で計算される |
| **Private LB** | 締切後に確定するリーダーボード。残りのテストデータで計算。最終順位はこちら |
| **Feature Engineering（FE）** | 特徴量の生成・加工。`src/features/` に 1 アイデア = 1 ファイルで管理 |
| **Baseline** | 最初のシンプルなモデル（生データ + LightGBM）。48h 以内に提出する |
| **Experiment（実験）** | モデル × FE の 1 組み合わせ。`experiments/` に 1 ファイルで保存 |
| **Ensemble** | 複数モデルの予測を結合する。ブロンズ圏では単純平均で十分 |
| **Submission** | Kaggle に提出する予測ファイル（`submission.csv`） |
| **run_id** | 実験を一意に識別する ID（`YYYYMMDD_HHMMSS_モデル_ランダム4桁`）|

## 実験ライフサイクル

```
新コンペ参加
  │
  ▼
config.yaml 更新 + data/raw/ にデータ配置
  │
  ▼
EDA（target 分布・欠損・feature correlation）
  │
  ▼
make run → Baseline (exp001_lgbm_base)
  │         CV Score を SQLite に記録
  │
  ▼
特徴量追加 → make run → CV Score 改善を確認
  │
  ▼
モデル変更（CatBoost 等）→ make run → 比較
  │
  ▼
アンサンブル（複数モデルの平均）
  │
  ▼
最終提出: CV 最良 + LB 最良 の 2 本を選択
```

## CV スコアと提出の関係

```
CV Score（主指標）  ─→  提出候補 A（CV 最良）
                   ─→  提出候補 B（Public LB 最良）
                         ↓
                   Kaggle に 2 本を提出して選択
                         ↓
                   Private LB で最終順位確定
```

- CV スコアを主指標にする（Public LB に引きずられない）
- Public LB と CV の乖離が大きい場合はデータリークを疑う

## 関連タスク

- 新しい用語・状態・ビジネスルールの変更は task に背景と影響範囲を残してから反映する。
- 未確定の業務ルールはこの文書へ入れず、`docs/tasks/backlog/` で調査対象として管理する。
