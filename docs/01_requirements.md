# 01 要件

## 目的

Kaggle コンペティションでブロンズメダル（上位 40% 前後）を獲得する。  
表形式データに対して、**48 時間以内に初回提出できる** 軽量パイプラインを手元環境で回し、スコアを反復改善する。

## スコープ

### 対象

- 表形式データを扱う Kaggle コンペへの参加・提出
- 前処理 → 学習 → 推論 → 提出ファイル生成のパイプライン構築
- 特徴量エンジニアリングとモデル選択の反復実験

### 非対象

- シルバー・ゴールドメダル水準の最終 push（アンサンブル過多、リーク活用等）
- 画像・音声・テキスト主体のコンペ（Deep Learning への過度な展開は行わない）
- **LLM / RAG を使うアプローチ**（実務ポートフォリオは LLM RAG だが、Kaggle ブロンズでは使わない。追随コストが高く、勾配ブースティングで解けるコンペに無理に持ち込まない）
- Google Colab 環境での動作保証
- 本番 MLOps 水準のアーキテクチャ（Port/Adapter, KFP, Vertex AI 等は使わない）

## スキルベース戦略

### 既存スキルの棚卸し（強み）

| スキル | 評価 | Kaggle での活かし方 |
|--------|------|---------------------|
| LightGBM (LambdaRank まで) | 上級 | ハイパラの感度を理解済み → Optuna 30 試行で十分 |
| scikit-learn Pipeline | 中〜上級 | 前処理 Pipeline をそのまま流用 |
| 特徴量スキュー防止の意識 | 上級 | Fold リークを犯さない CV 設計に直結 |
| カスタムメトリクス実装 | 上級 | コンペ指定スコア（NDCG, AUC 等）を自前実装できる |
| DuckDB / BigQuery | 上級 | EDA の集計・大規模 feature mart に即戦力 |

### 最大リスク（罠）

> **「本番品質で作ろうとして沼る」**  
> Port/Adapter、型安全、parity lock — これらは Kaggle では不要。  
> ノートブックを汚く使い倒す方が速い。**アーキテクチャへの投資は最小化する。**

## 制約・方針

| 区分 | 内容 |
|------|------|
| **目標水準** | ブロンズ取得。シルバーは狙わない |
| **モデル選択** | LightGBM を主軸。CatBoost / XGBoost は平均アンサンブル用に留める |
| **フレームワーク** | scikit-learn Pipeline（既存知識をそのまま使う） |
| **実験管理** | SQLite に `(run_id, cv_score, params, timestamp)` を記録。DuckDB で集計 |
| **仮想環境** | `uv` で管理（`uv venv` + `uv pip install`）。速度ペナルティなし・環境汚染なし |
| **実行環境** | WSL Ubuntu / Python |
| **コードスタイル** | ノートブック優先。モジュール化は「同じ処理を 3 回書いたら」に留める |
| **レシピ参照元** | Databricks のデザインパターン・ノートブックレシピを優先参照 |

## 技術スタック

```
アルゴリズム   : LightGBM（主軸）, CatBoost, XGBoost（アンサンブル用）
フレームワーク : scikit-learn
ハイパラ最適化 : Optuna（30〜50 試行）
実験管理       : SQLite（軽量ログ）+ DuckDB（集計・分析）
仮想環境       : uv
環境           : WSL Ubuntu / Python 3.11+

--- 使わないもの ---
Ray / Spark     : ローカル単機で十分。分散は不要
dbt             : SQL 変換ツール。EDA には DuckDB 直クエリで足りる
MLflow / wandb  : SQLite + DuckDB で代替。外部サービス登録コスト不要
```

## Kaggle 固有の学習ポイント

既存スキルでカバーできない Kaggle 特有の知識：

| ポイント | 内容 |
|----------|------|
| **Public LB 過学習** | Public / Private LB は分割されている。CV スコアを主指標にする |
| **Target Encoding** | Fold 内で fit する（リーク防止）。`category_encoders` 使用 |
| **Pseudo Labeling** | ブロンズ圏では不要。シルバー以降のテクニック |
| **コンペ EDA の流れ** | target 分布 → 欠損マップ → feature correlation → 先人の Discussion 確認 |
| **提出戦略** | 最終提出は「CV 最良」と「LB 最良」の 2 本を選ぶ |

## ユーザー

- コンペ参加者（本人のみ）

## ユースケース

| ID | ユースケース | 成功条件 |
|---|---|---|
| UC-001 | 新規コンペのデータを取得し EDA を実施する | target 分布・欠損・feature correlation を把握したノートブックが生成される |
| UC-002 | 48h 以内にベースラインを提出する | Public LB スコアが記録され、ブロンズ圏内かどうかを確認できる |
| UC-003 | 特徴量エンジニアリングを反復して改善する | 実験ごとの CV スコアが SQLite に記録され比較できる |
| UC-004 | 最終提出ファイルを 2 本選んで提出する | `submission.csv` が Kaggle 規格に適合し、CV 最良・LB 最良の 2 本が選択されている |

## 関連タスク

- 要件追加・変更は、まず `docs/tasks/active/` または `docs/tasks/backlog/` に task として記録する。
- 確定した要件だけをこの文書へ反映する。
- 要件変更に伴う未実装作業は `docs/tasks/README.md` から追跡できる状態にする。
