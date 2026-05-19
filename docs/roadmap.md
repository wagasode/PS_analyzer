# PS_analyzer ロードマップ

## この文書の位置づけ

この roadmap は一時的な TODO リストではなく、PS_analyzer 開発全体の優先順位を継続的に整理する living document です。

Cloudflare Access 移行や戦績管理ページ実装は現在の重点テーマですが、それらが完了した後もこの文書の役割は終わりません。新しい重点テーマ、週単位・月単位の優先順位、保留中の判断事項が変わるたびに更新します。

各時点の roadmap は、その時点で「次に何を優先するか」を判断するための共有基準として扱います。完了したテーマは必要に応じて整理し、新しい重点 issue や後続テーマを追加します。

## 方針

PS_analyzer は、配信データ、デッキ情報、戦績情報をチーム内限定で確認する分析基盤として整備します。

短期的には、既存の配信ダッシュボードとデッキ保存機能を維持しながら、公開範囲を Cloudflare Access 配下へ移行します。その後、戦績管理ページを追加し、配信、デッキ、戦績を同じ分析導線で扱える状態を目指します。

## 2026年5月の目標

- PS_analyzer の上位方針、プロダクト要件、ロードマップを明文化する
- Cloudflare Access 移行の issue 群を整理し、依存関係を確認する
- 公開済みデータの棚卸しを始める
- GitHub Pages 直URL、Cloudflare Pages、Access、Save API Worker の責務を分ける
- 戦績管理ページの限定公開設計を始める
- 実装 issue とセキュリティ hardening issue を混ぜずに進める

## 2026年6月の目標

- Cloudflare Pages + Access による限定公開基盤を作成する
- dashboard publish flow を Cloudflare Pages 前提へ移行する
- GitHub Pages 直URLを停止、または無害化する
- Save API Worker を Access 前提で保護する
- Access 移行後の運用ドキュメントを整備する
- 戦績管理ページの MVP スコープを確定し、最小実装に着手する

## 現在の重点issue

2026年5月時点の重点 issue は、限定公開化と戦績管理の設計です。

- #15: PS_analyzer全体をCloudflare Access配下へ移行する
- #46: 公開データ棚卸しと分類を行う
- #47: GitHub Pages直URLを停止・無害化する
- #48: PS_analyzerリポジトリをprivate化する影響を確認する
- #49: Cloudflare Pages + Access配信基盤を作成する
- #50: dashboard publish flowをCloudflare Pagesへ移行する
- #51: Save API WorkerをAccess前提で保護する
- #52: 戦績管理ページの限定公開設計を行う
- #53: Cloudflare Access移行後の運用ドキュメントを整備する

これらは1つの巨大 issue として扱わず、公開データ棚卸し、配信基盤、保存API保護、運用文書、戦績管理設計に分けて進めます。

## Cloudflare Access移行ロードマップ

### 1. 現状棚卸し

- 公開済みデータを分類する
- GitHub Pages 直URLで見えている内容を確認する
- repository private 化の影響を確認する
- Save API Worker の公開面と保存権限を整理する

主な関連 issue: #46, #47, #48

### 2. 限定公開基盤の作成

- Cloudflare Pages + Access の配信基盤を作る
- チーム内閲覧者のアクセス条件を定義する
- preview と本番公開の扱いを決める

主な関連 issue: #49

### 3. publish flow の移行

- dashboard publish flow を Cloudflare Pages 前提へ移行する
- GitHub Actions summary や preview 確認の導線を維持する
- GitHub Pages 依存を段階的に外す

主な関連 issue: #50

### 4. Save API Worker の保護

- Save API Worker を Access 前提で保護する
- repository、branch、origin、payload schema の検証を維持する
- CORS allowlist と認証の責務を分けて説明できる状態にする

主な関連 issue: #51

### 5. 運用ドキュメント整備

- Access 移行後の閲覧、保存、preview、障害時確認の手順を書く
- チーム内共有URLと管理者向け作業を分ける
- セキュリティ判断と日常運用の境界を明確にする

主な関連 issue: #53

## 戦績管理ページロードマップ

### 1. 限定公開前提の設計

- 誰が閲覧、入力、編集するかを決める
- 戦績データとして必要な最小項目を決める
- 配信データ、デッキ情報との関係を整理する

主な関連 issue: #52

### 2. MVPスコープ決定

- 試合日、イベント、選手、相手、使用デッキ、勝敗、メモを最小候補にする
- 入力方法を CSV、静的フォーム、Save API 拡張のどれに寄せるか判断する
- 最初の画面は一覧と基本集計を中心にする

### 3. 初期ページ作成

- 戦績一覧を表示する
- デッキ別、選手別、期間別の基本集計を表示する
- 未入力や要確認のデータを見つけやすくする

### 4. 横断分析への拡張

- 配信アーカイブ、デッキ、戦績を横断して確認する
- 大会や練習期間ごとの振り返りをしやすくする
- 対戦相手、クラス、アーキタイプ単位の傾向を確認できるようにする

## 保留中の判断事項

- repository を private 化する場合の GitHub Actions、Pages、Cloudflare 連携への影響
- GitHub Pages 直URLを完全停止するか、無害化した状態で残すか
- Cloudflare Pages の preview を PR ごとにどう扱うか
- Cloudflare Access の閲覧者管理をどの単位で運用するか
- Save API Worker を Access 配下に置いた後のローカル検証方法
- 戦績データをどの形式で管理するか
- 戦績入力を誰が担当し、どの粒度で確認済みにするか
- 配信データ、デッキ情報、戦績情報のキー設計をどこまで共通化するか
- MVP で扱う分析指標と、将来拡張へ回す指標の境界
