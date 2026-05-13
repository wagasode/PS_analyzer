# Web UI日本語化計画

## 背景

現状のダッシュボードは `<html lang="ja">` で生成され、日付表示も `ja-JP` を使っている一方、画面上の主要なUI文字列は英語のままになっている。日本人ユーザーが利用する前提で、静的ダッシュボードの表示文言を日本語化する。

この計画では実装は行わず、既存構造と実装範囲を整理する。

## 現状のUI文字列の配置

### `scripts/build_streaming_dashboard.py`

Web UI本体は `HTML = """..."""` の大きなHTMLテンプレートとして定義され、`write_html()` で `public/index.html` に書き出される。現状の表示文字列はこのテンプレート内のHTMLとJavaScriptに集中している。

- 静的HTML
  - `<title>Streaming Report</title>`
  - `<h1>Streaming Report</h1>`
  - JSONリンク: `Team JSON`, `Player JSON`, `Timeline JSON`, `Deck JSON`
  - ワークフローリンク: `Workflow run`
  - サマリー見出し: `Teams`, `Players`, `Streams`, `Total hours`, `SV hours`
  - タブ: `By team`, `By player`, `By deck`
  - 検索placeholder: `Filter by team, player, deck, or status`
  - 変更バー: `No unsaved changes.`, `Save changes`, `Review changes`, `Clear draft`
  - テーブル/タイムライン/空表示: `By team`, `Show details`, `0 rows`, `No matching rows.`, `Player timeline`, `0 streams`, `No stream archives collected.`
  - 保存モーダル: `Save deck edits`, `Close`, `Save target`, `Save changes`
  - デッキ編集モーダル: `Edit archive decks`, `Linked decks`, `Add existing deck`, `Search decks`, `Create new deck`, `Deck name`, `Advanced input`, `Deck key`, `Class`, `Archetype`, `Deck URL`, `Deck code`, `Notes`, `Create and link`

- JS内のテーブル列定義
  - `columns` に `Team`, `Streams`, `Total hours`, `SV hours`, `YouTube hours`, `Twitch hours`, `Player`, `Timeline`, `YouTube reason`, `Twitch reason`, `Deck`, `Class`, `Archetype`, `Usage`, `Players` が定義されている。

- JS内の動的表示
  - 数値: `Intl.NumberFormat("en-US", ...)`
  - 日付: `Intl.DateTimeFormat("ja-JP", ...)`
  - 未設定/不明表示: `Unknown`, `Unknown player`, `No thumbnail`, `Open archive`
  - 時間表記: `1h 05m`, `5m`
  - 下書き変更: `New deck`, `Linked`, `Unlinked`, `Updated link`, `Unknown archive`, `unsaved draft change(s)`
  - バリデーション: `Deck key is required.`, `Deck name is required...`, `Duplicate deck key...` など
  - 保存処理: `Repository or branch metadata is missing.`, `Changes will be sent...`, `Saving changes...`, `Saved. Run Collect streaming data...`, `Save failed...`
  - 表示件数: `${rows.length} rows`, `${streams.length} streams`
  - タイムライン: `Started`, `Published`, `Date unknown`, `Untitled stream`, `Shadowverse`, `Open archive`, `Edit decks`
  - デッキ利用: `Deck usage`, `No deck selected.`, `No stream archives linked.`
  - デッキ編集: `Class guess...`, `No linked decks.`, `Confidence`, `Display order`, `Note`, `Details`, `Hide details`, `Unlink`, `No existing decks found.`, `Linked`, `Add`
  - 読み込み失敗: `Failed to load report data.`

### `scripts/build_streaming_report.py`

GitHub Actionsのジョブサマリーに出すMarkdown文字列が英語で定義されている。

- `Streaming report`
- `By team`
- `By player`
- `_No rows._`
- `_Showing top ... Download the CSV artifact for the full table._`

これは公開Web UIではないが、CI上で人間が読む表示文言のため、別issueで日本語化対象にできる。

### `scripts/fetch_youtube_archives.py`

YouTube収集結果のGitHub Actionsサマリーが英語で定義されている。

- `YouTube archive fetch`
- `Channels checked`
- `Videos seen`
- `Rows upserted`
- `Skipped channels`
- `Team`, `Player`, `Identifier`, `Reason`, `Detail`

公開Web UIではないため、初回のWeb UI日本語化からは切り離す。

### `workers/save-deck-links/worker.mjs`

保存APIのJSONエラーメッセージが英語で定義されている。ダッシュボードの保存失敗時に `Save failed: ...` としてブラウザに表示される可能性がある。

- `Method not allowed.`
- `Origin is not allowed.`
- `Request body is too large.`
- `repository must be owner/repo.`
- `ALLOWED_REPOSITORY is not configured.`
- `branch is not allowed.`
- `decks_csv has an invalid CSV header.`
- `GitHub API request failed with status ...`

