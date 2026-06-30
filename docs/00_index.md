# プロジェクトドキュメント索引

Kaggle ブロンズ取得を目的とした LightGBM 主軸・表形式データパイプラインの正本ドキュメント。`AGENTS.md` は Codex / 他エージェント向けの repo ガイド、`CLAUDE.md` は Claude Code の司令塔、`docs/tasks/` は毎日の作業計画・実装タスク・調査ログの実行ハブ、`.claude/skills/` は Claude Code で繰り返し使う作業手順。

## 権威順位

```text
コード / Makefile / config / manifests
> docs
> docs/tasks
> README / CLAUDE / AGENTS
> archive
```

## 毎日使う入口

| 入口 | 用途 |
|---|---|
| [tasks/README.md](./tasks/README.md) | 今日やること、次にやること、完了したことを管理する |
| [tasks/active/refactoring-candidates.md](./tasks/active/refactoring-candidates.md) | 常時見る cleanup / refactoring 候補 |
| [04_workflows.md](./04_workflows.md) | 作業開始、検証、リリース前確認のコマンド |
| [07_test_strategy.md](./07_test_strategy.md) | タスク完了前に通す品質ゲート |

`docs/tasks/` は仕様の正本ではないが、日々の実行順・証跡・未決事項の正本として扱う。着手前の機能スペックは root `SPEC.md`、確定した仕様は 01〜08 文書へ、判断理由は `docs/adr/` へ昇格する。

## ドキュメント一覧

| ドキュメント | 役割 |
|---|---|
| [01_requirements.md](./01_requirements.md) | 目的・範囲・ユーザー・ユースケース |
| [02_architecture.md](./02_architecture.md) | 構成要素・境界・実行モデル |
| [03_domain_model.md](./03_domain_model.md) | 用語・状態・ビジネス概念 |
| [04_workflows.md](./04_workflows.md) | ローカルコマンドと運用フロー |
| [05_data_model.md](./05_data_model.md) | データ・スキーマ・設定・永続化 |
| [06_error_policy.md](./06_error_policy.md) | エラー処理・リトライ・ログ |
| [07_test_strategy.md](./07_test_strategy.md) | テスト方針と品質ゲート |
| [08_release_runbook.md](./08_release_runbook.md) | リリース・マイグレーション・復旧 |
| [tasks/README.md](./tasks/README.md) | 日次運用の実行ハブ、作業計画、実装タスク |

着手前の機能スペックはリポジトリ直下の `SPEC.md`（公式 spec-driven フロー）。完了後は確定内容を 01〜08 / ADR へ昇格する。

## コンペ別記録

| ドキュメント | 内容 |
|---|---|
| [competitions/_template.md](./competitions/_template.md) | 新コンペ参加時のテンプレート |
| [competitions/california_housing.md](./competitions/california_housing.md) | パイプライン検証用（練習データ）・スコア履歴 |

新コンペに参加するときは `_template.md` をコピーして `competitions/<competition-slug>.md` を作成する。
