.PHONY: setup run exp logs clean

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

# 特定の実験を実行: make exp EXP=exp002_catboost_base
exp:
	$(PYTHON) experiments/$(EXP).py

# 実験ログを表示
logs:
	PYTHONPATH=src $(PYTHON) -c "from logger import show_runs; show_runs()"

# 生成物を削除
clean:
	rm -f submission.csv
	find . -name "__pycache__" -type d | xargs rm -rf
