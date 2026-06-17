# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際の最小ガイド。

## Source of Truth

- Project overview: `README.md`
- Documentation index: `docs/00_index.md`
- Requirements: `docs/01_requirements.md`
- Architecture: `docs/02_architecture.md`
- Test strategy: `docs/07_test_strategy.md`
- Task notes: `docs/tasks/`

## コマンド

```bash
make setup    # 初期セットアップ (依存取得 + ビルド)
make build    # ビルド
make run      # 実行
make dev      # 開発サーバー / ホットリロード
make test     # テスト
make fmt      # フォーマット
make lint     # 静的解析
```

## アーキテクチャ

- ソースは `src/` 配下に置く。
- 非機密の設定は `env/config.yaml`、ローカル秘密情報は `env/secret.yaml`、チーム共有・本番クレデンシャルは Doppler (`doppler.yaml`) で管理する。
- 設計・運用ドキュメントは `docs/` 配下。権威順位と更新規約は `docs/00_index.md` に従う。
- パス別ルールは `.claude/rules/` 配下に置く。
- 一回性の作業計画は `docs/tasks/`、繰り返し使う作業手順は `.claude/skills/` に置く。

## 作業ルール

- 推測でコードを書かない。コマンドを書いたら実際に実行して確認する。
- 仕様変更は連動する `docs/` とテストを同一 PR で直す。drift を作らない。
- 既存の関数・ユーティリティ・パターンを優先的に再利用する。
- task note を仕様の正本にしない。確定内容は `docs/specs/`、`docs/adr/`、`docs/runbooks/` に昇格する。
