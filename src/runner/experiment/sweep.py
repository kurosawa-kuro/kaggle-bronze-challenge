"""Fan out multiple configs as parallel Vertex Custom Jobs.

各 config を独立した Custom Job として**並列**投入する（共有 DB 不要）。
seed 平均は train.py 内で完結するので、sweep は「複数 config/ハイパラを同時に回す」用途。
非ブロッキング submit なので N 本投げても待たずに返る。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from runner.experiment.vertex_run import submit_from_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit multiple configs as parallel Vertex Custom Jobs")
    parser.add_argument("--configs", nargs="+", required=True, help="config yaml paths")
    parser.add_argument("--tag", default=None, help="run_id suffix to group this sweep")
    parser.add_argument("--image-uri", default=None)
    parser.add_argument("--machine-type", default=None)
    parser.add_argument("--spot", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    submitted: list[tuple[str, object]] = []
    for cfg in args.configs:
        run_id = f"{Path(cfg).stem}_{args.tag}" if args.tag else Path(cfg).stem
        result = submit_from_config(
            config_path=cfg,
            run_id=run_id,
            image_uri=args.image_uri,
            machine_type=args.machine_type,
            smoke=args.smoke,
            spot=args.spot,
            sync=False,
            dry_run=args.dry_run,
        )
        submitted.append((run_id, result))

    print(f"[sweep] {len(submitted)} jobs {'planned' if args.dry_run else 'submitted'}:")
    for run_id, result in submitted:
        print(f"  - {run_id}: {result if isinstance(result, str) else '(dry-run)'}")
    print("[sweep] collect each with: make collect CONFIG=<cfg> RUN_ID=<run_id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
