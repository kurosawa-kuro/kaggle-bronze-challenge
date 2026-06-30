---
name: create-task
description: docs/tasks 配下に、仕様化せずに残る形のタスクノートを作る
---

# タスク作成

`docs/tasks/` 配下に、焦点を絞った**軽量な日次タスクノート**を1つ作る。

中規模以上の機能・実験・構造変更で、着手前に仕様を固めるべきものは、ここではなく `write-spec` スキルで root `SPEC.md` に自己完結スペックを書く（公式 spec-driven フロー）。

## ルール

- ユーザーが明確に active と言わない限り `docs/tasks/backlog/` を使う。
- 進行中、または次に実行するものは `docs/tasks/active/` を使う。
- `docs/tasks/done/` は完了したタスクノートだけに使う。
- 正本の挙動を重複させない。代わりに `SPEC.md`（着手前）、`docs/01〜08`、`docs/adr/` へリンクする。
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
