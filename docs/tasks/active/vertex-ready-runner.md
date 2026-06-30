# Vertex-ready 実験ランナーの実装

## Goal

同一 `train.py` を local / Vertex Custom Job で実行し、同一の run_id 成果物
（`outputs/runs/{competition}/{run_id}/`）を出す実験契約を実体化する。
決定は `docs/adr/0001-vertex-ready-experiment-runner.md`、契約は `docs/02_architecture.md`「実行モデル」。

## Context

ローカル単機では 5fold / CatBoost / seed 平均 / 複数 config 並列 / overnight が詰まる。
最初から Vertex 前提で組む。GCP は Custom Job + GCS + Artifact Registry に絞る
（Feature Store / Pipelines 本格運用 / Endpoint / Model Registry / Monitoring は使わない）。

破綻条件は「投入までが面倒になること」。CLI を 1 コマンドに保つことを品質ゲートにする。

## Scope

含む:
- `run.py` → config 駆動の `train.py`（`--config`）への移行。local / Vertex 共通、Vertex を知らない純粋学習コード
- run_id 成果物契約の生成（config snapshot / metrics.json / oof.parquet / test_pred.parquet / feature_importance.csv / submission.csv / log.txt）
- `vertex_run.py`（Custom Job 投入のみ）/ `collect.py`（GCS 回収）/ `submit.py`（整形＋提出）
- `configs/*.yaml`（`model` / `cv` / `seeds` / `runtime`）
- Makefile: `smoke` / `train-local` / `train-vertex` / `collect` / `submit`
- 学習コンテナ（Artifact Registry）と GCS バケットレイアウト `gs://<bucket>/runs/{competition}/{run_id}/`
- 連動ドキュメント更新: `04_workflows.md`（新コマンド）, `05_data_model.md`（config スキーマ / run_id レイアウト）, `CLAUDE.md` コマンド表

含まない:
- Vertex Pipelines / Endpoint / Model Registry / Monitoring / Feature Store

## Skeleton

ビジネスロジックを入れる前に、空シグネチャ + 成果物パス生成だけで配線を固定する
（`.claude/skills/skeleton-first` 準拠）:
- [x] `train.py --config` がダミー成果物を `outputs/runs/{comp}/{run_id}/` に書く
- [x] `vertex_run.py` が `make train-local` と同じ引数面で Custom Job を組み立てる（dry-run 可）
- [x] `collect.py` が `gs://.../runs/{comp}/{run_id}/` ↔ `outputs/runs/...` を 1:1 で対応づける

## Plan

未確定の設計判断（着手前に決める。括弧内は study-gcp-* 調査を踏まえた暫定方針）:
- [x] config スキーマ: 現行 flat に `model`/`cv`/`seeds`/`runtime` を足すか、ネスト構成へ移すか
  - 暫定: 軽量 stdlib YAML 読み込み（GKE `scripts/_common.py` 方式）を採用。Pydantic Settings 三層（GKE `ml/common/config/base.py`）は本番 MLOps 水準なので**持ち込まない**（ADR 0001 / CLAUDE.md と整合）
- [x] `run_id` 採番規則（timestamp 不可の制約あり → Makefile 側 `RUN_ID` で渡す。未指定時のみ UTC timestamp）
- [x] SQLite ログと run_id 成果物の責務分担（SQLite=横断インデックス、`outputs/runs/...`=正本実体）
- [x] GCP 認証: ローカル投入=ADC（`gcloud auth application-default login`）、コンテナ内=アタッチ SA + `google.auth.default()`。**Doppler は Kaggle token 専用のまま**
- [x] GCS バケット名・リージョン・Artifact Registry リポジトリ名の決定（`conf/project.yaml` に project 設定として置く）
- [x] **`vertex_run.py`（Custom Job 投入）は流用元が無い → 新規実装**

