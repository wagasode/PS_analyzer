# Cloudflare Pages + Access 配信基盤セットアップ手順

確認日: 2026-05-19

## この文書の位置づけ

この文書は #49「Cloudflare Pages + Access配信基盤を作成する」の設定手順と、後続 issue への引き継ぎ情報を整理する docs です。

#49 PR では Cloudflare dashboard、GitHub settings、GitHub Actions、Save API Worker、GitHub Pages、repository visibility を変更しません。Cloudflare 側の実操作は人間が dashboard で行い、実施結果は `docs/cloudflare_access/access_policy_checklist.md` に記録します。

## #49 の初期方針

| 項目 | 方針 |
|---|---|
| Cloudflare Pages project名 | `ps-analyzer` |
| 初期 production URL | `https://ps-analyzer.pages.dev` |
| 独自ドメイン | まず使わない |
| Access 認証方式 | Google login |
| 許可方式 | チームメンバーの Google アカウントを個別 allowlist する |
| One-time PIN | 初期必須ではない。Google login で詰まる場合の補助候補として残す |
| preview URL | Access 保護対象に含める |
| GitHub Pages 停止/無害化 | #47 で扱う |
| publish flow 移行 | #50 で扱う |
| Save API Worker 保護 | #51 で扱う |
| repository private 化 | Cloudflare Pages 連携確認後に段階的に実施する |

## 依存関係

- #46 の分類では、GitHub Pages root、preview、`gh-pages` 現在ツリー、Actions artifact、dashboard JSON は `チーム限定` として扱う方針です。
- #48 の調査では、private repository 化だけでは GitHub Pages、Actions artifact、`gh-pages` 履歴、Cloudflare Pages preview、repository read 権限者への CSV 可視性は解決しないと整理しています。
- #49 では Cloudflare Pages と Access の本番/preview保護方針を確認し、#50/#51/#47/#53 へ渡せる設定情報を確定します。

## 実操作前の確認事項

Cloudflare dashboard で作業する前に、人間が次を確認します。

| 確認事項 | #49 初期値 / 記録欄 |
|---|---|
| Cloudflare account | 人間が dashboard で選択して記録する |
| Cloudflare Zero Trust team domain | 人間が dashboard で確認して記録する |
| Pages project名 | `ps-analyzer` |
| production branch | `main` 候補 |
| production URL | `https://ps-analyzer.pages.dev` |
| custom domain | 初期は使わない |
| deployment mode | Git integration または Direct Upload を作成前に決める |
| GitHub App repository access | 可能な限り `wagasode/PS_analyzer` のみに限定する |
| Access login方式 | Google login |
| allowlist | チームメンバーの Google アカウントを個別指定する |

### deployment mode の注意

Cloudflare Pages は Git integration と Direct Upload で作成方法が異なります。#48 からの引き継ぎでは Git integration の repository access 確認が前提になっていますが、#50 で GitHub Actions から `wrangler pages deploy` する方針にする場合は、Direct Upload projectとして作成するか、Git integration project の自動deployを無効化して Wrangler direct upload と競合しない運用にします。

#49 の実操作では、Pages project を作成する前に、次のどちらで進めたかを checklist に記録してください。

| mode | #49 で確認すること | #50 への影響 |
|---|---|---|
| Git integration | Cloudflare Workers & Pages GitHub App が `wagasode/PS_analyzer` のみを読めること、production branch、preview branch 対象 | #50 で GitHub Actions direct upload を使う場合は、自動deployを無効化するか、Cloudflare側build/deploy commandが競合しないことを確認する |
| Direct Upload | Pages project を Direct Upload として作成すること、GitHub Actions から deploy するための API token 方針 | #50 で GitHub Actions secrets / vars と `wrangler pages deploy` 相当の publish flow を実装する |

どちらを選ぶ場合も、#49 PR では GitHub Actions を変更しません。

## #49 初回 deploy 失敗の記録

#49 後の初回 deploy では、Cloudflare Pages 側で `npx wrangler deploy` が実行され、静的ファイルの directory を検出できずに失敗しました。

この repository の dashboard は source branch に常置されず、GitHub Actions の `Collect streaming data` workflow が実行時に `public/` を生成します。そのため、Cloudflare Pages 側の build/deploy command で Workers 向けの `wrangler deploy` を実行する方式はこの用途に合いません。

#50 では、`dashboard-site` artifact を `Publish dashboard` workflow 側で download し、実ディレクトリ `dashboard/` を `wrangler pages deploy` で Cloudflare Pages project `ps-analyzer` へ deploy する方式にします。Git integration の自動 deploy が残っている場合は、Cloudflare dashboard 側で自動 deploy を無効化するか、GitHub Actions direct upload と競合しない設定へ変更します。この repository PR では Cloudflare dashboard の実設定変更は行いません。

