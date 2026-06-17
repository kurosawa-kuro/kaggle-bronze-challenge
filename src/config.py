"""コンペ切り替え時は conf/config.yaml の comp と4項目だけ変更する。"""
from pathlib import Path
import yaml

_cfg = yaml.safe_load((Path(__file__).parent.parent / "conf" / "config.yaml").read_text())

COMP: str = _cfg["comp"]

TARGET: str = _cfg["target"]
ID_COL: str | None = _cfg["id_col"]
OBJECTIVE: str = _cfg["objective"]   # regression / binary / multiclass
METRIC: str = _cfg["metric"]         # rmse / auc / logloss / mape

N_FOLDS: int = _cfg["n_folds"]
SEED: int = _cfg["seed"]

# データパスは comp から自動導出
DATA_RAW: Path = Path("data") / COMP / "raw"
DATA_INTERIM: Path = Path("data") / COMP / "interim"
DATA_FEATURES: Path = Path("data") / COMP / "features"
EXPERIMENTS_DB: Path = Path(_cfg.get("experiments_db", "data/experiments.db"))