実装順:
- [x] skeleton 配線（上記）
- [x] `train.py` を local full で緑にする（既存 pipelines/models を再利用、挙動を変えない）
- [x] run_id 成果物の生成
- [x] `make smoke` / `train-local`
- [x] 学習コンテナ + Artifact Registry push 経路（Docker build 済み、push は `make gcp-bootstrap && make build-push`）
- [x] `vertex_run.py` + `make train-vertex`（Custom Job dry-run 済み。実投入は GCP resource 作成後）
- [x] `collect.py` + `make collect` 経路（GCS bucket 作成後に実行）
- [x] `submit.py` + `make submit` 経路の整理
- [x] 連動ドキュメント更新

## 流用元マッピング（study-gcp-* リポジトリ）

3 リポジトリを調査。**学習・成果物・認証・コンテナ・CLI の足回りはほぼ流用できる**。
ただし **Vertex Custom Job の投入コードはどこにも無い**（GKE=KFP component を pod 内実行、feature-store 系 2 つ=Cloud Run job）→ `vertex_run.py` のみ新規。

| 今回のモジュール | 流用元 | 種別 |
|---|---|---|
| `collect.py` の GCS 1:1 入出力 | search-mlops-gke `ml/registry/artifact_store.py:22-95`（`GcsPrefix` + `upload_directory` / `download_file`） | 直接流用 |
| コンテナ内 GCP 認証 | feature-store `app/common/auth.py`（`google.auth.default` + refresh、ADC/メタデータ両対応） | 直接流用 |
| `train.py` の CLI / run 分離 | search-mlops-gke `ml/training/trainer.py:311-345`（argparse → `run()`、pure train / write / orchestrate 分離、uploader 注入） | テンプレ流用 |
| コンテナ entrypoint（複数コマンド dispatch） | feature-store(-offline) `app/main.py` + `infra/Dockerfile`（uv slim + `ENTRYPOINT python -m app.main`） | 直接流用 |
| Dockerfile + AR push | 3 repo 共通。例 feature-store-offline `infra/Dockerfile` + feature-store `Makefile:53-56`（`buildx --platform linux/amd64 --push`、URI `{region}-docker.pkg.dev/{project}/{repo}/{img}:{tag}`） | 直接流用 |
| Cloud Build 非同期 build（local docker の代替） | search-mlops-gke `scripts/deploy/build_kserve_images.py:65-100`（submit_async + wait） | 任意流用 |
| Vertex job 状態ポーリング | search-mlops-gke `scripts/ops/vertex/pipeline_wait.py:51-89`（`PipelineJob` → `CustomJob.state` に読替） | 参考 |
| 軽量 config precedence | search-mlops-gke `scripts/_common.py:38-154`（stdlib YAML + cascading env/secret、Pydantic 不要） | 直接流用 |
| Makefile CLI UX | feature-store(-offline) `Makefile`（computed IMAGE URI / phony targets / `gcloud storage` verify） | 流用 |
| `vertex_run.py`（Custom Job 投入） | **流用元なし** | 新規 |

### GKE をどこまで使うか（設計判断）

- **採用する**: search-mlops-gke の**コード資産**（上表）。`artifact_store.py` / `trainer.py` の CLI 構造 / `_common.py` の config precedence / Cloud Build 非同期 build が直撃で効く。
- **採用しない**: GKE クラスタ（Kubernetes / node pool / KServe / Composer / Endpoint）を**実行基盤として**立てること。
  - 理由: ブロンズの要件は「重い実験を並列・overnight・ローカル非占有で回すスループット」。これは **Vertex Custom Job（+ Spot VM）で完結**する。GKE はクラスタ常駐コスト・kubectl/manifest・autoscaler 運用という本番サービング/オーケストレーション向けの面を足すだけで、バッチ実験のスループットには寄与しない。ADR 0001 の「GCP を豪華にしない／Custom Job + GCS + AR に絞る」と逆行する。
  - 例外条件: 「数十〜数百 config を恒常的に bin-packing で回す」規模になったら GKE Job + 大きめ node pool が安くなりうる。ブロンズ規模（数 config × 数 seed）では over-engineering。必要になったら別 ADR で再検討。

