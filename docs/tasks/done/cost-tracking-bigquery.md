# GCP コスト可視化を BigQuery に統一  ✅ Done (2026-06-30)

> 完了。概算ロガー（BigQuery `cost_estimates`）+ `make cost`/`cost-record`/`cost-notify` + 予算アラート ¥5000（¥1000/¥2500/¥4500/¥5000）+ Discord 通知（概算側）を実装・実機確認。
> 判断: **実請求の Discord 連携（Budget→Pub/Sub→Cloud Function, 案B）は見送り（案A 採用）** — 概算が即時 Discord に出るため、実請求はメール（請求管理者既定）で保険とする。要望が出たら別タスクで案B。

## Goal

GCP 利用コストを「今月いくら使ったか」即時に把握できる状態にし、月 ¥1000（watch）/ ¥5000（相談）方針を運用で守れるようにする。記録は **BigQuery に統一**（SQLite は使わない）。

## Context

ユーザー方針（[[feedback_gcp_cost_policy]]）: 月額累計が ¥1000 未満は遠慮なく増強、¥5000 まで承認済み、超える前に相談。後から大きな請求が来るのを避けたい。
SQLite はローカルファイルで GCP 上に存在せず、Vertex（使い捨てコンテナ）/複数マシン運用ではコスト記録がマシン依存・消失する。→ BigQuery に統一する判断（ユーザー合意 2026-06-30）。

## Scope

含む（2層）:
- **A. 予算アラート（実請求ガードレール）**: Cloud Billing Budget ¥1000 / ¥5000 閾値でメール通知（billing account 010F21-EF2363-604E56）
- **B. 概算ロガー（即時・自作）**:
  - BQ dataset `kaggle_ops`（location us-central1）/ table `vertex_costs`
  - `costs.py`: 価格表（machine_type→on-demand/spot $/h, 概算）+ 概算計算 + BQ record/report
  - `make cost-record RUN_ID=<id>`: ジョブ実績時間（start/end）× machine 単価 × Spot 割で概算し1行 insert
  - `make cost`: 当月累計（概算 JPY）を ¥1000/¥5000 と並べて表示
- 連動ドキュメント更新（CLAUDE.md コマンド表 / 04_workflows / project.yaml 設定）

後追い（別タスク可）:
- Billing Export → BigQuery（実請求の真値, Console 設定, 約1日ラグ）で概算×実績を突合

含まない:
- リアルタイム原価ダッシュボード（BQ 課金エクスポートで十分になったら検討）

## 設計メモ

- 価格は **list price ベースの概算**。真値は Billing Export 側。`costs.py` の価格表は `env/project.yaml` の `jpyPerUsd` で円換算。
- 概算 = hourly_usd(machine, spot) × duration_h。duration は Vertex ジョブの start/end（`gcloud ai custom-jobs describe` / aiplatform）から取得。
- ジョブには `purpose=kaggle-bronze` ラベル付与済み（vertex_run.py）→ 将来 Billing Export を用途で絞れる。

## Plan

- [x] BQ dataset `kaggle_ops` + table **`cost_estimates`（汎用スキーマ）** 作成（`vertex_costs` は廃止）
- [x] Cloud Billing 予算アラート設定（¥5000 予算, 閾値 20/50/90/100% = ¥1000/¥2500/¥4500/¥5000）
- [x] `costs.py`（価格表 + estimate + BQ record/report、プラグイン式）
- [x] `make cost-record` / `make cost`
- [x] smoke2 で record テスト（n1-standard-4 60s ≈ ¥0.48 を記録、`make cost` で当月集計確認）
- [x] 連動ドキュメント更新（CLAUDE.md / 04_workflows / project.yaml）

## Acceptance Criteria

- `make cost-record RUN_ID=<完了ジョブ>` が `vertex_costs` に1行入る
- `make cost` が当月累計（概算 JPY）と ¥1000/¥5000 しきい値を表示
- 予算アラートが ¥1000 / ¥5000 で発火する設定になっている
- ドキュメントが新コマンドと drift していない

## Notes

- 2026-06-30 実装完了。**BigQuery 統一**（ユーザー主張どおり。SQLite はローカルファイルで Vertex/複数マシン運用に不適）。
- テーブルは **汎用 `kaggle_ops.cost_estimates`**（Vertex 専用にしない）。service/resource_type/usage_qty/usage_unit/unit_price_usd/est_usd/est_jpy/labels 等。GCS・BQ・GCE は `costs.py` に `PRICES` 追加＋`record_<service>()` を足すだけで同テーブルに記録できる。
- 価格は us-central1 list-price 概算（USD）、Spot は `SPOT_FACTOR=0.30`。真値は Billing Export（後追い・約1日ラグ）。
- 予算アラート: budget `28c447c6-6cf9-4390-93bb-1ddfd0640adf`（billing account 010F21-EF2363-604E56, JPY）。通知先は請求管理者既定。
- 後追い候補: (1) Billing Export → BigQuery で概算×実績の突合, (2) `collect` に cost-record を統合, (3) GCS/BQ ストレージ・スキャンのエスティメータ追加。
- 2026-06-30 **Discord 通知**追加: `make cost-notify`（当月サマリ送信）＋ `cost-record` 時に当月累計が ¥1000 以上なら自動通知。webhook は `env/secret.yaml`（gitignore 済、`env/secret.example.yaml` にテンプレ）/ env `DISCORD_WEBHOOK_URL` でも可。**ハマり所**: Discord は urllib 既定 UA を 403 で弾くため `User-Agent` ヘッダ必須（修正済、実送信成功）。
- 注意: これは**概算側**の Discord 通知。GCP **実請求**の予算アラートを Discord に出すには Budget→Pub/Sub→Cloud Function が必要（未実装、要望あれば別タスク）。