APIレスポンス仕様の一部でもあるため、初回はダッシュボード側の接頭辞や一般メッセージを日本語化し、Workerのエラー本文は別issueで扱うのが安全。

### `.github/workflows/*.yml`

GitHub Actionsのステップ名、input説明、ジョブサマリー文言に英語が残っている。

- `Collect streaming data`
- `Publish dashboard`
- `Compile scripts`
- `Build reports`
- `Build dashboard`
- `The dashboard will be published...`

開発者向け/運用者向けの表示であり、Web UI表示とは分けて扱う。

### `README.md` / `CONTRIBUTING.md`

READMEは英語中心、CONTRIBUTINGは日本語中心。今回の「Web UI日本語化」からは対象外とする。

## 既存のi18n構造の有無

専用のi18n構造はない。

- localeファイル、翻訳辞書、`data-i18n` 属性、言語切り替え、翻訳関数は存在しない。
- `scripts/build_streaming_dashboard.py` のHTMLテンプレートに表示文字列が直接埋め込まれている。
- ただし、既に日本語利用を意識した箇所はある。
  - `<html lang="ja">`
  - `Intl.DateTimeFormat("ja-JP", ...)`
  - `localeCompare(..., "ja")`
  - クラス推定用の日本語デッキ名エイリアス
  - データCSV内の日本語選手名/メモ
- 数値表示は `en-US` のままなので、日本語化時に `ja-JP` へ寄せる候補になる。

## 日本語化対象

初回実装では、公開ダッシュボードでユーザーに見える文言を優先する。

- ページタイトル、メイン見出し、メタ情報
- サマリーカードのラベル
- タブ、検索placeholder、テーブルタイトル、表示件数、空状態
- テーブル列名
- ステータス表示
  - `ok`, `skipped`, `failed`, `no_channel`, `not_checked`, `unknown`
  - raw値は変えず、表示ラベルだけ日本語化する。
- タイムライン/デッキ利用パネル
  - 日付種別、未タイトル、未サムネイル、アーカイブを開く、デッキ編集など
- デッキ編集モーダル
  - セクション見出し、入力ラベル、ボタン、検索結果、詳細開閉、未リンク表示
  - `confidence` の保存値 `low/medium/high` は維持し、optionの表示ラベルだけ日本語化する。
- 下書き変更/保存モーダル
  - 変更件数、保存先、保存中、保存完了、保存失敗、API未設定、バリデーションエラー
- 表示フォーマット
  - 数値: `ja-JP`
  - 時間: `1時間05分`, `5分` など日本語UIに合う表記
  - 件数: `3件`, `2配信` など文脈に合う表記

## 対象外にすべきもの

初回実装で翻訳しないもの。

- JSON/CSV/SQLiteのフィールド名
  - `team`, `player_name`, `stream_count`, `deck_key` などはデータ契約なので維持する。
- ファイル名、URL、API payload key
  - `data/streaming_by_team.json`, `decks_csv`, `stream_session_decks_csv` など。
- HTMLのid/class/data属性
  - JSの参照とCSSに影響するため維持する。
- GitHub workflow名、ブランチ名、環境変数名、secret/variable名
  - `Collect streaming data`, `SAVE_API_ENDPOINT`, `GITHUB_REPOSITORY` など。
- YouTube/Twitchなどのサービス名、Shadowverseなどの固有名詞
- プレイヤー名、チーム名、配信タイトル、デッキ名、メモなど外部/入力データ由来の値
- CSVマスタの列名と既存データ値
  - 日本語化すると既存スクリプトや保存APIに影響する。
- WorkerのAPIエラー本文
  - UIから露出する可能性はあるが、API仕様変更になるため別issueで扱う。
- README全体の日本語化
  - Web UI日本語化とは別スコープにする。

## 影響ファイル

初回のWeb UI日本語化で変更する可能性が高いファイル。

- `scripts/build_streaming_dashboard.py`
  - 主対象。静的HTML、JSラベル、動的メッセージ、format関数を更新する。

必要に応じて追加する可能性があるファイル。

- `docs/plans/ja-localization.md`
  - この計画書。
- `README.md`
  - 日本語化実装後の確認方法を追記する場合のみ。初回では必須ではない。

別issueで扱う候補。

- `scripts/build_streaming_report.py`
  - GitHub Actionsサマリーの日本語化。
- `scripts/fetch_youtube_archives.py`
  - YouTube収集サマリーの日本語化。
- `.github/workflows/collect-streams.yml`
  - workflow input説明、ステップ名、ダッシュボードURLサマリーの日本語化。
- `.github/workflows/publish-dashboard.yml`
  - publishサマリーの日本語化。
- `workers/save-deck-links/worker.mjs`
  - 保存APIエラー本文の日本語化、またはエラーコード化。

