#!/usr/bin/env python3
"""Kaggle コンペのローカル初期環境を1コマンドでセットアップする

使い方: make init COMP=house-prices-advanced-regression-techniques
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
KAGGLE_BIN = Path(sys.executable).parent / "kaggle"


def download(comp: str, raw_dir: Path) -> None:
    print(f"[init] ① {comp} をダウンロード中 ...")
    result = subprocess.run(
        [str(KAGGLE_BIN), "competitions", "download",
         "-c", comp, "-p", str(raw_dir)],
    )
    if result.returncode != 0:
        print(
            f"\n[init] ダウンロード失敗。\n"
            f"  rules 未同意の場合: https://www.kaggle.com/c/{comp}/rules"
        )
        sys.exit(1)

    for zf in list(raw_dir.glob("*.zip")):
        print(f"  展開: {zf.name}")
        with zipfile.ZipFile(zf) as z:
            z.extractall(raw_dir)
        zf.unlink()


def _find_csv(raw_dir: Path, keyword: str, exclude: str | None = None) -> Path | None:
    candidates = [
        p for p in raw_dir.rglob("*.csv")
        if keyword in p.stem.lower()
        and (exclude is None or exclude not in p.stem.lower())
    ]
    return max(candidates, key=lambda p: p.stat().st_size) if candidates else None


def normalize(raw_dir: Path) -> tuple[Path, Path]:
    print("\n[init] ② ファイル配置を正規化中 ...")
    train_src = _find_csv(raw_dir, "train")
    test_src = _find_csv(raw_dir, "test", exclude="sample")

    if train_src is None or test_src is None:
        all_csv = sorted(
            [p for p in raw_dir.rglob("*.csv") if "sample" not in p.stem.lower()],
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if len(all_csv) >= 2:
            train_src = train_src or all_csv[0]
            test_src = test_src or all_csv[1]

    dst_train = raw_dir / "train.csv"
    dst_test = raw_dir / "test.csv"

    for src, dst, label in [(train_src, dst_train, "train"), (test_src, dst_test, "test")]:
        if src is None:
            print(f"  {label}: 見つかりませんでした（手動で配置してください）")
        elif src.resolve() == dst.resolve():
            print(f"  {label}: {src.name} （移動不要）")
        else:
            shutil.copy2(src, dst)
            print(f"  {label}: {src.relative_to(raw_dir)} → {dst.name}")

    return dst_train, dst_test


def analyze(train_path: Path, test_path: Path) -> None:
    print("\n[init] ③ データ分析中 ...")
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path) if test_path.exists() else None

    print(f"\n  shape : train={train.shape}"
          + (f", test={test.shape}" if test is not None else ""))

    train_cols = set(train.columns)
    test_cols = set(test.columns) if test is not None else set()
    target_candidates = sorted(train_cols - test_cols)
    id_candidates = [c for c in (test_cols or train_cols) if "id" in c.lower()]

    print("\n  TARGET 候補（train にあって test にない列）:")
    for col in target_candidates:
        dtype = str(train[col].dtype)
        nuniq = train[col].nunique()
        miss = train[col].isna().mean() * 100
        print(f"    {col:<30} dtype={dtype:<10} nunique={nuniq:<6} missing={miss:.1f}%")

    print(f"\n  ID 候補: {id_candidates or ['(なし)']}")

    miss_top = train.isna().mean()
    miss_top = miss_top[miss_top > 0].sort_values(ascending=False).head(5)
    if not miss_top.empty:
        print("\n  欠損率 TOP5:")
        for col, rate in miss_top.items():
            print(f"    {col:<30} {rate * 100:.1f}%")

    target = target_candidates[0] if len(target_candidates) == 1 else None
    objective, metric = "regression", "rmse"
    if target:
        nuniq = train[target].nunique()
        if nuniq == 2:
            objective, metric = "binary", "auc"
        elif nuniq <= 20:
            objective, metric = "multiclass", "logloss"

    draft = {
        "comp": train_path.parent.parent.name,
        "target": target or "REPLACE_ME",
        "id_col": (id_candidates[0] if id_candidates else None),
        "objective": objective,
        "metric": metric,
        "n_folds": 5,
        "seed": 42,
        "experiments_db": "data/experiments.db",
    }
    print("\n  ─── conf/config.yaml 下書き ─────────────────────────")
    for line in yaml.dump(draft, allow_unicode=True, default_flow_style=False).splitlines():
        print(f"    {line}")
    print("  ──────────────────────────────────────────────────────")


def create_doc(comp: str) -> None:
    print("\n[init] ④ コンペドキュメントを生成中 ...")
    template = ROOT / "docs" / "competitions" / "_template.md"
    dest = ROOT / "docs" / "competitions" / f"{comp}.md"
    if dest.exists():
        print(f"  既存: docs/competitions/{comp}.md （スキップ）")
        return
    content = template.read_text()
    content = content.replace("# [コンペ名]", f"# {comp}")
    content = content.replace("<slug>", comp)
    dest.write_text(content)
    print(f"  作成: docs/competitions/{comp}.md")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: make init COMP=<competition-slug>")
        sys.exit(1)

    comp = sys.argv[1]
    raw_dir = ROOT / "data" / comp / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    download(comp, raw_dir)
    normalize(raw_dir)
    analyze(raw_dir / "train.csv", raw_dir / "test.csv")
    create_doc(comp)

    print(f"""
[init] 完了。次のステップ:
  1. conf/config.yaml を上記の下書きで更新
  2. rm -rf data/{comp}/interim/ data/{comp}/features/
  3. make run
""")


if __name__ == "__main__":
    main()
