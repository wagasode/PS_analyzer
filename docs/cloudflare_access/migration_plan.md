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
| #49 Cloudflare Pages + Access配信基盤を作成する | Cloudflare Pages projectとAccess applicationの作成手順、production/preview保護方針、後続issueへの引き継ぎを整理する | docs-only / Cloudflare dashboard checklist | Cloudflare Pages, Cloudflare Access, `pages.dev`, preview URL, access policy docs | #48, 人間によるCloudflare方針決定 | In progress. 実設定は人間がdashboardで行う |
| #50 dashboard publish flowをCloudflare Pagesへ移行する | `public/` dashboard生成物のpublish先をGitHub PagesからCloudflare Pagesへ移行する | GitHub Actions変更 / dashboard配信変更 | `.github/workflows/collect-streams.yml`, `.github/workflows/publish-dashboard.yml`, GitHub Actions secrets/vars | #46, #49 | This PR. `dashboard-site` artifactをCloudflare Pagesへdirect uploadする |
| #51 Save API WorkerをAccess前提で保護する | dashboardからの保存APIをCloudflare Access前提で保護し、CORSと認証の責務を分ける | Worker/API変更 / Cloudflare Access / CORS | `workers/save-deck-links/worker.mjs`, `workers/save-deck-links/wrangler.toml`, dashboard fetch, `SAVE_API_ENDPOINT` | #49, #50, Save API route決定 | Not yet. Access境界とroute決定後に進める |
| #52 戦績管理ページの限定公開設計を行う | 相手PN、CR、備考などを含む戦績データの限定公開設計と保存先候補を整理する | docs-only / 設計 | docs, 戦績schema案, private repo CSV MVP検討 | #46, #48, #49 | Later. 前提整理後に進める |
| #53 Cloudflare Access移行後の運用ドキュメントを整備する | Access移行後の閲覧、保存、preview、障害時切り分け、チーム運用をdocs化する | docs-only / 運用手順 | docs, README必要箇所, Cloudflare/GitHub運用手順 | #47, #49, #50, #51, #52 | Last. 実装結果反映後に進める |

## Issue別レポート

- #46: `docs/cloudflare_access/public_data_classification.md`
- #48: `docs/cloudflare_access/private_repo_impact.md`
- #49: `docs/cloudflare_access/cloudflare_pages_access_setup.md`, `docs/cloudflare_access/access_policy_checklist.md`

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

#49はCloudflare Pages project名を `ps-analyzer`、初期 production URL を `https://ps-analyzer.pages.dev`、認証方式を Google login、許可方式をチームメンバーの Google account 個別 allowlist として開始します。初期は独自ドメインを使わず、preview URL も Access 保護対象に含めます。

#49 の PR では Cloudflare dashboard の実操作、GitHub Actions 変更、Save API Worker 変更、GitHub Pages停止、repository private化は行いません。出力は Cloudflare Pages + Access の設定手順、Access policy checklist、#50/#51/#47/#53 への引き継ぎに限定します。

### Wave 3

- #50 dashboard publish flow移行
- #47 GitHub Pages直URL停止/無害化
- #51 Save API Worker保護

#50が先行です。Cloudflare Pages + Access側で代替公開先とpreview導線が確認できてから、#47でGitHub Pages直URLを停止または無害化します。#51はAccess境界、Worker route、`SAVE_API_ENDPOINT`の向き先が決まってから進めます。

#50 では `Collect streaming data` が生成した `public/` を `dashboard-site` artifact として受け渡し、`Publish dashboard` workflow が `dashboard/` にdownloadして `wrangler pages deploy` で Cloudflare Pages project `ps-analyzer` へdeployします。#49後の初回deploy失敗は Cloudflare Pages側で Workers向け `npx wrangler deploy` が実行されたことが原因であり、この用途では Pages向けの `wrangler pages deploy` を使います。

### Wave 4

- #52 戦績管理ページ限定公開設計
- #53 運用ドキュメント整備

#52は#46/#48/#49の結果を踏まえて、戦績データをどこに保存し、Access外へ出さないための設計を確定します。#53は#47/#49/#50/#51/#52の実装結果を反映する最後のdocsとして扱います。

## Worktree creation decision

初期計画時点で作成するworktreeは、Wave 1の#46と#48のみでした。#46/#48 の結果と人間側の #49 初期方針決定を受けて、現在は #49 の専用worktreeを作成済みです。

