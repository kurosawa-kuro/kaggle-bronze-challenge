---
name: project-review
description: プロジェクトの構成・ドキュメント・責務境界・不足テストをレビューする
---

# プロジェクトレビュー

構造的な変更を提案する前に、プロジェクトをレビューする。

## 手順

1. まず `README.md`、`CLAUDE.md`、`AGENTS.md`、`docs/00_index.md`、関連 spec を読む。
2. `rg --files` でリポジトリ構成を確認し、主要なエントリポイントを特定する。
3. モジュールを責務に対応づける: domain、application/usecase、ports、adapters、infrastructure、UI、DB、外部 I/O。
4. まず重大度順に、ファイルパスと具体的な根拠つきで findings を報告する。
5. 確定した事実と仮説を分ける。モジュール・コマンド・実行時挙動を捏造しない。

## 出力

- Findings
- 責務マップ
- 境界の問題
- テスト / ドキュメントの不足
- 推奨する次のアクション