## 重要サンプルコード（流用元の実コード抜粋）

> いずれも study-gcp-* リポジトリの実コード。今回の `train.py`/`collect.py`/`vertex_run.py`/Docker/Makefile の雛形として転用する。

### GCS run_id 成果物の up/download（`collect.py` の核）
`search-mlops-gke/ml/registry/artifact_store.py`。`outputs/runs/{comp}/{run_id}/` ↔ `gs://.../runs/{comp}/{run_id}/` の 1:1 にそのまま使える。重い `google.cloud.storage` import を呼び出し時まで遅延しているのもテスト容易で良い。

```python
@dataclass(frozen=True)
class GcsPrefix:
    bucket: str
    prefix: str  # no leading/trailing slash

    def uri(self, *parts: str) -> str:
        joined = "/".join(p.strip("/") for p in parts if p)
        base = f"gs://{self.bucket}" + (f"/{self.prefix}" if self.prefix else "")
        return f"{base}/{joined}" if joined else base


def upload_directory(local_dir: Path, destination: GcsPrefix) -> list[str]:
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket(destination.bucket)
    uploaded = []
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(local_dir).as_posix()
        blob_name = f"{destination.prefix}/{rel}" if destination.prefix else rel
        bucket.blob(blob_name).upload_from_filename(str(path))
        uploaded.append(f"gs://{destination.bucket}/{blob_name}")
    return uploaded
```

### GCP 認証（コンテナ内・ローカル共通）
`feature-store/app/common/auth.py`。Custom Job 内のアタッチ SA でも、ローカル ADC でも同じコードで通る。

```python
import google.auth, google.auth.transport.requests
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

def access_token() -> str:
    creds, _ = google.auth.default(scopes=_SCOPES)
    creds.refresh(google.auth.transport.requests.Request())
    if not creds.token:
        raise SystemExit("[error] failed to obtain access token")
    return str(creds.token)
```

### config 駆動 train CLI（pure train / write / orchestrate 分離）
`search-mlops-gke/ml/training/trainer.py:311-345`。`train.py --config ... --run-id ... --output-uri ...` の引数面と `main()→run()` 分離をこの形に倣う。

```python
def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="LightGBM LambdaRank training job")
    p.add_argument("--dry-run", action="store_true")          # ← make smoke 相当
    p.add_argument("--save-to", default=None)
    p.add_argument("--hyperparams-json", default=None)
    p.add_argument("--model-output-path", default=None)
    p.add_argument("--metrics-output-path", default=None)
    p.add_argument("--feature-importance-output-path", default=None)
    return p.parse_args(argv)

def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        run(dry_run=args.dry_run, save_to=args.save_to, ...)   # 純粋ロジックは run() に隔離
    except Exception:
        logger.exception("training job failed")
        return 1
    return 0
```

### 学習コンテナ（uv slim + 単一 entrypoint）
`feature-store-offline/infra/Dockerfile`。`app.main` の dispatch table で `train`/`collect` を分岐させる。

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache "lightgbm" "catboost" "google-cloud-storage>=2.18" "google-auth>=2.30"
COPY src ./
ENTRYPOINT ["python", "-m", "app.main"]
CMD ["train"]
```

### AR build & push（`make` ターゲット）
`feature-store/Makefile:53-56`。

```makefile
build-push: ## 学習 image を AR へ build & push
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet
	docker buildx build --platform linux/amd64 -f infra/Dockerfile -t $(IMAGE) --push .