## 実装方針

### 1. まずは単一言語の日本語UIとして実装する

このリポジトリには言語切り替え要件がなく、既に `<html lang="ja">` で出力されている。そのため初回は大きなi18n基盤を追加せず、既存の単一HTMLテンプレートを日本語表示にする。

ただし、JS内に同じ文言が複数回出るため、保存/空状態/ステータスなど再利用頻度が高い文言は小さな定数オブジェクトにまとめる。

### 2. データ契約は変更しない

CSVヘッダー、JSONフィールド、SQLiteスキーマ、保存API payload、`confidence` の保存値、`platform` 値は変更しない。表示ラベルだけを日本語化する。

### 3. 表示ラベルの変換関数を追加する

候補:

- `statusLabel(value)`
  - `ok` -> `正常`
  - `skipped` -> `スキップ`
  - `failed` -> `失敗`
  - `no_channel` -> `チャンネルなし`
  - `not_checked` -> `未確認`
  - `unknown` -> `不明`
- `confidenceLabel(value)`
  - `low` -> `低`
  - `medium` -> `中`
  - `high` -> `高`
  - 空文字 -> `未設定`
- `formatCount(count, unit)`
  - `0件`, `3行`, `2配信` などの統一。
- `formatDuration(totalSeconds)`
  - `1時間05分`, `5分` などに変更。

### 4. 検索・ソート・保存挙動は維持する

検索対象は現状 `JSON.stringify(row).toLowerCase()` なので、データ値の検索挙動は維持される。日本語化したラベルで検索できるようにするかは別途判断が必要。初回は挙動変更を避け、表示文言のみを主対象にする。

### 5. UIの折り返しを確認する

日本語文言は英語より短いものも長いものもある。特にボタン、サマリーカード、モーダルヘッダー、変更バーは表示崩れが起きやすいため、生成後の `public/index.html` をデスクトップ幅とモバイル幅で確認する。

### 6. 将来の多言語化に備えるなら後続issueで行う

もし英語/日本語切り替えが必要になった場合は、今回の単一日本語化とは別に、翻訳辞書や言語選択を設計する。その場合は `scripts/build_streaming_dashboard.py` のHTMLテンプレートを分割するか、JS側に `messages` 辞書を持たせる。

## issue分割案

### Issue 1: 公開ダッシュボードの基本表示を日本語化する

対象:

- `scripts/build_streaming_dashboard.py`
- ページ見出し、サマリー、タブ、検索、テーブル列、空状態、タイムライン、デッキ利用パネル
- 数値/日付/時間/件数フォーマット

対象外:

- デッキ編集/保存モーダルの詳細文言
- Worker/APIエラー本文
- GitHub Actionsサマリー

### Issue 2: デッキ編集と保存フローの表示を日本語化する

対象:

- デッキ編集モーダル
- 既存デッキ検索
- 新規デッキ作成
- リンク詳細、confidence表示
- 下書き変更一覧
- 保存モーダル、保存状態、バリデーションエラー

注意:

- 保存payloadとCSV値は変更しない。
- APIから返る英語エラーはこのissueでは翻訳ラップに留めるか、原文併記にする。

### Issue 3: GitHub Actionsサマリーを日本語化する

対象:

- `scripts/build_streaming_report.py`
- `scripts/fetch_youtube_archives.py`
- `.github/workflows/collect-streams.yml`
- `.github/workflows/publish-dashboard.yml`

注意:

- workflow名を変える場合、`workflow_run.workflows` の参照に影響するため慎重に扱う。

### Issue 4: 保存APIのエラー表示方針を整理する

対象:

- `workers/save-deck-links/worker.mjs`
- ダッシュボード側の保存失敗表示

方針候補:

- Workerは `error_code` を返し、UI側で日本語メッセージへ変換する。
- 既存の `error` 文字列は後方互換のため残す。
- GitHub API由来の詳細エラーは原文併記にする。

## Acceptance criteria

初回実装issueの完了条件。

- 生成された `public/index.html` の公開ダッシュボードで、主要な画面表示が日本語になっている。
- ページタイトル、見出し、サマリーカード、タブ、検索placeholder、テーブル列名、表示件数、空状態、タイムライン、デッキ利用パネルの英語UI文言が残っていない。
- `YouTube`, `Twitch`, `Shadowverse`, `SV`, JSONリンク、URL、ファイル名、ブランチ名、workflow名、データ由来の配信タイトル/選手名/チーム名は翻訳対象外として維持されている。
- CSV/JSON/SQLite/API payloadのフィールド名や保存値は変更されていない。
- デッキ編集や保存機能を対象に含めるissueでは、保存payloadの形とCSVヘッダーが既存と同じである。
- `python3 -m py_compile scripts/*.py` が成功する。
- `python3 scripts/init_db.py`、`python3 scripts/import_deck_links.py`、`python3 scripts/build_streaming_report.py`、`python3 scripts/build_streaming_dashboard.py` がローカルで成功する。
- 生成されたダッシュボードで、チーム別/選手別/デッキ別の切り替え、検索、ソート、タイムライン表示が動作する。
- デスクトップ幅とモバイル幅で、主要ボタンや見出しの日本語テキストが崩れず表示される。

