"""Collect a run_id artifact directory from GCS into outputs/runs."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download run artifacts from GCS")
    parser.add_argument("--config", default="configs/lgbm_baseline.yaml")
    parser.add_argument("--competition", "--comp", dest="competition", default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--project-config", default="env/project.yaml")
    parser.add_argument("--output-root", default="outputs/runs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_cfg = _load_yaml(Path(args.project_config))
    train_cfg = _load_yaml(Path(args.config))
    competition = args.competition or train_cfg.get("data", train_cfg).get("comp") or project_cfg.get("competition")
    bucket = args.bucket or project_cfg.get("gcsBucket")
    if not competition:
        raise SystemExit("[collect] competition is required")
    if not bucket:
        raise SystemExit("[collect] bucket is required via --bucket or env/project.yaml:gcsBucket")

    from utils.artifact_store import GcsPrefix, download_directory, latest_run_id

    run_id = latest_run_id(bucket, competition) if args.run_id == "latest" else args.run_id
    source = GcsPrefix(bucket=bucket, prefix=f"runs/{competition}/{run_id}")
    local_dir = Path(args.output_root) / competition / run_id
    downloaded = download_directory(source, local_dir)
    print(f"[collect] downloaded {len(downloaded)} files from {source.uri()} to {local_dir}")
    return 0


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


if __name__ == "__main__":
    raise SystemExit(main())
