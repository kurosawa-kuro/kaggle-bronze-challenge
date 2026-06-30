.PHONY: setup run nb logs clean init download submit smoke train-local train-vertex collect build-push gcp-bootstrap submit-legacy

VENV   := .venv
PYTHON := $(VENV)/bin/python
UV     := uv
CONFIG ?= configs/lgbm_baseline.yaml
RUN_ID ?= $(shell date -u +%Y%m%d_%H%M%S)
PROJECT_CONFIG ?= conf/project.yaml
GCP_PROJECT ?= $(shell $(PYTHON) -c 'import yaml; c=yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}; print(c.get("gcpProject") or c.get("gcp", {}).get("project") or "")' 2>/dev/null)
REGION ?= $(shell $(PYTHON) -c 'import yaml; c=yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}; print(c.get("gcpRegion") or c.get("gcp", {}).get("region") or "us-central1")' 2>/dev/null)
AR_REPO ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("artifactRegistryRepo") or "kaggle")' 2>/dev/null)
IMAGE_NAME ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("imageName") or "kaggle-bronze-challenge")' 2>/dev/null)
IMAGE_TAG ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("imageTag") or "latest")' 2>/dev/null)
GCS_BUCKET ?= $(shell $(PYTHON) -c 'import yaml; print((yaml.safe_load(open("$(PROJECT_CONFIG)")) or {}).get("gcsBucket") or "")' 2>/dev/null)
IMAGE ?= $(REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(AR_REPO)/$(IMAGE_NAME):$(IMAGE_TAG)

# 初期セットアップ: venv 作成 + 依存インストール
setup:
	$(UV) venv $(VENV)
	$(UV) pip install -r requirements.txt --python $(VENV)/bin/python
	@echo "Setup complete. Run: make run"

# 現在の実験を実行 (run.py)
run:
	$(PYTHON) run.py

# Vertex-ready runner: quick one-fold local check
smoke:
	$(PYTHON) train.py --config $(CONFIG) --run-id $(RUN_ID) --smoke

# Vertex-ready runner: full local training
train-local:
	$(PYTHON) train.py --config $(CONFIG) --run-id $(RUN_ID)

# Build and push the training image to Artifact Registry
build-push:
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet
	docker buildx build --platform linux/amd64 -f infra/Dockerfile -t $(IMAGE) --push .

# Create the minimal GCP resources used by build-push/train-vertex/collect.
gcp-bootstrap:
	gcloud services enable aiplatform.googleapis.com artifactregistry.googleapis.com storage.googleapis.com --project $(GCP_PROJECT)
	gcloud artifacts repositories describe $(AR_REPO) --location=$(REGION) --project=$(GCP_PROJECT) >/dev/null 2>&1 || gcloud artifacts repositories create $(AR_REPO) --repository-format=docker --location=$(REGION) --project=$(GCP_PROJECT)
	gcloud storage buckets describe gs://$(GCS_BUCKET) >/dev/null 2>&1 || gcloud storage buckets create gs://$(GCS_BUCKET) --project=$(GCP_PROJECT) --location=$(REGION) --uniform-bucket-level-access

# Submit the same train.py contract to Vertex Custom Job
train-vertex:
	$(PYTHON) vertex_run.py --config $(CONFIG) --run-id $(RUN_ID) --image-uri $(IMAGE)

# Collect artifacts from gs://<bucket>/runs/<competition>/<run_id>
collect:
	$(PYTHON) collect.py --config $(CONFIG) --run-id $(RUN_ID)

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
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(PYTHON) submit.py --config $(CONFIG) --run-id $(RUN_ID) --message "$(MSG)"'

# 旧提出経路: repository root の submission.csv を直接提出
submit-legacy:
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(VENV)/bin/kaggle competitions submit -c $(COMP) -f submission.csv -m "$(MSG)"'

# 生成物を削除
clean:
	rm -f submission.csv
	find . -name "__pycache__" -type d | xargs rm -rf
