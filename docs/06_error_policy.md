# 06 エラー方針

## エラー分類

| 分類 | 意味 | 対応 |
|---|---|---|
| **データリーク（FE）** | 学習データ全体で fit し、テストに transform した | `encode()` / `add_*()` は必ず train データのみで fit する |
| **データリーク（CV）** | Fold 外の情報を使って学習した | KFold の分割後に fit する。Target Encoding は Fold 内で必ず行う |
| **Public LB 過学習** | CV Score は良いが Private LB で大幅ダウン | CV Score を主指標にする。LB スコアに引きずられない |
| **キャッシュ不整合** | `data/interim/` が古いまま残っている | コンペ切り替え時は `rm -rf data/interim/` してから `make run` |
| **設定ミスマッチ** | `config.yaml` の TARGET 列名がデータに存在しない | `make run` 実行直後のエラーメッセージで確認 |
| **パッケージ欠損** | venv にライブラリが入っていない | `make setup` を再実行する |

## Fold リーク防止の規則

```python
# NG: 学習データ全体で fit してから fold 分割
enc.fit(X_train_all)
for fold in folds:
    X_tr = enc.transform(X_tr)   # ← リーク

# OK: fold 内で fit
for fold in folds:
    enc.fit(X_tr)
    X_tr  = enc.transform(X_tr)
    X_val = enc.transform(X_val)  # ← fit は学習 fold のみ
```

Target Encoding を使う場合は必ず `category_encoders.TargetEncoder` を fold 内で fit する。

## ログ

- `[ingest]`, `[lgbm]`, `[catboost]`, `[xgboost]`, `[logger]`, `[score]` プレフィックスで標準出力に出る。
- 秘密情報（API トークン等）をログに出さない。
- 実験ログは `data/experiments.db` に永続化される（`make logs` で確認）。

## 関連タスク

- リーク・スコア異常は task に再現手順と原因を残してから修正する。
- 障害対応で得た恒久手順は `docs/runbooks/` へ昇格する。