## Google login の準備

Google login を使う場合は、Cloudflare Zero Trust の Identity provider として Google を追加します。

1. Google Cloud 側で OAuth client を用意する。
2. Cloudflare Zero Trust team domain の callback URL を Google OAuth client に登録する。
3. Google OAuth client ID / client secret を Cloudflare Zero Trust の Google identity provider に設定する。
4. Cloudflare 側で identity provider の接続テストを行う。
5. OAuth client secret、Access cookie、JWT、API token は docs、GitHub issue、PR、artifact、CSV、dashboard JSON に保存しない。

Google login が詰まる場合の補助候補として One-time PIN を残します。ただし One-time PIN を使う場合も、`Everyone` や任意メール許可にはせず、個別 email allowlist と組み合わせます。

## Cloudflare Pages project 作成手順

人間が Cloudflare dashboard で実施します。

1. Cloudflare dashboard で対象 account を開く。
2. Workers & Pages から Pages project を作成する。
3. project name に `ps-analyzer` を指定する。
4. deployment mode を選ぶ。
5. Git integration を選ぶ場合は、Cloudflare Workers & Pages GitHub App の repository access を `wagasode/PS_analyzer` のみに限定できるか確認する。
6. production branch は `main` を候補にする。
7. preview deployment の対象 branch を確認し、Access 保護が完了するまで preview URL を共有しない。
8. production URL が `https://ps-analyzer.pages.dev` になることを確認する。
9. 作成結果、deployment mode、production URL、preview URL 例を checklist に記録する。

現行 repository では dashboard 生成物は workflow 実行時に `public/` へ生成され、source branch には追跡されません。そのため、Cloudflare Pages 側で実際に dashboard を deploy する publish flow は #50 で実装します。#49 で Pages project を作成しても、#50 完了までは本番 dashboard の移行完了とは扱いません。

## Access application 作成手順

Access application は production の `ps-analyzer.pages.dev` と preview URL の両方を保護対象にします。

### production `pages.dev`

1. Cloudflare Zero Trust dashboard を開く。
2. Access applications で self-hosted application を作成する。
3. application 名は `PS Analyzer production pages.dev` など、production 用だと分かる名前にする。
4. public hostname に `ps-analyzer.pages.dev` を設定する。
5. login method に Google identity provider を選ぶ。
6. allow policy を作成し、チームメンバーの Google account email を個別に include する。
7. policy で `Everyone`、全ドメイン許可、広い email domain 許可を使っていないことを確認する。
8. Access application の session duration、app launcher 表示有無、ログ記録方針を checklist に記録する。

### preview URL

preview deployment は production と同じくチーム限定公開として扱います。

1. Pages project の Access policy / preview deployment protection 設定を確認する。
2. preview deployment 用の Access application または Pages project 側の Access policy を有効にする。
3. preview wildcard が `*.ps-analyzer.pages.dev` 相当を保護できているか確認する。
4. production `ps-analyzer.pages.dev` と preview wildcard の保護範囲を別々に記録する。
5. branch alias URL と deployment hash URL のどちらが発行されるかを確認し、両方を確認対象に含める。

Cloudflare Pages の preview Access 設定だけでは production の `ps-analyzer.pages.dev` を保護できない場合があります。production URL と preview URL は別々に未ログイン、許可外、許可ユーザーの確認を行ってください。

## Access policy の最小方針

| 項目 | 方針 |
|---|---|
| Policy action | `Allow` |
| Include | チームメンバーの Google account email を個別指定 |
| Require | Google login を使う。設定可能なら login method を Google に限定する |
| Exclude | 必要に応じて退任者や一時除外ユーザーを指定する |
| One-time PIN | 初期は使わない。fallback で使う場合は理由と期間を記録する |
| 許可しない設定 | `Everyone`、広い email domain allow、認証方式だけで email allowlist がない policy |

## 動作確認手順

Cloudflare 側設定後、人間がブラウザで確認します。

| 対象 | 状態 | 期待結果 |
|---|---|---|
| `https://ps-analyzer.pages.dev` | 未ログイン / private window | Cloudflare Access login に誘導される |
| `https://ps-analyzer.pages.dev` | allowlist 外の Google account | Access denied になる |
| `https://ps-analyzer.pages.dev` | allowlist 内の Google account | Pages の内容を表示できる |
| preview branch URL | 未ログイン / private window | Cloudflare Access login に誘導される |
| preview branch URL | allowlist 外の Google account | Access denied になる |
| preview branch URL | allowlist 内の Google account | preview の内容を表示できる |
| Cloudflare Access logs | 上記確認後 | allow / deny の記録が見える |

