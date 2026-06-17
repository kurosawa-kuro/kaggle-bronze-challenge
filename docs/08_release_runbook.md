# 08 提出 Runbook

Kaggle における「リリース」= 最終提出ファイルの選択と提出。

## 提出前チェックリスト

```bash
make run      # 最終 CV Score を確認
make logs     # 全実験ログを確認し最良 run_id を特定
ls -lh submission.csv   # ファイルが存在し、サイズが正常なこと
head submission.csv     # ヘッダと値の形式を確認
```

確認項目:

- [ ] `submission.csv` のヘッダがコンペ規定と一致している
- [ ] 行数がテストデータの行数と一致している（`wc -l submission.csv`）
- [ ] 値に NaN / inf が含まれていない
- [ ] `data/experiments.db` に最終実験が記録されている

## 最終提出の選択（2本戦略）

Kaggle は締切までに 2 本の提出を選択できる（デフォルトは最終 2 提出）。

| 提出 | 選び方 |
|---|---|
| **提出 A** | CV Score が最良の実験 (`make logs` で確認) |
| **提出 B** | Public LB Score が最良の実験 |

両者が同じなら 1 本で問題ない。

## Kaggle CLI での提出

```bash
make submit COMP=<competition-name> MSG="exp001: lgbm baseline  CV=0.44498"
```

## コンペ切り替え手順

```bash
# 1. conf/config.yaml を更新
vim conf/config.yaml

# 2. 古いキャッシュを削除（Silver / Gold レイヤー）
rm -rf data/interim/ data/features/

# 3. Kaggle CLI でデータ取得
make download COMP=<competition-name>

# 4. 動作確認
make run
```

## ロールバック（前の実験に戻す）

```bash
# 過去のノートブック実験を再実行して submission.csv を上書き
make nb NB=exp001_lgbm_base
```

## 提出後タスク

- Public LB スコアと CV Score の差を `docs/tasks/active/` に記録する。
- 乖離が大きい場合（`|CV - LB| > 0.05`）は原因を調査してリーク防止策を `docs/06_error_policy.md` に追記する。
- 結果（ブロンズ取得 / 未達）と振り返りを task に残す。
