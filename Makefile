.PHONY: setup run nb logs clean init download submit smoke train-local train-vertex collect register-model register-servable pipeline build-push build-push-serving batch-predict endpoint-deploy endpoint-teardown gcp-bootstrap submit-legacy stage-data cost cost-record cost-notify sweep tune hp-tune

VENV   := .venv
PYTHON := $(VENV)/bin/python
UV     := uv
# entrypoints は src/runner/ パッケージ。runner 実行時のみ src を import パスに通す
# （gcloud/bq/kaggle 等の外部 Python CLI に PYTHONPATH=src を渡すと自身の utils を
#   こちらの src/utils で shadow され壊れるため、グローバル export はしない）。
PYRUN  := PYTHONPATH=src $(PYTHON) -m
CONFIG ?= configs/lgbm_baseline.yaml
RUN_ID ?= $(shell date -u +%Y%m%d_%H%M%S)
PROJECT_CONFIG ?= env/project.yaml
GCP_PROJECT ?= $(shell $(PYTHON) -c 'import yaml; c=yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}; print(c.get("gcpProject") or c.get("gcp", {}).get("project") or "")' 2>/dev/null)
REGION ?= $(shell $(PYTHON) -c 'import yaml; c=yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}; print(c.get("gcpRegion") or c.get("gcp", {}).get("region") or "us-central1")' 2>/dev/null)
AR_REPO ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("artifactRegistryRepo") or "kaggle")' 2>/dev/null)
IMAGE_NAME ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("imageName") or "kaggle-bronze-challenge")' 2>/dev/null)
IMAGE_TAG ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("imageTag") or "latest")' 2>/dev/null)
GCS_BUCKET ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("gcsBucket") or "")' 2>/dev/null)
COMP_DATA ?= $(shell $(PYTHON) -c 'import yaml; c=yaml.safe_load(open("env/config.yaml")) or {}; print(c.get("comp") or c.get("data", {}).get("comp") or "")' 2>/dev/null)
IMAGE ?= $(REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(AR_REPO)/$(IMAGE_NAME):$(IMAGE_TAG)
SERVING_IMAGE ?= $(REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(AR_REPO)/$(IMAGE_NAME)-serving:$(IMAGE_TAG)
# overnight バッチ既定で Spot（約1/3以下）。on-demand にするには: make train-vertex SPOT=
SPOT ?= --spot

# 初期セットアップ: venv 作成 + 依存インストール
setup:
	$(UV) venv $(VENV)
	$(UV) pip install -r requirements.txt --python $(VENV)/bin/python
	@echo "Setup complete. Run: make run"

# 現在の実験を実行 (run.py)
run:
	$(PYRUN) runner.run

# Vertex-ready runner: quick one-fold local check
smoke:
	$(PYRUN) runner.experiment.train --config $(CONFIG) --run-id $(RUN_ID) --smoke

# Vertex-ready runner: full local training
train-local:
	$(PYRUN) runner.experiment.train --config $(CONFIG) --run-id $(RUN_ID)

# Build and push the training image to Artifact Registry
build-push:
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet
	docker buildx build --platform linux/amd64 -f infra/Dockerfile -t $(IMAGE) --push .

# Create the minimal GCP resources used by build-push/train-vertex/collect.
gcp-bootstrap:
	gcloud services enable aiplatform.googleapis.com artifactregistry.googleapis.com storage.googleapis.com --project $(GCP_PROJECT)
	gcloud artifacts repositories describe $(AR_REPO) --location=$(REGION) --project=$(GCP_PROJECT) >/dev/null 2>&1 || gcloud artifacts repositories create $(AR_REPO) --repository-format=docker --location=$(REGION) --project=$(GCP_PROJECT)
	gcloud storage buckets describe gs://$(GCS_BUCKET) >/dev/null 2>&1 || gcloud storage buckets create gs://$(GCS_BUCKET) --project=$(GCP_PROJECT) --location=$(REGION) --uniform-bucket-level-access

# Stage local raw data to GCS so the Vertex container can fetch it (train.py --input-uri)
stage-data:
	gcloud storage cp --recursive data/$(COMP_DATA)/raw gs://$(GCS_BUCKET)/data/$(COMP_DATA)/

# Submit the same train.py contract to Vertex Custom Job (Spot by default)
train-vertex:
	$(PYRUN) runner.experiment.vertex_run --config $(CONFIG) --run-id $(RUN_ID) --image-uri $(IMAGE) $(SPOT)

# Optuna 探索（1マシン）。best params を run_id 成果物に保存。N_TRIALS / FINAL=--final
# make tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=tune01 N_TRIALS=30
tune:
	$(PYRUN) runner.experiment.tune --config $(CONFIG) --run-id $(RUN_ID) --n-trials $(or $(N_TRIALS),30) $(FINAL)

# Vertex Hyperparameter Tuning (Vizier) — マネージド並列探索。MAX_TRIALS / PARALLEL
# make hp-tune CONFIG=configs/lgbm_baseline.yaml RUN_ID=hpt01 MAX_TRIALS=20 PARALLEL=4
hp-tune:
	$(PYRUN) runner.experiment.hp_tune --config $(CONFIG) --run-id $(RUN_ID) --image-uri $(IMAGE) --max-trials $(or $(MAX_TRIALS),20) --parallel-trials $(or $(PARALLEL),4)

# Fan out multiple configs as parallel Vertex Custom Jobs (Spot by default)
# make sweep CONFIGS="configs/a.yaml configs/b.yaml" TAG=exp01
sweep:
	$(PYRUN) runner.experiment.sweep --configs $(CONFIGS) $(if $(TAG),--tag $(TAG),) --image-uri $(IMAGE) $(SPOT)

# Collect artifacts from gs://<bucket>/runs/<competition>/<run_id>
collect:
	$(PYRUN) runner.ops.collect --config $(CONFIG) --run-id $(RUN_ID)

# Register a run's model into Vertex AI Model Registry (gs://<bucket>/runs/<comp>/<run_id>/model)
register-model:
	$(PYRUN) runner.model.register --config $(CONFIG) --run-id $(RUN_ID)

# Register WITH the real serving container so the model is batch/online predictable
register-servable:
	$(PYRUN) runner.model.register --config $(CONFIG) --run-id $(RUN_ID) --serving-image $(SERVING_IMAGE)

# Submit a Vertex AI Pipeline (KFP): train -> register. DRY=--dry-run for compile-only.
pipeline:
	$(PYRUN) runner.model.pipeline --config $(CONFIG) --run-id $(RUN_ID) $(DRY)

# Build + push the serving image (infra/Dockerfile.serving) to Artifact Registry
build-push-serving:
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet
	docker buildx build --platform linux/amd64 -f infra/Dockerfile.serving -t $(SERVING_IMAGE) --push .

# Submit a Vertex Batch Prediction job. SRC=gs://.../instances.jsonl. DRY=--dry-run.
batch-predict:
	$(PYRUN) runner.model.batch_predict --config $(CONFIG) --run-id $(RUN_ID) --gcs-source $(SRC) $(DRY)

# Deploy a servable model to a Vertex Endpoint. WARNING: 24/7 standing cost. DRY=--dry-run.
endpoint-deploy:
	$(PYRUN) runner.model.deploy deploy --config $(CONFIG) $(DRY)

# Undeploy + delete the Endpoint to stop the standing cost.
endpoint-teardown:
	$(PYRUN) runner.model.deploy teardown --config $(CONFIG) $(DRY)

# Record a finished Vertex job's estimated cost into BigQuery (kaggle_ops.cost_estimates)
cost-record:
	$(PYRUN) runner.ops.costs record --config $(CONFIG) --run-id $(RUN_ID)

# Show month-to-date estimated GCP cost vs ¥1000/¥5000 thresholds
cost:
	$(PYRUN) runner.ops.costs report --config $(CONFIG)

# Push the month-to-date cost summary to Discord (webhook in env/secret.yaml)
cost-notify:
	$(PYRUN) runner.ops.costs notify --config $(CONFIG)

# 特定のノートブック実験を実行: make nb NB=exp002_catboost_base
nb:
	$(PYTHON) notebooks/$(NB).py

# 実験ログを表示
logs:
	PYTHONPATH=src $(PYTHON) -c "from utils.logger import show_runs; show_runs()"

# 新コンペ初期化: make init COMP=house-prices-advanced-regression-techniques
# download → train/test 正規化 → config.yaml 下書き表示 → competition doc 生成
init:
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(PYTHON) scripts/init_competition.py $(COMP)'

# Kaggle データ取得: make download COMP=house-prices
# Doppler の ML_KAGGLE_TOKEN を KAGGLE_API_TOKEN にマッピングして kaggle CLI へ渡す
download:
	mkdir -p data/$(COMP)/raw
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(VENV)/bin/kaggle competitions download -c $(COMP) -p data/$(COMP)/raw'

# Kaggle 提出: make submit CONFIG=configs/lgbm_baseline.yaml RUN_ID=exp001 MSG="exp001 lgbm baseline"
submit:
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" PYTHONPATH=src $(PYTHON) -m runner.ops.submit --config $(CONFIG) --run-id $(RUN_ID) --message "$(MSG)"'

# 旧提出経路: repository root の submission.csv を直接提出
submit-legacy:
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(VENV)/bin/kaggle competitions submit -c $(COMP) -f submission.csv -m "$(MSG)"'

# 生成物を削除
clean:
	rm -f submission.csv
	find . -name "__pycache__" -type d | xargs rm -rf
