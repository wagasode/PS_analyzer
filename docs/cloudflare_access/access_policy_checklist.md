# Cloudflare Pages + Access 設定チェックリスト

確認日: 2026-05-19

## この文書の位置づけ

この文書は #49「Cloudflare Pages + Access配信基盤を作成する」で、人間が Cloudflare dashboard で行う作業と、Codex / repository 側へ記録する作業を分けるための checklist です。

#49 PR では Cloudflare 側の実設定、GitHub settings 変更、GitHub Actions 変更、Save API Worker 変更、GitHub Pages 停止、repository private 化は行いません。

## 作業前チェック

| チェック | 記録 |
|---|---|
| [ ] Cloudflare account を確認した | account名: |
| [ ] Cloudflare Zero Trust team domain を確認した | team domain: |
| [ ] Pages project名を `ps-analyzer` にする | project名: `ps-analyzer` |
| [ ] 初期 production URL `https://ps-analyzer.pages.dev` は deploy 検証用として扱う | production URL: `https://ps-analyzer.pages.dev` |
| [ ] チーム限定本番URL用の custom domain 要否を後続判断に残す | custom domain: 未設定 |
| [ ] Google login を第一候補にする | identity provider: Google |
| [ ] 許可ユーザーは Google account email の個別 allowlist にする | allowlist owner: |
| [ ] One-time PIN は初期必須にしない | fallback要否: |
| [ ] preview URL を Access 保護対象に含める | preview保護: |
| [ ] #50/#51/#47/#53 へ渡す情報をこの文書に記録する | 記録者: |

## Pages project 作成チェック

| チェック | 記録 |
|---|---|
| [ ] Cloudflare dashboard で Workers & Pages を開いた | 実施日: |
| [ ] Pages project を作成した | project名: |
| [ ] deployment mode を作成前に決めた | `Git integration` / `Direct Upload`: |
| [ ] Git integration の場合、GitHub App repository access を確認した | repository access: |
| [ ] Git integration の場合、production branch を確認した | branch: |
| [ ] Direct Upload の場合、#50 で必要な API token 方針を記録した | token方針: |
| [ ] production URL を確認した | URL: |
| [ ] preview deployment の対象 branch / URL 形式を確認した | preview設定: |
| [ ] `ps-analyzer.pages.dev` を限定公開本番URLとして共有しない | 共有状態: |

## Google identity provider チェック

| チェック | 記録 |
|---|---|
| [ ] Google OAuth client を用意した | Google Cloud project名: |
| [ ] Cloudflare Access callback URL を Google OAuth client に登録した | callback URL: |
| [ ] Google client ID / secret を Cloudflare Zero Trust に設定した | 設定者: |
| [ ] Cloudflare 側の Google login 接続テストに成功した | 結果: |
| [ ] OAuth client secret を docs / issue / PR / artifact に保存していない | 確認者: |

## Access application チェック

| チェック | 記録 |
|---|---|
| [ ] `Restrict previews` は preview deployment URL だけを保護すると確認した | 確認日: 2026-05-20 |
| [ ] production `pages.dev` と custom domain は Zero Trust 側で別管理だと確認した | 確認者: |
| [ ] production custom domain を Cloudflare に onboard した | hostname: |
| [ ] production custom domain 用 Access application を作成した | application名: |
| [ ] public hostname に production custom domain を設定した | hostname: |
| [ ] preview URL 用の Access policy / application を作成した | application名: |
| [ ] preview wildcard が保護対象に入っている | hostname / wildcard: |
| [ ] branch alias URL と deployment hash URL の扱いを確認した | 対象URL形式: |
| [ ] Google identity provider を login method にした | login method: |
| [ ] allow policy に個別 Google account email を include した | allowlist管理者: |
| [ ] `Everyone`、広い email domain allow、認証方式のみの許可を使っていない | 確認者: |
| [ ] One-time PIN を有効化した場合、理由と期限を記録した | 理由 / 期限: |
| [ ] Access session duration を記録した | session duration: |
| [ ] Access logs の確認場所を記録した | logs確認場所: |

## allowlist 記録テンプレート

個人メールアドレスを repository に残してよいかは人間が判断してください。repository に残さない場合は、管理場所と件数だけを記録します。

| 項目 | 記録 |
|---|---|
| allowlist管理場所 | Cloudflare Access dashboard / 外部台帳 / その他: |
| 許可ユーザー数 | |
| 追加担当者 | |
| 削除担当者 | |
| 退任時の削除SLA | |
| repository collaborator と同一管理か | 同一 / 別管理: |

## 確認マトリクス

| 対象URL | ユーザー状態 | 期待結果 | 実結果 | 確認日 |
|---|---|---|---|---|
| `https://ps-analyzer.pages.dev` | 通常ブラウザ / private window | deploy 検証用URLとして dashboard が表示できる。限定公開確認には使わない | | |
| production custom domain | 未ログイン / private window | Access login に誘導される | | |
| production custom domain | allowlist 外 Google account | Access denied になる | | |
| production custom domain | allowlist 内 Google account | Pages の内容を表示できる | | |
| preview branch URL | 未ログイン / private window | Access login に誘導される | | |
| preview branch URL | allowlist 外 Google account | Access denied になる | | |
| preview branch URL | allowlist 内 Google account | preview の内容を表示できる | | |
| Cloudflare Access logs | 上記確認後 | allow / deny の記録が見える | | |

#49 時点で dashboard 本体がまだ Cloudflare Pages に deploy されていない場合は、Pages の初期ページや placeholder 表示でも Access 確認として扱えます。ただし #50 の publish flow 移行完了とは分けて記録します。

