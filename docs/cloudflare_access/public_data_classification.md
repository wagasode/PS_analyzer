# 公開データ棚卸しと分類

## 位置づけ

この文書は #46「公開データ棚卸しと分類を行う」の調査結果です。#47、#50、#52 が参照できるように、現在の dashboard 生成物、`public/data/*.json`、deck/timeline 情報、preview / artifact / `gh-pages` 露出、将来の戦績データ候補を `公開可` / `チーム限定` / `保存不可` に分類します。

この文書では raw data の値を全文掲載しません。分類は field / key / 生成経路 / 公開面単位で記録します。

## 確認した状態

- 調査日: 2026-05-19
- source branch の `public/` は `.gitignore` 対象で、worktree には存在しない。
- `scripts/build_streaming_dashboard.py` は `public/index.html` と `public/data/*.json` を生成する。
- `origin/gh-pages` の現在ツリーには root の `index.html` と `data/*.json`、および preview 配下の dashboard 生成物が残っている。
- `origin/gh-pages` の現在ツリーでは preview directory が 15 個、root / preview の `index.html` と JSON 生成物が合計 94 ファイル確認できた。
- `origin/gh-pages` は履歴を持つ publish branch であり、現在のファイルを置き換えても過去 commit の内容は自動では消えない。

## 公開面ごとの分類

| 公開面 | 現在含まれるもの | 分類 | 判断 |
|---|---|---|---|
| source branch の `public/` | なし。生成物は gitignore 対象 | 公開可 | source branch に静的 dashboard 生成物を追跡しない現状は維持してよい |
| GitHub Pages root | `index.html` と `data/*.json` | チーム限定 | 現在は直URLで見えるが、生成済みJSONに分析結果、deck/timeline、保存API設定状態が含まれる。dataをfetchしないstubだけなら公開可にできる |
| GitHub Pages preview | `previews/<slug>/index.html` と `previews/<slug>/data/*.json` | チーム限定 | branch preview は merge前確認用であり、公開URLとして残すべきではない |
| `gh-pages` 現在ツリー | root と過去 preview の生成物 | チーム限定 | #47 で現在ツリーの停止・無害化対象にする |
| `gh-pages` 履歴 | 過去 publish commit の生成物 | チーム限定 | 現在ツリーを消しても履歴には残る。#47/#48 で履歴・repository visibility・branch retention の扱いを決める |
| Actions artifact `dashboard-site` | `public/` dashboard 一式 | チーム限定 | publish workflow への受け渡し用途。Access 外で長期参照する前提にしない |
| Actions artifact `streaming-data` | SQLite、reports CSV、`public/**` | チーム限定 | raw SQLite と reports を含むため、dashboard表示用JSONより広い情報を含み得る |
| GitHub Pages artifact | Pages deploy 用の site copy | チーム限定 | GitHub Pages 公開経路の一部として扱い、#47/#50 の移行対象に含める |

## `public/data/*.json` の分類

| ファイル | 主な key / field | 分類 | 判断 |
|---|---|---|---|
| `metadata.json` | `generated_at`, `workflow`, `run_number`, `run_id`, `run_url`, `commit_sha`, `repository`, `branch_name`, `save_api_endpoint`, 集計件数 | チーム限定 | run / branch / endpoint の運用情報を含む。集計件数だけを公開する場合も、public stub 用に別payload化する |
| `streaming_by_team.json` | `team`, `stream_count`, `total_hours`, `shadowverse_hours`, platform別時間 | チーム限定 | 元データは公開配信由来でも、チーム別の加工済み分析値として扱う |
| `streaming_by_player.json` | `team`, `player_name`, channel有無、platform別時間、channel status / skipped reason | チーム限定 | player名や公開チャンネル自体は公開情報でも、収集状態・skip理由・分析値は内部運用情報になる |
| `streaming_timeline_by_player.json` | player単位の `streams`、動画ID、title、URL、thumbnail、日時、deck link、`missing_deck_info`、`simulcast_streams` | チーム限定 | 公開動画へのリンク集でも、選手別の網羅的な収集結果とdeck未判定状態は内部分析に近い |
| `streaming_deck_usage.json` | deck metadata、`players`、deck別stream一覧、`source_note`, `confidence`, `display_order` | チーム限定 | deck採用状況、手入力メモ、根拠メモを含む。Access外に出さない |

### JSON内の値種別