#49 時点で dashboard 本体がまだ deploy されていない場合は、Pages の初期ページや placeholder が表示されるだけでも構いません。ただし「Access が効いていること」と「publish flow が移行済みであること」は分けて記録します。

## 後続 issue への引き継ぎ

### #50 dashboard publish flow を Cloudflare Pages へ移行する

- Pages project名: `ps-analyzer`
- production URL: `https://ps-analyzer.pages.dev`
- deploy command: `wrangler pages deploy dashboard --project-name ps-analyzer --branch <head_branch>`
- artifact path: `Collect streaming data` が upload する `dashboard-site` artifact を、`Publish dashboard` workflow が `dashboard/` として download する。
- deployment mode: GitHub Actions から Pages direct upload する。Git integration project で始めている場合は、Cloudflare 側の自動deploy設定が残っていないか checklist で確認する。
- GitHub Actions secrets / vars と Cloudflare API token の最小権限を決める。
- GitHub Actions summary から production / preview URL へ移動できる導線を維持する。
- #50 では `gh-pages` branch、GitHub Pages settings、過去 preview は変更しない。GitHub Pages 直URLの停止/無害化は #47 で扱う。

### #51 Save API Worker を Access 前提で保護する

- dashboard の origin は `https://ps-analyzer.pages.dev` と preview URL を前提に再整理する。
- `ALLOWED_ORIGINS` は production / preview / custom domain の扱いを分けて判断する。
- Cloudflare Access、CORS、Worker 側 Access JWT 検証、repository/branch/payload schema check は別レイヤーとして扱う。
- Save API Worker の変更は #51 で行い、#49 では変更しない。

### #47 GitHub Pages 直URLを停止・無害化する

- #49/#50 で Cloudflare Pages + Access の production / preview 導線が確認できてから進める。
- root dashboard だけでなく `previews/<slug>/` も停止・無害化対象にする。
- public stub を残す場合は `data/*.json`、`save_api_endpoint`、deck/timeline payload を含めない。

### #53 Cloudflare Access 移行後の運用ドキュメントを整備する

- 許可ユーザー追加/削除手順。
- Google login / One-time PIN fallback の運用条件。
- production / preview URL の確認手順。
- Access deny 時、Pages deploy failure 時、Save API failure 時の切り分け手順。
- Cloudflare Access 閲覧者リストと GitHub repository collaborator を同一管理にするか、別管理にするかの運用ルール。

## GitHub secrets / vars 候補

この PR では secrets / vars を追加しません。#50/#51 で必要になる候補だけを整理します。

| 名前候補 | 種別候補 | 用途 | 主な後続 issue |
|---|---|---|---|
| `CF_PAGES_PROJECT_NAME` | GitHub variable | Cloudflare Pages project名。初期値候補は `ps-analyzer` | #50 |
| `CLOUDFLARE_ACCOUNT_ID` | GitHub variable または secret | Direct Upload / Wrangler deploy で account を指定する場合に使う | #50 |
| `CLOUDFLARE_API_TOKEN` | GitHub secret | GitHub Actions から Cloudflare Pages へ deploy する場合に使う最小権限 token | #50 |
| `PAGES_BASE_URL` | GitHub variable | workflow summary や metadata に出す Cloudflare Pages production URL | #50 |
| `CF_ACCESS_TEAM_DOMAIN` | GitHub variable | Worker 側 Access JWT 検証や運用 docs で team domain を参照する場合に使う | #51/#53 |
| `CF_ACCESS_AUD` | GitHub variable または secret | Worker 側で Access JWT の audience を検証する場合に使う | #51 |
| `SAVE_API_ENDPOINT` | GitHub variable | dashboard から呼ぶ Save API endpoint。#49 では変更しない | #51 |

secret の値、OAuth client secret、API token、Access cookie、JWT は docs や PR 本文に書きません。

## 参照した公式docs

- Cloudflare Docs, "Git integration": https://developers.cloudflare.com/pages/get-started/git-integration/
- Cloudflare Docs, "GitHub integration": https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/
- Cloudflare Docs, "Use Direct Upload with continuous integration": https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/
- Cloudflare Docs, "Wrangler pages commands": https://developers.cloudflare.com/workers/wrangler/commands/pages/
- Cloudflare Docs, "Preview deployments": https://developers.cloudflare.com/pages/configuration/preview-deployments/
- Cloudflare Docs, "Known issues": https://developers.cloudflare.com/pages/platform/known-issues/
- Cloudflare Docs, "Google identity provider": https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/google/
