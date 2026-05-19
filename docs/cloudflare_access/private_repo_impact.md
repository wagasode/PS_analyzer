# PS_analyzer private化影響レポート

確認日: 2026-05-19

## この文書の位置づけ

この文書は、#48「PS_analyzerリポジトリをprivate化する影響を確認する」の調査結果です。

実際の repository private 化、GitHub Pages 停止、Cloudflare Pages deploy 実装、Worker/API変更、GitHub/Cloudflare settings変更は行っていません。

## 結論

PS_analyzer を private repository にすることは、チーム内限定公開化の前提整備として有効です。ただし、private 化だけでは GitHub Pages、Actions artifact、`gh-pages`履歴、Cloudflare Pages preview、repository read 権限者へのCSV可視性を解決できません。

推奨タイミングは、次の条件を満たした後です。

1. #46 の公開データ分類が完了している。
2. #49 で Cloudflare Pages + Access の本番/preview保護方針が確認済みである。
3. #50 で dashboard publish flow の移行先が動作確認済みである。
4. #47 で GitHub Pages 直URLを停止または無害化する方針が確定している。
5. Save API Worker が private repository へ書き込む GitHub token の権限と運用者が確認済みである。

#46 は 2026-05-19 時点で `OPEN` です。そのため、戦績CSVや既存公開データの最終的な保存可否は、#46 の分類結果待ちとして扱います。

## 現在の repo / Pages / Actions 状態

2026-05-19 時点の read-only 確認結果です。

| 項目 | 現状 |
|---|---|
| GitHub repository visibility | `PUBLIC` |
| GitHub Pages | `https://wagasode.github.io/PS_analyzer/` が設定済み、`build_type: workflow`、`public: true` |
| Pages source | API上は `main` / `/`、実際の publish flow は workflow artifact + `actions/deploy-pages` |
| `gh-pages` branch | `origin/gh-pages` が存在する |
| GitHub Actions | enabled, allowed actions: `all` |
| default `GITHUB_TOKEN` permission | `read` |
| tracked `public/` | 現在の working tree には存在しない。workflow 実行時に生成され、artifact / Pagesへ出る |
| tracked CSV | `data/players_channels.csv`, `data/decks.csv`, `data/stream_session_decks.csv` |

## GitHub Pages への影響

GitHub Pages は、private repository 化しても安全な限定公開面にはなりません。

- GitHub Free / Free organization では、public repository を private に変更すると、公開済み GitHub Pages site は自動で unpublish されます。
- GitHub Pro / Team / Enterprise 系では private repository の GitHub Pages が利用可能ですが、GitHub Pages site は原則としてインターネットへ公開されます。
- GitHub Enterprise Cloud の一部構成では Pages の private publishing / access control が使えますが、今回のロードマップは GitHub Pages を長期公開基盤にしない方針です。
- 現在は `gh-pages` branch と workflow artifact を経由して dashboard を出しているため、private 化前後にかかわらず、GitHub Pages 直URL停止または無害化は #47 で別途必要です。

このため、private 化は「GitHub repository の閲覧者を絞る」対策であり、「GitHub Pages URL を知っている人の閲覧を止める」対策ではありません。後者は #47/#49/#50 の担当です。

## GitHub Actions への影響

private 化後も GitHub Actions 自体は利用できますが、運用上の注意点があります。

### `.github/workflows/collect-streams.yml`

現行の workflow は `permissions: contents: read` で、YouTube / Twitch の secrets を使ってデータを収集し、`public/` dashboard と report を生成します。

artifact として次をアップロードします。

- `streaming-data`: `data/streams.sqlite`, `reports/*.csv`, `public/**`
- `dashboard-site`: `public`, `retention-days: 7`

private repository では repository read 権限を持つユーザーが artifact を取得できます。artifact は Pages より狭い公開面になりますが、チーム内閲覧者全員へ見せてよいデータだけを入れる前提が必要です。

### `.github/workflows/publish-dashboard.yml`

現行の workflow は `permissions: actions: read`, `contents: write`, `pages: write`, `id-token: write` を要求し、`dashboard-site` artifact を download して `gh-pages` branch と GitHub Pages へ publish します。

private 化後の注意点は次の通りです。

- GitHub Actions の private repository 利用は、プランの無料枠や課金条件の影響を受ける。
- `contents: write` により `gh-pages` branch へ push する前提は残る。
- GitHub Pages が private repository で使えるか、または自動 unpublish されるかは GitHub plan に依存する。
- `gh-pages` branch の履歴や過去の Pages deploy は、private 化だけでは過去に公開された内容の回収にならない。

