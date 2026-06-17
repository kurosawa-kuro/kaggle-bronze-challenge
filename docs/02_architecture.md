# 02 アーキテクチャ

## 概要

```text
入力
  -> アプリケーション
  -> 出力
```

## 構成要素

| 構成要素 | 役割 | 担当パス |
|---|---|---|
| TODO | TODO | TODO |
| エージェントガイド | Codex / 他エージェント向けの repo ガイド | `AGENTS.md` |
| Claude ガイド | Claude Code の司令ルール | `CLAUDE.md` |
| タスク文書 | 一回性の作業計画・実装タスク | `docs/tasks/` |
| Claude skills | Claude Code で繰り返し使う作業手順 | `.claude/skills/` |

## 境界

- ソースコードは、別の境界を定義しない限り `src/` 配下に置く。
- 非機密の設定は `env/config.yaml` に置く。
- ローカル秘密情報は ignore したまま。共有・本番の秘密情報は Doppler などの secret manager に置く。
- Codex が `.claude/rules/` や `.claude/skills/` を読む前提にしない。Codex / 他エージェント向けに永続させたい指針は `AGENTS.md` に置く。

## 関連タスク

- 構造変更、責務移動、adapter 追加、共通化は、実装前に `docs/tasks/active/` へ task を作る。
- 中規模以上の変更では、task に Skeleton / Plan / Acceptance Criteria を書いてから実装する。
- 確定した設計判断は task から `docs/adr/` またはこの文書へ昇格する。
