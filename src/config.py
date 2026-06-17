"""コンペ切り替え時はここだけ変更する。"""
from pathlib import Path
import yaml

_cfg = yaml.safe_load((Path(__file__).parent.parent / "env" / "config.yaml").read_text())

TARGET: str = _cfg["target"]
ID_COL: str | None = _cfg["id_col"]
OBJECTIVE: str = _cfg["objective"]   # regression / binary / multiclass
METRIC: str = _cfg["metric"]         # rmse / auc / logloss / mape

N_FOLDS: int = _cfg["n_folds"]
SEED: int = _cfg["seed"]

DATA_RAW: Path = Path(_cfg["data_raw"])
DATA_INTERIM: Path = Path(_cfg["data_interim"])
EXPERIMENTS_DB: Path = Path(_cfg["experiments_db"])
