# 07 テスト戦略

## 方針

Kaggle パイプラインはノートブックファーストで速く回すことが優先。  
ユニットテストは最小限にとどめ、**`make run` が通ること**を最低品質ゲートとする。

## 品質ゲート

```bash
make run    # エラーなく完了し、submission.csv が生成されること
make logs   # 実験ログが記録されていること
```

## CV スコアによる品質判断

| 判断基準 | 目安 |
|---|---|
| CV std が安定している | `std < 0.015` を目安（不安定なら fold 数や seed を確認）|
| CV Score が改善している | 前回 run_id との比較で改善が確認できること |
| Public LB との乖離が小さい | `\|CV - LB\| < 0.05` を目安。大きい場合はリークを疑う |

## テスト範囲

| 範囲 | 手段 | 備考 |
|---|---|---|
| パイプライン結合 | `make run` | エラーなく完了すること |
| モデル切り替え | `make nb NB=exp002_catboost_base` | 同様にエラーなく完了すること |
| 実験ログ記録 | `make logs` | run_id と cv_score が記録されていること |
| FE 追加 | `make run` 後に CV Score を比較 | スコアが改善または維持されること |

## タスク完了条件

各 task は、完了前に以下を `Verification` に残す:

- 実行したコマンドと出力（CV Score）
- 前回との比較
- 実行できなかった検証と理由
- 残るリスク（Public LB との乖離等）

## Fold リーク検査

FE を追加した後、CV Score が不自然に高くなった場合はリークを疑う:

```python
# 検査: train と test で分布が揃っているか
print(X_train["new_feature"].describe())
print(X_test["new_feature"].describe())
```

## 関連タスク

- テスト追加や期待値変更が必要な場合は、task に理由を書き、仕様変更なら先に該当 docs を更新する。
