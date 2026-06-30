# SPEC: GCP レバレッジ Phase1 — sweep + Optuna tune + Vertex HP Tuning

> Claude Code 公式 spec-driven フローの実装前スペック（出典: code.claude.com/docs/en/best-practices）。
> このファイル単体で、文脈を持たない別セッションの Claude が実装できる状態に保つ。
> 着手はこのスペックを書いたセッションではなく**新しいセッション**で行う。
> 親タスク: `docs/tasks/active/hpo-leverage-phase1.md` / 基盤: vertex-ready-runner（完了） / 判断: `docs/adr/0001-vertex-ready-experiment-runner.md`

## Goal

固定パラメータで1回学習するだけの現状の上に、「重要なタイミングで訓練・HPO を高速に並列で回す」3 経路を配線する:

1. **sweep** — 複数 config を並列 Vertex Custom Job に fan-out（独立ジョブ、共有 DB 不要）。
2. **Optuna tune** — 1 台の大マシンで N trials 探索し、best params で最終学習（seed 平均込み）。
3. **Vertex Hyperparameter Tuning** — Vizier ネイティブの並列 trial で大規模 HPO。

いずれも既存の run_id 成果物契約（`outputs/runs/{comp}/{run_id}/`）と「投入は 1 コマンド」の UX を壊さない。

## 現状（実装済みの前提・推測でなく確認済み）

- entrypoints は `src/runner/` パッケージ。`python -m runner.<module>` で起動（Makefile が `PYTHONPATH=src` を export）。
- `src/runner/train.py`: `main()→run()→_train_lgbm()`。**seed 平均は実装済み**（`cfg["seeds"]` をループし oof / test_pred / feature_importance を seed 横断で平均、`metrics.json` に per-seed スコア）。CLI: `--config --run-id [--smoke] [--output-uri] [--input-uri] [--dry-run]`。現状 `model.name=lgbm` のみ対応。
- `src/runner/vertex_run.py`: `main()` 内で `plan` を組み `aiplatform.CustomJob(...).run(sync=args.sync, ...)` で投入。`--sync` 未指定なら `job.run(sync=False)` で**非ブロッキング投入済み**。ただし投入ロジックが `main()` に密結合で、関数として再利用できない。container は `command=["python","-m","runner.train"]`。
- config 例: `configs/lgbm_baseline.yaml`（`data / model / cv / seeds / runtime` の flat 構成。`comp=playground-series-s6e6`, `metric=logloss`, `objective=multiclass`, `seeds:[42,777,2026]`）。

## Out of scope

- Ray / 分散 Optuna + 共有 DB（単機 + Vertex HP Tuning で代替する）。
- MLflow / Vertex AI Experiments を実験トラッキングの正本にすること — 実験記録は **BigQuery `kaggle_ops` に統一**（ADR 0002）。
- DL / GPU / LLM / RAG（LightGBM 主軸を維持）。

（注: Vertex Pipelines / Endpoint / Model Registry / Monitoring / Feature Store は ADR 0002 で**採用方針に反転**。非DL Vertex 機能はフル活用し、邪魔なら後で削る。本 SPEC の対象機能は引き続き sweep / Optuna tune / Vertex HP Tuning の3経路。）
- lgbm 以外（catboost / xgboost）の tune 対応 — 別タスク。本スペックは lgbm のみ。
- 探索空間の高度な config 化 — 今回は最小の `tune:` キー + コード内デフォルトに留める。

## Files & interfaces

| パス | 変更内容 |
|---|---|
| `src/runner/vertex_run.py` | `main()` から再利用可能な投入関数 `submit(*, config_path, run_id, project_cfg, train_cfg, image_uri=None, machine_type=None, spot=True, smoke=False, sync=False, dry_run=False) -> str`（job resource name、dry-run 時は plan JSON 文字列）を抽出。`main()` はこの関数を呼ぶだけにする。**挙動は現状維持**（リグレッションなし）。 |
| `src/runner/sweep.py`（新規） | `python -m runner.sweep --configs a.yaml b.yaml [--run-id-prefix <p>] [--spot] [--dry-run]`。各 config を `vertex_run.submit(..., sync=False)` で**非ブロッキング fan-out**。run_id は `<prefix>_<configstem>` で衝突回避。投入した job resource name 一覧を stdout 出力。 |
| `src/runner/tune.py`（新規） | `python -m runner.tune --config <base.yaml> --run-id <id> [--n-trials N] [--timeout-hours H] [--smoke]`。Optuna で lgbm params を 1 プロセス内 N trials 探索（目的 = cv_score、`data.metric` から方向決定）。各 trial は既存 `models.lgbm.train_cv` + `pipelines.evaluate.cv_score` を再利用（学習を再実装しない）。完了後 best params で**最終学習を seed 平均込みで実行**（`runner.train.run` を呼ぶ）。成果物: 通常の run_id 一式 + `best_params.json` + `study.pkl`（または trials CSV）。 |
| `src/runner/hp_tune.py`（新規） | `python -m runner.hp_tune --config <base.yaml> --run-id <id> [--max-trials N] [--parallel-trials P] [--spot] [--dry-run]`。`aiplatform.HyperparameterTuningJob` を組み、worker は既存学習イメージで `python -m runner.train` を実行。探索空間（learning_rate / num_leaves / feature_fraction 等）を定義し metric id（例 `cv_score`）を最適化。dry-run で job spec を JSON 表示。 |
| `src/runner/train.py` | HP Tuning 用に2点追加。(1) Vizier が渡す trial パラメータを **CLI で受け取り `model.params` を上書き**（`--hyperparams-json '{"learning_rate":0.05}'` 形）。(2) 学習完了時に `cloudml-hypertune` で `cv_score` を Vertex に **report**（`--report-metric <id>` 指定時のみ。未指定なら no-op で**挙動不変**）。 |
| `configs/lgbm_baseline.yaml` | （任意）`tune:` セクションで探索範囲の下限/上限を持たせる。無ければ tune.py / hp_tune.py のコード内デフォルト探索空間を使う。 |
| `Makefile` | `sweep` / `tune` / `hp-tune` ターゲット追加（`.PHONY` に追記）。新ターゲットは `python -m runner.<module>` 形式で書く。 |
| `requirements.txt` | `optuna`（依存済みなら据え置き）、`cloudml-hypertune` を追加（未導入なら）。 |