| 値種別 | 分類 | 判断 |
|---|---|---|
| player名、team名、公開チャンネルURL、公開動画URL、thumbnail URL | 公開可 | 元の公開情報として単独掲載は可能。ただし dashboard の分析payloadに混在する場合は全体をチーム限定にする |
| stream title、配信日時、duration、platform、external stream id | 公開可 | 公開配信由来。ただし網羅的な収集・分類結果として出す場合はチーム限定にする |
| channel status、skipped reason、missing deck flag、Shadowverse関連判定 | チーム限定 | 収集品質や分析判断が見えるため、公開ページには出さない |
| deck key / deck name / class / archetype | チーム限定 | 公開decklist由来でも、内部の分析キーや採用状況と結びつくため限定扱いにする |
| deck URL / deck code | チーム限定 | deck情報としては共有可能な場合があるが、採用状況やstream紐付けと一体で扱うため限定扱いにする |
| `notes`, `source_note`, `confidence` | チーム限定 | 人手による根拠・補足・確信度であり、公開情報として扱わない |
| `save_api_endpoint` | チーム限定 | secret ではないが、保存APIの向き先を示す運用情報。public stub には含めない |
| API key、token、secret、Access JWT、cookie、認証header | 保存不可 | dashboard生成物、JSON、CSV、artifact、Git履歴のいずれにも保存しない |

## source CSV の分類

| ファイル | 主な field | 分類 | 判断 |
|---|---|---|---|
| `data/players_channels.csv` | team、player名、`x_handle`、YouTube/Twitch識別子、confidence、source URL、notes | チーム限定 | 公開情報を元にしていても、確認状況やnotesを含むため限定扱いにする |
| `data/decks.csv` | deck key/name、class、archetype、deck URL/code、notes | チーム限定 | dashboard編集対象であり、採用分析と紐づく |
| `data/stream_session_decks.csv` | platform、external stream id、deck key、confidence、source note、display order | チーム限定 | streamとdeckの紐付け、根拠、確信度が内部分析情報になる |

## SQLite / report / artifact の分類

| データ | 分類 | 判断 |
|---|---|---|
| `data/streams.sqlite` | チーム限定 | `stream_sessions`、`channels`、collection status、raw API payload を含むため、公開サイトの配布物にしない |
| `reports/*.csv` | チーム限定 | dashboard JSON の元になる集計・skip情報を含むため、公開download導線にしない |
| `public/**` artifact copy | チーム限定 | dashboard publish への中間成果物であり、GitHub Pages移行後はCloudflare Pages + Access側のみに流す |
| collector secrets / GitHub vars の値 | 保存不可 | secrets は検証時も名前と有無だけを扱い、値はdocs・artifact・JSONに残さない |

## 将来の戦績データ候補

将来の戦績管理は、原則として Cloudflare Access 配下でのみ閲覧・入力できる前提にする。

| データ候補 | 分類 | 判断 |
|---|---|---|
| 公開済み大会名、試合日、公式に公開された最終結果 | 公開可 | 公式公開情報として単独で扱う場合に限る |
| 自チーム選手、使用デッキ、クラス、アーキタイプ、勝敗、イベント文脈 | チーム限定 | 振り返り・対策用途の分析情報として扱う |
| 相手PN、相手CR / rank、相手デッキ、相手クラス / アーキタイプ | チーム限定 | 相手別分析に直結するため Access 外に出さない |
| 備考、チーム内メモ、確認ステータス、根拠URL、入力者、更新者 | チーム限定 | 運用・判断過程を含むため公開しない |
| 配信アーカイブやdeck情報との内部link key | チーム限定 | 公開情報へのlinkであっても、分析導線として限定扱いにする |
| API key、token、secret、cookie、Access認証情報 | 保存不可 | 保存先を問わず記録しない |
| 不要な個人情報、連絡先、DM本文、認証情報、目的外のセンシティブ情報 | 保存不可 | 戦績分析に不要な情報は収集・保存しない |

## 後続issueへの引き継ぎ

### #47 GitHub Pages直URLを停止・無害化する

- root dashboard だけでなく `previews/<slug>/` も停止・無害化対象にする。
- `gh-pages` 現在ツリーを消すだけでは履歴に残るため、履歴・branch visibility・branch retention の扱いを明示する。
- public stub を残す場合は、`data/*.json`、`save_api_endpoint`、deck/timeline payload を含めない。

### #50 dashboard publish flowをCloudflare Pagesへ移行する

- `dashboard-site` artifact と Pages artifact の流れを Cloudflare Pages + Access 側へ移す。
- preview URL も Access配下に置き、branch preview を公開URLとして残さない。
- `metadata.json` をそのまま公開payloadにしない。public stub が必要な場合は表示用metadataを分離する。

### #52 戦績管理ページの限定公開設計を行う

- 戦績データは `チーム限定` をdefaultにする。
- 相手PN、CR、備考、チーム内メモは Access 外に出さない。
- private repository CSV MVP を採る場合でも、Git履歴とrepository read権限者に見えることを前提リスクとして明記する。
- free-form memo には `保存不可` 情報を入れない運用ルールが必要。

### #48 / #51 への関連事項

- #48 では private repository 化後の Actions artifact、Pages、Cloudflare Pages連携、`gh-pages` 履歴の可視性を確認する。
- #51 では `save_api_endpoint` の公開範囲と Worker側認証責務を、Cloudflare Access / CORS / JWT検証に分けて扱う。
