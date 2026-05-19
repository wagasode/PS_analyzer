# Cloudflare Access Migration Plan

## この文書の位置づけ

この文書は、#15「PS_analyzer全体をCloudflare Access配下へ移行する」を進めるための依存関係・作業順・判断事項を整理する living document です。

#46〜#53 の進行に応じて継続的に更新します。

この文書は実装手順書ではなく、司令塔スレッドで確認した依存関係、並列化方針、worktree作成判断、人間が先に決めるべき事項を残すための進行管理資料です。各issueで実装・調査結果が確定した場合は、そのissueのPRでこの文書も必要に応じて更新します。

## Issue summary

| Issue | Purpose | Type | Likely files | Dependencies | Parallelizable |
|---|---|---|---|---|---|
| #46 公開データ棚卸しと分類を行う | dashboard生成物、`public/data/*.json`、deck/timeline情報、preview/artifact/`gh-pages`露出、将来の戦績データ候補を分類する | docs-only / 棚卸し | `public/`, `public/data/*.json`, `data/*.csv`, `.github/workflows/*.yml`, `scripts/build_streaming_dashboard.py`, docs | #15 | Yes. Wave 1で先行する |
| #47 GitHub Pages直URLを停止・無害化する | Cloudflare AccessをバイパスするGitHub Pages直URLとpreview URLを停止または無害化する | GitHub Pages設定 / GitHub Actions変更 / stub検討 | `.github/workflows/publish-dashboard.yml`, `gh-pages`, GitHub Pages settings, stub page案 | #46, #49, #50 | Not yet. 代替公開先確認後に進める |
| #48 PS_analyzerリポジトリをprivate化する影響を確認する | repository private化がGitHub Pages、Actions、Cloudflare Pages、Save API Worker、team access、CSV保存に与える影響を確認する | docs-only / 設定調査 | `docs/cloudflare_access/private_repo_impact.md`, docs, `.github/workflows/*.yml`, `workers/save-deck-links/*`, GitHub/Cloudflare設定調査 | #15, #46の分類結果を参照 | Yes. Wave 1で#46と並列調査する |
| #49 Cloudflare Pages + Access配信基盤を作成する | Cloudflare Pages projectとAccess applicationを作り、dashboard公開先をチーム限定公開にする | Cloudflare側設定 / 配信基盤 / docs | Cloudflare Pages, Cloudflare Access, custom domain, `pages.dev`, preview URL, access policy docs | #48, 人間によるCloudflare方針決定 | Not yet. 人間判断後に進める |
| #50 dashboard publish flowをCloudflare Pagesへ移行する | `public/` dashboard生成物のpublish先をGitHub PagesからCloudflare Pagesへ移行する | GitHub Actions変更 / dashboard配信変更 | `.github/workflows/collect-streams.yml`, `.github/workflows/publish-dashboard.yml`, `scripts/build_streaming_dashboard.py`, GitHub Actions secrets/vars | #46, #49 | Not yet. #49で配信基盤が見えてから進める |
| #51 Save API WorkerをAccess前提で保護する | dashboardからの保存APIをCloudflare Access前提で保護し、CORSと認証の責務を分ける | Worker/API変更 / Cloudflare Access / CORS | `workers/save-deck-links/worker.mjs`, `workers/save-deck-links/wrangler.toml`, dashboard fetch, `SAVE_API_ENDPOINT` | #49, #50, Save API route決定 | Not yet. Access境界とroute決定後に進める |
| #52 戦績管理ページの限定公開設計を行う | 相手PN、CR、備考などを含む戦績データの限定公開設計と保存先候補を整理する | docs-only / 設計 | docs, 戦績schema案, private repo CSV MVP検討 | #46, #48, #49 | Later. 前提整理後に進める |
| #53 Cloudflare Access移行後の運用ドキュメントを整備する | Access移行後の閲覧、保存、preview、障害時切り分け、チーム運用をdocs化する | docs-only / 運用手順 | docs, README必要箇所, Cloudflare/GitHub運用手順 | #47, #49, #50, #51, #52 | Last. 実装結果反映後に進める |

## Dependency graph

```text
#46 ─┬─> #47
     ├─> #50
     └─> #52

#48 ─┬─> #49
     └─> #52

#49 ─┬─> #50
     ├─> #51
     ├─> #47
     └─> #52

#50 ─┬─> #47
     ├─> #51
     └─> #53

#47 ─┐
#51 ─┼─> #53
#52 ─┘
```

## Recommended waves

### Wave 1

- #46 公開データ棚卸しと分類
- #48 private化影響確認