## #50 への引き継ぎ

| 項目 | 記録 |
|---|---|
| Pages project名 | `ps-analyzer` |
| production URL | `https://ps-analyzer.pages.dev`。deploy 検証用として扱う |
| チーム限定本番URL | custom domain + Cloudflare Access で後続確保する |
| deployment mode | |
| production branch | |
| preview branch 対象 | |
| preview URL 例 | |
| GitHub App repository access | |
| #50 で必要な GitHub secrets / vars | |
| GitHub Actions summary に表示する URL | |
| #50 で変更してよい workflow | `.github/workflows/collect-streams.yml`, `.github/workflows/publish-dashboard.yml` 候補 |
| #49 で未変更の workflow | すべて未変更 |

## #51 への引き継ぎ

| 項目 | 記録 |
|---|---|
| Save API の deploy 検証 origin 候補 | `https://ps-analyzer.pages.dev` |
| Save API の production origin 候補 | custom domain 確保後に #51 で決定 |
| Save API の preview origin 方針 | |
| `ALLOWED_ORIGINS` に入れる候補 | #51 で決定 |
| Worker 側 Access JWT 検証の要否 | #51 で決定 |
| Access team domain | |
| Access application audience / AUD | |
| One-time PIN fallback を使ったか | |
| #49 で未変更の Worker | `workers/save-deck-links/worker.mjs` は未変更 |

## #47 への引き継ぎ

| 項目 | 記録 |
|---|---|
| Cloudflare Pages `pages.dev` deploy 確認 | 未確認 / 確認済み: |
| production custom domain + Access 確認 | 未確認 / 確認済み: |
| Cloudflare Pages preview の Access 確認 | 未確認 / 確認済み: |
| #50 publish flow 移行 | 未完了 / 完了: |
| GitHub Pages root 停止/無害化の開始可否 | 限定公開本番URL確保後に判断 |
| GitHub Pages preview 停止/無害化の開始可否 | 限定公開本番URL確保後に判断 |
| public stub が必要な場合の禁止事項 | `data/*.json`、`save_api_endpoint`、deck/timeline payload を含めない |

## #53 への引き継ぎ

| 運用項目 | #53 で整備する内容 |
|---|---|
| 許可ユーザー追加 | Google account email 追加手順、承認者、反映確認 |
| 許可ユーザー削除 | 退任時削除、棚卸し頻度、Access logs 確認 |
| Google login 障害 | One-time PIN fallback を使う条件、期限、戻し手順 |
| preview確認 | PR / branch preview URL の探し方、Access 確認 |
| Save API 障害 | Access、CORS、Worker、GitHub API token、branch allowlist の切り分け |
| GitHub / Cloudflare 管理分離 | repository collaborator と Access 閲覧者を同一管理にするか、別管理にするか |

## #50 publish flow 確認欄

| 確認項目 | 記録 |
|---|---|
| Cloudflare Pages project名 | `ps-analyzer` |
| production URL | `https://ps-analyzer.pages.dev`。deploy 検証用として扱う |
| GitHub Actions deploy方式 | `dashboard-site` artifact を download し、`wrangler pages deploy dashboard --project-name ps-analyzer` で direct upload |
| #49 初回deploy失敗理由 | Cloudflare Pages側で Workers向け `npx wrangler deploy` が実行され、GitHub Actions生成前提の静的directoryを検出できなかった |
| Cloudflare側Git integration自動deploy | 未確認 / 無効化済み / direct uploadと競合しない設定へ変更済み: |
| `Restrict previews` の範囲 | preview deployment URLのみ。production `pages.dev` と custom domain は Zero Trust 側で別管理 |
| GitHub Pages直URL停止 | #47で実施。ただし限定公開本番URL確保後まで進めない。#50では `gh-pages` branch、Pages settings、過去previewを変更しない |

## GitHub secrets / vars 候補

この checklist は候補整理のみです。secret 値そのものは repository、PR、artifact、docs に残しません。

| 名前候補 | 種別候補 | 用途 | 後続 issue |
|---|---|---|---|
| `CF_PAGES_PROJECT_NAME` | variable | Pages project名。初期値候補は `ps-analyzer` | #50 |
| `CLOUDFLARE_ACCOUNT_ID` | variable または secret | GitHub Actions から Cloudflare Pages direct upload する account を指定する | #50 |
| `CLOUDFLARE_API_TOKEN` | secret | GitHub Actions から Cloudflare Pages へ deploy する。権限は Account / Cloudflare Pages / Edit を候補にする | #50 |
| `PAGES_BASE_URL` | variable | workflow summary に出す production URL。初期値候補は `https://ps-analyzer.pages.dev` | #50 |
| `CF_ACCESS_TEAM_DOMAIN` | variable | Access JWT 検証や運用 docs で team domain を参照する場合に使う | #51/#53 |
| `CF_ACCESS_AUD` | variable または secret | Worker 側で Access JWT の audience を検証する場合に使う | #51 |
| `SAVE_API_ENDPOINT` | variable | dashboard から呼ぶ Save API endpoint。#49 では変更しない | #51 |

## 記録時の禁止事項

- OAuth client secret、Cloudflare API token、Access cookie、Access JWT、GitHub token を記録しない。
- 許可ユーザーの個別メールアドレスを repository に残す場合は、人間が許容した範囲だけにする。
- Cloudflare dashboard の secret 値や token 値を screenshot / artifact に残さない。
- #49 の PR 差分に `.codex/tmp/`、一時メモ、secret 値を含めない。
