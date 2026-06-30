---
name: execute-task
description: 公式 Explore→Plan→Implement→Commit で SPEC.md・docs/tasks の作業を実行する
---

# タスク実行（公式 Explore → Plan → Implement → Commit）

root `SPEC.md`（スペックがある場合）または `docs/tasks/` の作業を実装する。Claude Code 公式の実行ワークフローに従う（出典: code.claude.com/docs/en/best-practices）。スペック駆動の作業は、スペックを書いたセッションではなく**新しいセッション**で実行するのが公式の前提。

## 手順

1. **Explore** — 編集前に、`SPEC.md` / タスクファイルとリンク先ドキュメント・対象コードを読む。先にコードを書かない。
2. **Plan** — 中規模以上、または構造的な作業では、ロジックを書く前に `skeleton-first` スキルを回して責務配置と変更範囲を固定する。
3. テスト・静的解析・対象を絞った確認で現状の挙動を把握する。
4. **Implement** — 小さなステップで実装する。挙動の変更は `SPEC.md` の「Docs to update」と `docs/03_domain_model.md` ほか連動 docs に整合させる（drift 防止）。API・DB・CLI・運用の変更に応じてテスト/ドキュメントを更新する。
5. `Makefile` の関連チェックを実行する。
6. **E2E 検証** — `SPEC.md` 末尾の検証ステップ（または acceptance criteria）を実際に実行して通す。
7. **Commit** — 検証が通ってから、説明的なメッセージでコミットする。SPEC.md の確定内容は `docs/01〜08` / `docs/adr/` へ昇格し、タスクは done に移動 / マークする。

## 安全

- 秘密情報・プライベートなパス・トークン・生成レポート・生の運用データを露出させない。
- ユーザーが明示的に求めない限り、破壊的なコマンドを実行しない。
