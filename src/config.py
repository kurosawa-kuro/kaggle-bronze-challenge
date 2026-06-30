"""コンペ切り替え時は env/config.yaml の comp と4項目だけ変更する。"""
import os
from pathlib import Path
import yaml

_ROOT = Path(__file__).parent.parent
_cfg_path = Path(os.environ.get("KBC_CONFIG_PATH", _ROOT / "env" / "config.yaml"))
_cfg = yaml.safe_load(_cfg_path.read_text()) or {}

_data = _cfg.get("data", {})
_cv = _cfg.get("cv", {})
_runtime = _cfg.get("runtime", {})

COMP: str = _cfg.get("comp") or _data["comp"]

TARGET: str = _cfg.get("target") or _data["target"]
ID_COL: str | None = _cfg.get("id_col", _data.get("id_col"))
OBJECTIVE: str = _cfg.get("objective") or _data["objective"]   # regression / binary / multiclass
METRIC: str = _cfg.get("metric") or _data["metric"]             # rmse / auc / logloss / mape

N_FOLDS: int = int(_cfg.get("n_folds", _cv.get("n_folds", 5)))
SEED: int = int(_cfg.get("seed", _cv.get("seed", 42)))

# データパスは comp から自動導出
DATA_RAW: Path = Path("data") / COMP / "raw"
DATA_INTERIM: Path = Path("data") / COMP / "interim"
DATA_FEATURES: Path = Path("data") / COMP / "features"
# 実験記録は BigQuery `<bqDataset>.experiments` に統一（ADR 0002 / utils.logger）。
# 旧 SQLite (EXPERIMENTS_DB) は廃止。
