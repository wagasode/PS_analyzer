## Temporary file rules

- PR本文やissue本文の一時ファイルは `/private/tmp` ではなく `.codex/tmp/` に作成する。
- `.codex/tmp/` はgit追跡しない。
- `gh pr create` では `--body-file .codex/tmp/pr_body.md` を使う。
- `gh pr edit` では `--body-file .codex/tmp/pr_body_ja.md` のように `.codex/tmp/` 配下の一時ファイルを使う。
- PR本文を作成・編集する前に、本文が日本語であることを確認する。