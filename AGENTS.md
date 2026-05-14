# Codex workflow rules

## GitHub issue / PR rules

- GitHub issue / PR のタイトルと本文は、ユーザーが明示しない限り日本語で作成する。
- PR本文は見出しだけでなく、各セクション本文も日本語にする。
- PR作成前に本文ファイルを確認し、英語中心なら日本語に直してから `gh pr create` する。
- PR作成時は `gh pr create --repo wagasode/PS_analyzer --base main ...` のように `--repo` と `--base main` を明示する。
- issueを解決するPRでは `Closes #<issue-number>` を含める。
- mergeはユーザーが明示的に指示するまで行わない。

## Temporary file rules

- 一時的な検証用スクリプト、fixture、PR本文、issue本文は `.codex/tmp/` に作成する。
- `.codex/tmp/` はgit追跡しない。
- 一時ファイルをPR差分に含めない。
- `gh pr create` では `--body-file .codex/tmp/pr_body.md` のように `.codex/tmp/` 配下の本文ファイルを使う。
- `gh pr edit` では `--body-file .codex/tmp/pr_body_ja.md` のように `.codex/tmp/` 配下の本文ファイルを使う。
- 一時スクリプト内で `git push`, `gh pr edit`, `gh pr merge`, `rm -rf` など外部状態や破壊的変更を伴う操作をしない。
- 作業完了時に、一時ファイルの目的、実行コマンド、生成物、PR差分に含まれていないことを報告する。