Cloudflare Pages へ移行する場合、#50 でこの workflow の役割を「GitHub Pages publish」から「Cloudflare Pages publish または Cloudflare側Git連携」へ整理する必要があります。

## Cloudflare Pages 連携への影響

Cloudflare Pages は GitHub の public / private repository の両方を扱えます。ただし、private repository を deploy するには Cloudflare Workers & Pages GitHub App が該当 repository へアクセスできる必要があります。

#49 で確認すべき項目は次の通りです。

- Cloudflare account と GitHub account / organization の対応関係。
- Cloudflare Workers & Pages GitHub App の repository access を `wagasode/PS_analyzer` のみに絞れるか。
- production branch を `main` にするか。
- preview branch をどこまで自動deploy対象にするか。
- `*.pages.dev` production URL、custom domain、preview URL の Access 保護方針。

Cloudflare Pages preview URL は初期状態では公開される前提で扱います。Cloudflare Access policy で preview deployments を制限できますが、production の `*.pages.dev` や custom domain も含めて保護する設計は #49 で明示確認が必要です。

## Save API Worker の GitHub API 権限

`workers/save-deck-links/worker.mjs` は、Cloudflare Worker の secret `GITHUB_TOKEN` を使って GitHub REST API の Git database endpoints を呼び出し、次のCSVを更新します。

- `data/decks.csv`
- `data/stream_session_decks.csv`

現行の `wrangler.toml` では次の allowlist です。

- `ALLOWED_REPOSITORY = "wagasode/PS_analyzer"`
- `ALLOWED_BRANCHES = "main"`
- `ALLOWED_ORIGINS = "https://wagasode.github.io"`

private repository 化後は、Worker の `GITHUB_TOKEN` が private repository へアクセスできる必要があります。最小方針は次の通りです。

- fine-grained PAT または GitHub App installation token を使う。
- repository scope は `wagasode/PS_analyzer` のみに限定する。
- Git database への blob 作成、tree/commit作成、ref更新に必要な `Contents` write 権限を持たせる。
- token は Cloudflare Worker secret としてのみ保持し、ブラウザや static artifact へ出さない。
- `ALLOWED_ORIGINS` は #49/#50 の Cloudflare Pages domain / custom domain に合わせて更新する。
- `ALLOWED_BRANCHES` は `main` への直接更新を続けるか、保存専用branchやPR経由に変えるかを #51 で判断する。

private 化自体は Worker のCORSや認証を強化しません。Cloudflare Access、Worker側のAccess JWT検証、repository/branch/origin/payload schema check は別レイヤーとして扱います。

## team member access への影響

現在の repository owner は `wagasode` の個人アカウントです。個人アカウント所有の private repository では、collaborator は repository の読み取りと書き込みが可能で、read-only collaborator を付与できません。

そのため、人間が決める必要がある事項は次の通りです。

- 個人 repository の collaborator 管理で運用するか。
- read-only / write / maintain などの粒度が必要なら organization へ移すか。
- GitHub repository collaborator と Cloudflare Access の閲覧者リストを同一にするか、別管理にするか。
- repository read 権限者に CSV と Git履歴が見えることを許容するか。
- Save API token を持つ Cloudflare Worker の管理者を誰に限定するか。

GitHub access と Cloudflare Access は別のアクセス制御です。Cloudflare Access で dashboard 閲覧を許可しても GitHub repository が読めるとは限らず、逆に GitHub repository collaborator は CSV や履歴を直接読めます。

## private repository 内CSV保存MVPのリスク

private repository 内CSV保存は MVP として簡素ですが、database や秘密情報管理サービスではありません。

主なリスクは次の通りです。

- CSVの内容は Git commit として履歴に残る。
- CSVを削除しても過去 commit には残る。
- repository read 権限者は現在のCSVと履歴を読める。
- collaborator の local clone には削除後も過去内容が残り得る。
- PR diff、Actions log、Actions artifact、Pages/preview、Cloudflare Pages deploy に誤って出すと repository private 化の外へ漏れる。
- `gh-pages` branch や過去 preview に出た内容は、private 化だけでは消えない。
- public repository だった期間に公開された Pages / artifact / branch 内容は、外部コピーやキャッシュの可能性を前提にする。

private repo CSV MVP に載せてよいのは、#46 で `チーム限定` と分類され、repository collaborator に読まれてよい項目です。#46 で `保存不可` と分類された項目は、private repository であっても CSV へ保存しません。

## data/*.csv の現状リスク整理

この調査では値の全文確認ではなく、tracked CSV の種類と header を確認しました。

