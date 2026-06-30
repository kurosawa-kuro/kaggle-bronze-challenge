# GCP レバレッジ Phase1: seed平均 + sweep + Optuna + HP Tuning 土台  ✅ Done (2026-06-30)

> 完了。4機能すべて実機検証: seed平均（実full run で平均がベスト個別 seed を上回る）/ sweep（並列 baseline vs deep）/ Optuna tune / Vertex HP Tuning（Vizier 2 trial SUCCEEDED）。基盤改善で config を base64 配送（新 config でも再ビルド不要）。Ray/MLflow は不採用、スケール HPO は Vertex 純正で。

## Goal

「重要なタイミングで訓練・HPO を高速に並列で回す」ための実行ロジックを配線する。
基盤（Vertex 投入 / Spot / 大マシン / run_id / コスト）は完成済み（[[vertex-ready-runner]]）。本タスクはその上の「中身」。

## Context

現状 `train.py` は固定パラメータで `train_cv` を1回呼ぶだけ。seed平均も Optuna 探索も未配線。
道具立て判断（2026-06-30, ユーザー合意）:
- **入れる**: Optuna（依存済・local/Kaggle 再現用）、make sweep（独立 Custom Job を並列 fan-out）、**Vertex Hyperparameter Tuning（Vizier, native）** = スケール並列 HPO。
- **入れない**: Ray（クラスタ常駐・ADR 0001 逆行・bronze に過剰）、MLflow（常駐サーバ。SQLite+run_id成果物+BQ で代替。クラウド UI が要れば Vertex AI Experiments を native で）。
- 「vertex標準で足りるなら native を優先」というユーザー方針に従う。

## Scope

- [x] **seed 平均**: `train.py` が config の `seeds:[...]` をループし、oof/test_pred/feature_importance を seed 横断で平均。metrics に per-seed スコア + 平均。（検証: 2seed 平均 cv=0.11047 < 個別 0.11071/0.11148。smoke 回帰なし）
- [x] **make sweep**: 複数 config を**並列 Vertex Custom Job**に fan-out。`vertex_run` を `submit_from_config()` 関数化＋非ブロッキング `.submit()` 化（検証: dry-run で run_id 導出OK／実投入で2本が約1秒差で並列作成＝ハングなし）。
- [x] **Optuna tune**: `runner/tune.py`（`make tune`）で 1台の大マシン上で N trials。best_params.json / best_config.yaml / trials.csv を run_id 成果物に保存、`--final` で best の最終学習（seed平均）。（検証: 2 trials smoke で best 選択・成果物生成 OK）
- [x] **Vertex HP Tuning 土台**: `train.py` が `parse_known_args` で Vertex の `--<param>=<value>` を拾い model.params 上書き、`--hp-metric-tag` で cv_score を `hypertune` 報告。`runner/hp_tune.py`（`make hp-tune`）が HyperparameterTuningJob（Vizier, 7 param 空間）を投げる。（検証: local で override+metric報告 OK／n1-standard-4 で smoke HPT が RUNNING）
- 連動ドキュメント更新（CLAUDE.md / 04_workflows / requirements 技術スタック）

含まない: Ray, MLflow, 分散Optuna+DB（HP Tuning で代替）。

## Plan

- [ ] configs に `seeds` 追加 + train.py seed平均（local smoke/2-seed で検証）
- [ ] vertex_run `.submit()` 非ブロッキング化 + sweep.py + make sweep
- [ ] Optuna tune モード + 成果物（best_params.json / study）
- [ ] cloudml-hypertune report + hp_tune.py（HyperparameterTuningJob submitter）+ make hp-tune
- [ ] ドキュメント

## Acceptance Criteria

- `make smoke` 緑（回帰なし）。seeds 複数指定で oof/test_pred が seed 平均になり metrics に seed 別スコアが出る
- `make sweep CONFIGS=...` が複数ジョブを並列投入（ブロックしない）
- `make tune` が Optuna で best params を出し、best で最終 run_id 成果物を生成
- `make hp-tune` が Vertex HyperparameterTuningJob を投げ、Vizier 並列 trial が走る
- ドキュメントが新コマンドと drift していない

## Notes

- 2026-06-30 sweep 検証中に **config がイメージにベイクされている**問題を発見（`make sweep` で新規 `lgbm_deep.yaml` を投げたら `/app/configs/lgbm_deep.yaml` not found で FAILED）。→ **config を base64 でコンテナ引数に渡す**方式に変更（`train.py --config-b64` / `vertex_run` が `Path(config).read_bytes()` を b64 化）。これで**新 config でも再ビルド不要**で sweep できる。ローカルは従来どおり `--config` パス。
- sweep 検証で `make sweep`（--dry-run 付け忘れ）により実ジョブ2本を誤投入。非ブロッキング `.submit()` の並列性（約1秒差で2本作成）を実証。コスト方針上は予算内。baseline は走行、旧 deep は上記 config 問題で FAILED → b64 修正後に deep_b64 として再投入。
- 2026-06-30 #4 HP Tuning 実装。**ハマり所2点**: (1) `HyperparameterTuningJob.run(sync=False)` 直後に `resource_name` を読むと「resource has not been created」→ `wait_for_resource_creation()` を挟む（作成 RPC 完了のみ待つ、プロセス終了で消えない）。(2) parallel×n2-standard-16 で `429 custom_model_training_n2_cpus` quota 超過 → 大きい並列 HPT は n2 quota 増加申請 or 小さめマシン/並列に。smoke 検証は n1-standard-4 で実施。
- 実 baseline vs deep スイープ結果: baseline cv=0.08668 > deep cv=0.08689（deep 過学習気味）。コスト: full run 1本 ≈ ¥6.5（spot n2-standard-16）。当月概算 ¥15。