#46は後続issueの前提になるため最優先で進めます。#48は#46の最終分類を参照しますが、GitHub Pages、GitHub Actions、Cloudflare Pages連携、Save API Worker token権限、private repository内CSV保存リスクの調査自体は#46と並列に進められます。

### Wave 2

- #49 Cloudflare Pages + Access配信基盤

#49はCloudflare account / zone / custom domain / Pages project名 / Access policy / 許可ユーザー管理単位が決まってから開始します。Cloudflare側設定を伴うため、司令塔スレッドでは人間側の判断事項を明確にしてから実装スレッドへ渡します。

### Wave 3

- #50 dashboard publish flow移行
- #47 GitHub Pages直URL停止/無害化
- #51 Save API Worker保護

#50が先行です。Cloudflare Pages + Access側で代替公開先とpreview導線が確認できてから、#47でGitHub Pages直URLを停止または無害化します。#51はAccess境界、Worker route、`SAVE_API_ENDPOINT`の向き先が決まってから進めます。

### Wave 4

- #52 戦績管理ページ限定公開設計
- #53 運用ドキュメント整備

#52は#46/#48/#49の結果を踏まえて、戦績データをどこに保存し、Access外へ出さないための設計を確定します。#53は#47/#49/#50/#51/#52の実装結果を反映する最後のdocsとして扱います。

## Worktree creation decision

現時点で作成するworktreeは、Wave 1の#46と#48のみです。

#46は公開データ棚卸しで、後続issueの判断材料になります。#48はprivate化影響確認で、#46の分類結果を参照しつつも、影響調査そのものは並列に進められます。

#49〜#53は、依存関係または人間側のCloudflare/GitHub方針決定が残っているため、現時点ではworktreeを作成しません。依存関係が未整理のissueを先に分離すると、後から前提が変わりやすく、不要な差分や設定変更を生みやすいためです。

## Worktrees to create now

- #46
  - path: `/Users/wagasode/Documents/GitHub/wagasode/PS_analyzer_issue46`
  - branch: `feature/issue-46-public-data-inventory`
  - purpose: 公開データ棚卸しと分類をdocs/reportとして残す
- #48
  - path: `/Users/wagasode/Documents/GitHub/wagasode/PS_analyzer_issue48`
  - branch: `feature/issue-48-private-repo-impact`
  - purpose: repository private化の影響をdocs/reportとして残す

## Worktrees not to create yet

- #49
  - Cloudflare account / zone / custom domain / Pages project名 / Access policy / 許可ユーザー管理単位の人間判断が先に必要なため。
- #50
  - #49でCloudflare Pages + Access配信基盤が見えてから、publish flowを移行する方が安全なため。
- #47
  - #50で代替公開先とpreview導線が動いてからGitHub Pagesを停止または無害化しないと、dashboard確認導線が一時的に失われるため。
- #51
  - #49/#50でAccess境界、Worker route、`SAVE_API_ENDPOINT`の向き先が確定してから進める必要があるため。
- #52
  - #46のデータ分類、#48のprivate化影響、#49のAccess配信基盤を踏まえて設計する必要があるため。
- #53
  - 実装結果を反映する運用docsであり、早すぎる着手は仮説ベースの手順になりやすいため。

## Human decisions required before later waves

- Cloudflare account / zone / custom domain / Pages project名
- `pages.dev` と preview URL の保護方針
- Access login方式: Google login / メールallowlist / One-time PIN
- 許可ユーザーの管理単位
- GitHub Pagesを完全停止するか、stubを残すか
- repo private化のタイミング
- Save API Worker route / domain / Access JWT検証方針
- `SAVE_API_ENDPOINT` と GitHub Actions secrets/vars の命名
- 戦績データの保存先: private repo CSV MVPか、別DB検討か

## Risks

- `gh-pages`履歴、過去preview、Actions artifactに残るデータは、新公開先へ移しても消えない。
- #50 と #47 を逆順にすると、dashboard確認導線が一時的に失われる。
- #51 はCORS変更だけでは認証にならない。CORS allowlist、Cloudflare Access、Worker側JWT検証の責務を分けて判断する必要がある。
- #48 はGitHub/Cloudflareの仕様確認が必要。private repository、GitHub Pages、Cloudflare Pages連携、Actions artifact、token権限の仕様は変わり得る。
- #46 の分類で `保存不可` が出た場合、後続issueの設計が変わる。

## Issue outputs

- #48: `docs/cloudflare_access/private_repo_impact.md`

## Next actions

1. #46専用スレッドを開き、公開データ棚卸しを行う。
2. #48専用スレッドを開き、private化影響確認を行う。
3. #46/#48の結果を踏まえ、司令塔スレッドで #49 の開始条件を再確認する。
4. 人間側でCloudflareのaccount/zone/domain/Access policy方針を決める。
