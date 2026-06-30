"""Submit a run artifact's submission.csv to Kaggle."""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import yaml


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit outputs/runs/.../submission.csv")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--competition", "--comp", dest="competition", default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--message", "--msg", dest="message", required=True)
    parser.add_argument("--output-root", default="outputs/runs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    competition = args.competition or cfg.get("data", cfg).get("comp")
    if not competition:
        raise SystemExit("[submit] competition is required")
    submission = Path(args.output_root) / competition / args.run_id / "submission.csv"
    if not submission.exists():
        raise SystemExit(f"[submit] missing submission: {submission}")
    cmd = [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        competition,
        "-f",
        str(submission),
        "-m",
        args.message,
    ]
    print("[submit] " + " ".join(cmd))
    # kaggle CLI に PYTHONPATH=src を渡すと自前モジュールが shadow されるため除去
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(cmd, check=False, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
