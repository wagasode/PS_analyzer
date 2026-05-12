# Contribution Workflow

このリポジトリでは、原則としてすべての変更を GitHub Issue に紐づけたブランチで行います。

## 基本ルール

- `main` へ直接変更を入れない。
- 作業を始める前に、対応する issue を用意する。
- 1つの issue に対して、原則1つの作業ブランチを作る。
- ブランチ名は issue の内容が分かる短い名前にする。
- 作業完了後は Pull Request を作成し、issue と PR を相互に参照する。

## 標準フロー

1. Issue を作成する

   目的、背景、スコープ、完了条件を issue に書く。

2. 最新の `main` からブランチを切る

   ```bash
   git switch main
   git pull
   git switch -c codex/issue-<issue-number>-<short-description>
   ```

   issue 番号がまだ無い場合は、短い説明だけでもよい。

   ```bash
   git switch -c codex/<short-description>
   ```

3. ブランチ上で実装する

   変更範囲は issue のスコープに合わせる。別の問題を見つけた場合は、同じブランチで広げず、必要に応じて別 issue に分ける。

4. ローカルで検証する

   変更内容に応じて、最低限の確認コマンドを実行する。

   ```bash
   python3 -m py_compile scripts/*.py
   ```

   集計処理を触った場合は、必要に応じて以下も確認する。

   ```bash
   python3 scripts/build_streaming_report.py
   python3 scripts/build_streaming_dashboard.py
   ```

5. Pull Request を作成する

   PR 本文には、対応 issue、変更内容、検証結果を書く。

   ```md
   Closes #<issue-number>
   ```

## ブランチ命名

推奨形式:

```text
codex/issue-<issue-number>-<short-description>
```

例:

```text
codex/issue-12-dashboard-pages
codex/issue-18-twitch-fetch-retry
codex/update-branch-workflow-docs
```

## 例外

次のような小さな変更でも、可能な限り issue とブランチを作る。

- README の軽微な修正
- typo 修正
- CI 設定の小さな調整

ただし、緊急の復旧対応などで先に修正が必要な場合は、後から issue と PR に経緯を記録する。

## 禁止事項

- `main` 上で実装を進めること。
- 複数の無関係な issue を1つのブランチに混ぜること。
- issue の完了条件に含まれない大きなリファクタリングを同時に行うこと。
- 生成物だけを目的なくコミットすること。
