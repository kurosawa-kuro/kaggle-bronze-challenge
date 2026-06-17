---
name: create-task
description: docs/tasks 配下に、仕様化せずに残る形のタスクノートを作る
---

# タスク作成

`docs/tasks/` 配下に、焦点を絞ったタスクファイルを1つ作る。

## ルール

- ユーザーが明確に active と言わない限り `docs/tasks/backlog/` を使う。
- 進行中、または次に実行するものは `docs/tasks/active/` を使う。
- `docs/tasks/done/` は完了したタスクノートだけに使う。
- 正本の挙動を重複させない。代わりに `docs/specs/`、`docs/adr/`、`docs/runbooks/` へリンクする。
- タスクファイル名は `YYYY-MM-DD-topic.md` にする。
- 秘密情報・プライベートなパス・認証情報・ログ・個人の運用データを入れない。

## テンプレート

```markdown
# タスクタイトル

## Goal

## Context

## Scope

## Plan

## Acceptance Criteria
```
