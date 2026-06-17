.PHONY: setup run nb logs clean init download submit

VENV   := .venv
PYTHON := $(VENV)/bin/python
UV     := uv

# 初期セットアップ: venv 作成 + 依存インストール
setup:
	$(UV) venv $(VENV)
	$(UV) pip install -r requirements.txt --python $(VENV)/bin/python
	@echo "Setup complete. Run: make run"

# 現在の実験を実行 (run.py)
run:
	$(PYTHON) run.py

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
	mkdir -p data/raw
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(VENV)/bin/kaggle competitions download -c $(COMP) -p data/raw'

# Kaggle 提出: make submit COMP=house-prices MSG="exp001 lgbm baseline cv=0.44498"
submit:
	doppler run -- sh -c 'KAGGLE_API_TOKEN="$$ML_KAGGLE_TOKEN" $(VENV)/bin/kaggle competitions submit -c $(COMP) -f submission.csv -m "$(MSG)"'

# 生成物を削除
clean:
	rm -f submission.csv
	find . -name "__pycache__" -type d | xargs rm -rf