```

### Vertex job 状態ポーリング（`vertex_run.py` の wait 部・参考）
`search-mlops-gke/scripts/ops/vertex/pipeline_wait.py`。`PipelineJob` を `CustomJob` に読み替える。terminal state 判定とポーリング間隔の作りをそのまま使える。

```python
TERMINAL_FAILURE_STATES = {"FAILED", "CANCELLED", "CANCELLING", "PAUSED"}
from google.cloud import aiplatform
aiplatform.init(project=project_id, location=region)
deadline = time.monotonic() + timeout_seconds
while time.monotonic() < deadline:
    state = _state_name(getattr(job, "state", None))
    if state == "SUCCEEDED":
        return 0
    if state in TERMINAL_FAILURE_STATES:
        return fail(f"ended in state={state}")
    time.sleep(poll_seconds)
```

### `vertex_run.py` Custom Job 投入（新規・参考雛形 / ★未検証）
流用元が無いため新規。学習ロジックは持たず、AR の学習 image で `train.py` を投げるだけ。API 仕様は実装時に SDK ドキュメントで確認する（下は形の参考）。

```python
# 参考雛形（未検証）— 実装タスクで API を確認して確定する
from google.cloud import aiplatform

def submit(*, project, region, bucket, image_uri, config_path, run_id, comp,
           machine_type="n1-highmem-16", timeout_hours=8):
    aiplatform.init(project=project, location=region, staging_bucket=f"gs://{bucket}")
    job = aiplatform.CustomJob(
        display_name=f"kaggle-{comp}-{run_id}",
        worker_pool_specs=[{
            "machine_spec": {"machine_type": machine_type},
            "replica_count": 1,
            "container_spec": {
                "image_uri": image_uri,
                "args": ["train", "--config", config_path, "--run-id", run_id,
                         "--output-uri", f"gs://{bucket}/runs/{comp}/{run_id}/"],
            },
        }],
    )
    job.run(timeout=timeout_hours * 3600)   # Spot VM は scheduling/strategy で指定（要確認）
    return job.resource_name
```

## Acceptance Criteria

- `make smoke CONFIG=...` が 1fold をローカルで実行し成果物を出す
- `make train-local CONFIG=...` と `make train-vertex CONFIG=...` が **同一レイアウトの run_id 成果物**を出す
- `make collect RUN_ID=...` が GCS から `outputs/runs/...` を再現する
- 既存 `make run`／既存 CV スコアが回帰しない（または明示的に `train.py` へ移行済み）
- `04_workflows.md` / `05_data_model.md` / `CLAUDE.md` が新コマンドと drift していない

## Verification

- `make smoke CONFIG=configs/lgbm_baseline.yaml`
- `make train-local CONFIG=configs/lgbm_baseline.yaml` → `outputs/runs/<comp>/<run_id>/` を確認
- `make train-vertex CONFIG=configs/catboost_seed_avg.yaml` → Vertex ログ + GCS 成果物
- `make collect RUN_ID=latest` → ローカルと一致

## Notes

- 推測でコードを書かない。コマンドは実際に実行して確認する（CLAUDE.md）。
- GCP コストは「豪華にしない」。Kaggle 実験を 1 コマンドで外に投げられる状態だけを守る。
- 2026-06-30: `make run` 成功（CV logloss=0.08763）。`make train-local CONFIG=configs/lgbm_baseline.yaml RUN_ID=local_full_check` 成功し、同じ CV logloss=0.08763 と run_id 成果物一式を生成。
- 2026-06-30: `make smoke CONFIG=configs/lgbm_baseline.yaml RUN_ID=smoke_check` 成功。`docker build -f infra/Dockerfile -t kaggle-bronze-challenge:local .` と `docker run --rm kaggle-bronze-challenge:local train.py --config configs/lgbm_baseline.yaml --run-id container_dryrun --dry-run` 成功。
- 2026-06-30: GCP active account/project は `kurokawa81toshifumi@gmail.com` / `mlops-dev-a`。`gcsBucket=mlops-dev-a-kaggle-bronze-runs` と AR repo `kaggle` は未作成だったため、コスト発生を避けて実作成・push・Vertex 実投入は保留。明示実行用に `make gcp-bootstrap` を追加。