| file | header上の性質 | private化時の扱い |
|---|---|---|
| `data/players_channels.csv` | team, player_name, roster status, X/YouTube/Twitch identifiers, source URL, notes | 既存の公開情報由来でも、notes や source の扱いは #46 で分類する |
| `data/decks.csv` | deck name, class, archetype, deck URL/code, notes | deck URL/code/notes がチーム限定か公開可かを #46 で分類する |
| `data/stream_session_decks.csv` | stream id と deck key の紐づけ、confidence, source_note | 配信とデッキの紐づけが外部公開可か、チーム限定かを #46 で分類する |

将来の戦績CSVでは、対戦相手PN、CR、備考、練習相手、試合メモのような項目が `チーム限定` または `保存不可` になりやすいです。#52 では、CSV保存候補に入れる前に #46/#48/#49 の結果を前提条件として参照します。

## private化の推奨実行順

1. #46 で `公開可` / `チーム限定` / `保存不可` の分類を確定する。
2. #49 で Cloudflare Pages project、Access application、閲覧者管理単位、production/preview保護を確認する。
3. #50 で dashboard publish flow を Cloudflare Pages 前提へ移行し、main と preview の確認導線を維持する。
4. #47 で GitHub Pages 直URLを停止または無害化し、`wagasode.github.io/PS_analyzer` が機密データを出さないことを確認する。
5. #51 または private化直前作業で Save API Worker の token / origin / branch 方針を確認する。
6. repository を private 化する。
7. private 化直後に、Actions、Cloudflare Pages deploy、Save API書き込み、team member access を確認する。

private化は、戦績CSVのMVP保存を始める前に完了しているのが望ましいです。ただし、GitHub Pages停止とCloudflare Pages + Access移行が未完の状態で private 化すると、dashboard公開が壊れるか、逆にGitHub Pagesだけが公開面として残る可能性があります。

## 人間が決める必要がある事項

- GitHub plan 上、private repository の GitHub Pages がどう扱われるかを許容するか。
- GitHub Pages は完全停止するか、stubを残すか。
- Cloudflare Pages の production URL、preview URL、custom domain、`pages.dev` をどこまで Access 配下に置くか。
- Cloudflare Workers & Pages GitHub App の repository access をどの範囲にするか。
- GitHub repository を個人所有のままにするか、organization に移すか。
- repository collaborator と Cloudflare Access 閲覧者をどう同期するか。
- Save API Worker の GitHub token を fine-grained PAT にするか GitHub App にするか。
- 戦績データのうち、private repo CSV MVP に置く項目と、置かない項目。

## 後続 issue への引き継ぎ

### #49 Cloudflare Pages + Access配信基盤

- private repository からの Git integration は可能だが、Cloudflare Workers & Pages GitHub App の repository access が必要。
- GitHub App access は `wagasode/PS_analyzer` のみに絞る。
- preview deployments は公開が初期前提のため、Access保護を明示する。
- production の `*.pages.dev` / custom domain と preview の保護範囲を別々に確認する。

### #52 戦績管理ページの限定公開設計

- private repo CSV MVP は、#46 で `チーム限定` とされた項目に限定する。
- `保存不可` 項目は private repository でも保存しない。
- CSVはGit履歴、read権限、local clone、artifact/preview漏えいのリスクを持つため、試合メモや相手情報は最小項目から始める。
- 将来、編集頻度や秘匿性が上がる場合は DB / KV / D1 / R2 など別保存先を再検討する。

## 参照した公式docs

- GitHub Docs, "Creating a GitHub Pages site", 2026-05-19確認: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
- GitHub Docs, "Setting repository visibility", 2026-05-19確認: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
- GitHub Docs, "GITHUB_TOKEN", 2026-05-19確認: https://docs.github.com/en/actions/concepts/security/github_token
- GitHub Docs, "Downloading workflow artifacts", 2026-05-19確認: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts
- GitHub Docs, "REST API endpoints for Git blobs", 2026-05-19確認: https://docs.github.com/en/rest/git/blobs
- GitHub Docs, "REST API endpoints for Git trees", 2026-05-19確認: https://docs.github.com/en/rest/git/trees
- GitHub Docs, "REST API endpoints for Git commits", 2026-05-19確認: https://docs.github.com/en/rest/git/commits
- GitHub Docs, "REST API endpoints for Git references", 2026-05-19確認: https://docs.github.com/en/rest/git/refs
- GitHub Docs, "Permission levels for a personal account repository", 2026-05-19確認: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository
- Cloudflare Docs, "Pages Git integration", 2026-05-19確認: https://developers.cloudflare.com/pages/get-started/git-integration/
- Cloudflare Docs, "Pages GitHub integration", 2026-05-19確認: https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/
- Cloudflare Docs, "Preview deployments", 2026-05-19確認: https://developers.cloudflare.com/pages/configuration/preview-deployments/