### Makefile 追加（形）

```makefile
sweep:   ## 複数 config を並列 Vertex Custom Job へ fan-out: make sweep CONFIGS="configs/a.yaml configs/b.yaml"
	$(PYTHON) -m runner.sweep --configs $(CONFIGS) $(SPOT)

tune:    ## Optuna で 1 台 N trials 探索し best で最終学習: make tune CONFIG=... RUN_ID=... N_TRIALS=50
	$(PYTHON) -m runner.tune --config $(CONFIG) --run-id $(RUN_ID) --n-trials $(N_TRIALS)

hp-tune: ## Vertex Hyperparameter Tuning (Vizier 並列): make hp-tune CONFIG=... RUN_ID=... MAX_TRIALS=20 PARALLEL=4
	$(PYTHON) -m runner.hp_tune --config $(CONFIG) --run-id $(RUN_ID) --max-trials $(MAX_TRIALS) --parallel-trials $(PARALLEL) $(SPOT)
```

## Constraints

- 既存の関数・パターンを再利用する（`train_cv` / `cv_score` / `GcsPrefix` / `aiplatform` 投入形）。学習ロジックを再実装しない。
- 学習コード（`train.py`）に Vertex 固有コードを混ぜない分離を維持（ADR 0001）。HP Tuning の report は opt-in で挙動不変。
- Pydantic Settings 三層・DI・本番 MLOps 抽象を持ち込まない（CLAUDE.md）。軽量 stdlib YAML のまま。
- LightGBM 主軸。LLM / RAG / DL を持ち込まない。
- 破綻条件 = 投入 UX が 1 コマンドから崩れること。`make sweep/tune/hp-tune` を 1 行に保つ。
- 推測でコードを書かない。各経路は実際に実行（dry-run 含む）して確認する。
- 既知の前提: 現 Makefile の `train-local/train-vertex/collect/submit/cost-*` は root スクリプト削除に伴い `python -m runner.X` へ要追随（別作業）。本スペックの新ターゲットは最初から新方式で書く。

## Plan

1. `vertex_run.py` の `submit()` 抽出（リファクタのみ、`--dry-run` で挙動不変を確認）。
2. `sweep.py` + `make sweep`（dry-run で複数 plan → 非ブロッキング fan-out）。
3. `tune.py` + `make tune`（極小 trials/folds でローカル緑、`best_params.json` 生成、best で最終 run_id 成果物）。
4. `train.py` に hyperparams 上書き + `cloudml-hypertune` report（report opt-in、未指定時の回帰なし）。
5. `hp_tune.py` + `make hp-tune`（dry-run で job spec → 実投入は GCP コスト承認後）。
6. 連動ドキュメント更新（下記）。

## E2E verification

```bash
# 0. 回帰なし（既存経路）
make smoke CONFIG=configs/lgbm_baseline.yaml

# 1. sweep: 複数 config の投入計画が dry-run で出る（実投入はコスト承認後）
python -m runner.sweep --configs configs/lgbm_baseline.yaml configs/lgbm_baseline.yaml --dry-run

# 2. Optuna tune: ローカルで小 trials が回り best で最終成果物が出る
make tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=tune_smoke N_TRIALS=3
test -f outputs/runs/playground-series-s6e6/tune_smoke/best_params.json
cat  outputs/runs/playground-series-s6e6/tune_smoke/metrics.json   # best params で seed 平均された cv_score

# 3. HP Tuning: job spec が dry-run で出る
python -m runner.hp_tune --config configs/lgbm_baseline.yaml --run-id hp_smoke --max-trials 4 --parallel-trials 2 --dry-run
```

期待:
- (0) 既存 smoke が緑（report / override を足しても回帰しない）。
- (1) 各 config 1 件ずつ計2件の CustomJob plan が JSON 表示される（非ブロッキング投入の形）。
- (2) `best_params.json` が生成され、`metrics.json` の `cv_score` が baseline と比較可能。`seeds` 平均が効いている。
- (3) HyperparameterTuningJob の spec（metric id / 探索空間 / max・parallel trials）が JSON 表示される。

## Docs to update（drift 防止・挙動変更と同一変更内で）

- [ ] `CLAUDE.md` コマンド表（`make sweep` / `make tune` / `make hp-tune`）
- [ ] `docs/04_workflows.md`（3 経路の使い分け: sweep=複数案並列 / tune=単機探索 / hp-tune=Vizier 大規模並列）
- [ ] `docs/01_requirements.md` 技術スタック（Optuna / Vertex HP Tuning / cloudml-hypertune を明記。Ray・MLflow 不採用も）
- [ ] `docs/05_data_model.md`（`best_params.json` / `study.pkl` を run_id 成果物に追加、`tune:` config キー）
- [ ] 完了後、設計判断（native 優先・Ray/MLflow 不採用）の `docs/adr/` 昇格を検討