#49 は Cloudflare 側設定そのものではなく、人間が dashboard で行う作業の手順化と、後続 issue へ渡す設定情報の整理を docs-only で行います。

#50〜#53は、#49 の checklist 記録と Cloudflare Pages + Access の確認結果を受けて進めます。

## Created / active worktrees

- #46 完了済み
  - path: `/Users/wagasode/Documents/GitHub/wagasode/PS_analyzer_issue46`
  - branch: `feature/issue-46-public-data-inventory`
  - purpose: 公開データ棚卸しと分類をdocs/reportとして残す
- #48 完了済み
  - path: `/Users/wagasode/Documents/GitHub/wagasode/PS_analyzer_issue48`
  - branch: `feature/issue-48-private-repo-impact`
  - purpose: repository private化の影響をdocs/reportとして残す
- #49 進行中
  - path: `/Users/wagasode/Documents/GitHub/wagasode/PS_analyzer_issue49`
  - branch: `feature/issue-49-cloudflare-pages-access`
  - purpose: Cloudflare Pages + Access の設定手順、policy checklist、後続issueへの引き継ぎをdocsとして残す
- #50 着手済み
  - path: `/Users/wagasode/Documents/GitHub/wagasode/PS_analyzer_issue50`
  - branch: `feature/issue-50-cloudflare-pages-publish`
  - purpose: dashboard publish flow を Cloudflare Pages direct upload へ移行する

## Worktrees not to create yet

- #47
  - #50で代替公開先とpreview導線が動いてからGitHub Pagesを停止または無害化しないと、dashboard確認導線が一時的に失われるため。
- #51
  - #49/#50でAccess境界、Worker route、`SAVE_API_ENDPOINT`の向き先が確定してから進める必要があるため。
- #52
  - #46のデータ分類、#48のprivate化影響、#49のAccess配信基盤を踏まえて設計する必要があるため。
- #53
  - 実装結果を反映する運用docsであり、早すぎる着手は仮説ベースの手順になりやすいため。

## Human decisions required before later waves

- Cloudflare account / zone
- deployment mode: Git integration / Direct Upload
- Cloudflare Workers & Pages GitHub App の repository access 範囲
- preview deployment の対象 branch / URL 形式
- One-time PIN fallback を使う条件と期限
- GitHub Pagesを完全停止するか、stubを残すか
- repo private化のタイミング
- Save API Worker route / domain / Access JWT検証方針
- `SAVE_API_ENDPOINT` と GitHub Actions secrets/vars の命名
- 戦績データの保存先: private repo CSV MVPか、別DB検討か

## Decisions resolved for #49 initial setup

- Pages project名: `ps-analyzer`
- 初期 production URL: `https://ps-analyzer.pages.dev`
- custom domain: 初期は使わない
- Access login方式: Google login
- 許可方式: チームメンバーの Google account 個別 allowlist
- One-time PIN: 初期必須ではなく、Google loginで詰まる場合の補助候補
- preview URL: Access 保護対象に含める
- GitHub Pages停止/無害化: #47
- dashboard publish flow移行: #50
- Save API Worker保護: #51
- repo private化: Cloudflare Pages連携確認後に段階的に実施

## Risks

- `gh-pages`履歴、過去preview、Actions artifactに残るデータは、新公開先へ移しても消えない。
- #50 と #47 を逆順にすると、dashboard確認導線が一時的に失われる。
- #51 はCORS変更だけでは認証にならない。CORS allowlist、Cloudflare Access、Worker側JWT検証の責務を分けて判断する必要がある。
- #48 はGitHub/Cloudflareの仕様確認が必要。private repository、GitHub Pages、Cloudflare Pages連携、Actions artifact、token権限の仕様は変わり得る。
- #46 の分類で `保存不可` が出た場合、後続issueの設計が変わる。

## Issue outputs

- #48: `docs/cloudflare_access/private_repo_impact.md`
- #49: `docs/cloudflare_access/cloudflare_pages_access_setup.md`, `docs/cloudflare_access/access_policy_checklist.md`

## Next actions

1. #49 の手順に沿って、人間が Cloudflare Pages project と Access application を dashboard で設定する。
2. `docs/cloudflare_access/access_policy_checklist.md` に production / preview の Access 確認結果を記録する。
3. #49 の記録を前提に #50 で dashboard publish flow を Cloudflare Pages へ移行する。
4. #50 の代替公開先確認後、#47 で GitHub Pages 直URLを停止または無害化する。
5. #49/#50 の Access境界と origin を前提に #51 で Save API Worker 保護を進める。