## Test plan

実装時の確認手順。

1. Python構文チェック

   ```bash
   python3 -m py_compile scripts/*.py
   ```

2. ローカル生成

   ```bash
   python3 scripts/init_db.py
   python3 scripts/import_deck_links.py
   python3 scripts/build_streaming_report.py
   python3 scripts/build_streaming_dashboard.py
   ```

3. 生成物の文字列確認

   ```bash
   rg -n "Streaming Report|Loading|By team|By player|By deck|No matching|Save changes|Edit decks|Open archive|Total hours|Players|Streams" public/index.html
   ```

   許容する英語固有名詞やファイル名を除き、画面表示用の英語が残っていないことを確認する。

4. ブラウザ確認

   ```bash
   python3 -m http.server --directory public 8000
   ```

   `http://localhost:8000/` を開き、以下を確認する。

   - 初期表示
   - チーム別/選手別/デッキ別タブ
   - 検索
   - テーブルソート
   - 選手タイムライン
   - デッキ利用パネル
   - デッキ編集モーダル
   - 保存API未設定時の表示

5. レスポンシブ確認

   - デスクトップ幅
   - タブレット幅
   - モバイル幅

6. PR後の確認

   - 対象ブランチで `Collect streaming data` workflowを手動実行する。
   - dashboard previewで日本語表示、検索、ソート、タイムラインを確認する。

## GitHub issue本文案

```md
## 背景

現状の公開ダッシュボードは `<html lang="ja">` で生成され、日付表示も `ja-JP` ですが、画面上の主要なUI文字列は英語のままです。日本人ユーザーが利用する前提で、Web UIの表示を日本語化したいです。

## 対象

- `scripts/build_streaming_dashboard.py` で生成している公開ダッシュボードの表示文言
- ページタイトル、見出し、サマリーカード
- タブ、検索placeholder、テーブルタイトル、テーブル列名、表示件数、空状態
- ステータス表示
- 選手タイムライン、デッキ利用パネル
- 必要に応じて数値/時間/件数フォーマット

## 対象外

- CSV/JSON/SQLite/API payloadのフィールド名
- HTMLのid/class/data属性
- URL、ファイル名、環境変数名、ブランチ名
- YouTube/Twitch/Shadowverse/SVなどの固有名詞
- プレイヤー名、チーム名、配信タイトル、デッキ名、メモなどデータ由来の値
- WorkerのAPIエラー本文
- GitHub Actionsサマリー
- README全体の日本語化

## 方針

- まずは単一言語の日本語UIとして実装する。
- 大きなi18n基盤や言語切り替えは追加しない。
- ただし、ステータスや保存メッセージなど再利用される文言は小さな定数/変換関数にまとめる。
- データ契約は変更せず、表示ラベルだけを日本語化する。
- `confidence` など保存値が `low/medium/high` のものは値を維持し、optionの表示だけ日本語化する。

## Acceptance criteria

- [ ] 生成された `public/index.html` の公開ダッシュボードで、主要な画面表示が日本語になっている。
- [ ] ページタイトル、見出し、サマリーカード、タブ、検索placeholder、テーブル列名、表示件数、空状態、タイムライン、デッキ利用パネルの英語UI文言が残っていない。
- [ ] `YouTube`, `Twitch`, `Shadowverse`, `SV`, JSONリンク、URL、ファイル名、ブランチ名、workflow名、データ由来の配信タイトル/選手名/チーム名は翻訳対象外として維持されている。
- [ ] CSV/JSON/SQLite/API payloadのフィールド名や保存値は変更されていない。
- [ ] チーム別/選手別/デッキ別の切り替え、検索、ソート、タイムライン表示が引き続き動作する。
- [ ] デスクトップ幅とモバイル幅で、主要ボタンや見出しの日本語テキストが崩れず表示される。

## Test plan

- [ ] `python3 -m py_compile scripts/*.py`
- [ ] `python3 scripts/init_db.py`
- [ ] `python3 scripts/import_deck_links.py`
- [ ] `python3 scripts/build_streaming_report.py`
- [ ] `python3 scripts/build_streaming_dashboard.py`
- [ ] `public/index.html` 内に対象外ではない英語UI文言が残っていないことを確認する。
- [ ] ローカルサーバーまたはdashboard previewで、初期表示、タブ切り替え、検索、ソート、タイムライン、デッキ利用パネルを確認する。
```
