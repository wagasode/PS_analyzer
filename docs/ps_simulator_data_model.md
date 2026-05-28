# PS 7デッキ制シミュレーター データモデル

この文書は、PS 7デッキ制シミュレーターのWebUI、将来のGoogle Sheets取込、相性表、バトルログで共有する正規化済みJSONのデータモデルを定義する。

Issue #64 の範囲では、Google Sheets API連携、提出UI、相性表読込、バトル実行は実装しない。後続Issueが同じIDとJSON形を参照できるように、repo-localのサンプルJSONを固定する。Issue #69 では、このデータモデルに基づくBattleLog構造とJSON preview / exportを固定する。

## 基本方針

- WebUIで扱う主キーは表示名ではなく、安定した `deckId` / `playerId` にする。
- `deckName` と `playerName` は表示用の値であり、参照や保存の主キーにしない。
- `className` は既存WebUIの7クラス値 `E`, `R`, `W`, `D`, `Ni`, `B`, `Nm` に統一する。
- 既存 `data/decks.csv` にあるデッキを使う場合は、原則として `deck_key` をそのまま `deckId` として扱う。
- 既存CSVにまだ存在しないシミュレーター専用サンプルデッキは、`ps-<class>-<slug>` 形式の安定IDを使う。
- Google Sheetsなど外部入力の列名、表記揺れ、空欄処理は取込層で吸収し、WebUIにはこの文書の正規化済みJSONだけを渡す。

## 正規化済みJSON

最小サンプルは `data/ps_simulator/sample_dataset.json` に置く。トップレベルは次の責務を持つ。

- `schemaVersion`: データ形の互換性を判断するためのバージョン。
- `classDefinitions`: 7クラスの表示名と安定値。
- `decks`: 提出候補デッキ。
- `players`: 提出担当候補の選手。
- `playerDeckStatuses`: 選手ごとのデッキ使用可能度。
- `sampleSubmission`: 後続の提出UIが初期表示とJSONプレビューに使える提出案。
- `sampleMatchups`: 後続の相性表読込やバトル機能が参照できる最小例。
- `sampleBattleLog`: 後続のログ保存、再生UI、分岐再シミュレーションが参照できる最小例。

## Deck

デッキ候補を表す。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `deckId` | yes | デッキの安定ID。既存CSV由来なら `deck_key` と同値にする。 |
| `className` | yes | `E`, `R`, `W`, `D`, `Ni`, `B`, `Nm` のいずれか。 |
| `deckName` | yes | UI表示名。主キーとして使わない。 |
| `weaknessTags` | yes | 弱点や注意点を表す文字列配列。未設定なら空配列。 |
| `note` | yes | 補足メモ。未設定なら空文字。 |
| `source` | no | `repo_csv`, `repo_sample`, `google_sheets` などの由来。 |
| `sourceDeckKey` | no | 既存 `data/decks.csv` の `deck_key` と対応する場合の元キー。 |

## Player

提出担当候補の選手を表す。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `playerId` | yes | 選手の安定ID。 |
| `playerName` | yes | UI表示名。主キーとして使わない。 |
| `team` | no | 所属チーム名。表示や絞り込み用。 |
| `note` | no | 補足メモ。 |

## PlayerDeckStatus

選手が各デッキをどの程度使えるかを表す。提出UIでは `hard` をリスク警告、`trainable` を練習負荷として表示する。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `playerId` | yes | `players[].playerId` への参照。 |
| `deckId` | yes | `decks[].deckId` への参照。 |
| `status` | yes | `confident`, `available`, `trainable`, `hard` のいずれか。 |
| `practiceCost` | yes | 練習負荷の数値。0以上の整数。 |
| `note` | yes | 補足メモ。未設定なら空文字。 |

## Submission

7デッキをA/B/Cに3/2/2で割り当てる提出案を表す。自分側と相手側の両方で同じ形を使う。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `submissionId` | no | 提出案を識別する任意ID。 |
| `side` | yes | `self` または `opponent`。 |
| `assignments` | yes | A/B/Cの割当配列。 |

`assignments` の各要素は次の形にする。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `role` | yes | `A`, `B`, `C` のいずれか。 |
| `playerId` | yes | 担当選手。 |
| `deckIds` | yes | その担当者に割り当てるデッキID配列。Aは3件、B/Cは2件。 |

提出UIの基本バリデーションは次を確認する。

- 提出全体で7デッキが選ばれている。
- 選ばれた7デッキの `className` が7クラスを重複なく網羅している。
- A/B/Cの割当数が3/2/2である。
- `playerDeckStatuses` を参照し、`hard` と `trainable` をリスクとして表示できる。

## ラウンド候補生成と使用済みデッキ制約

バトル進行UIと将来の `BattleLog` / 振り返りUIは、次の候補生成を正とする。候補生成は自分側と相手側で独立に行い、片側で使用済みになったデッキIDは反対側の候補生成には影響しない。

| ラウンド | 候補生成 |
| --- | --- |
| R1 | Aに割り当てられた3デッキ。 |
| R2 | Bに割り当てられた2デッキ。 |
| R3 | Cに割り当てられた2デッキ。 |
| R4 | R1〜R3で使用されなかった4デッキ。 |
| R5 | R1〜R4で使用されなかった3デッキ。 |

使用済みデッキ制約は次を保証する。

- 一度選出されたデッキは勝敗に関係なく使用済み扱いにする。
- 使用済みデッキは以降のラウンド候補から除外し、再選択できない。
- 自分側と相手側の使用済みデッキ集合は独立に管理する。
- リセット時は使用済みデッキ、選出、勝敗、スコア、最終結果を初期化する。
- 正常な提出案では候補数が R1=3、R2=2、R3=2、R4=4、R5=3 になる。

現行UIでは進行中ラウンドだけを選出でき、確定済みの過去ラウンドを直接変更する操作は提供しない。将来、過去ラウンドの選出変更を許可する場合は、変更したラウンド以降の選出、勝敗、スコア、使用済みデッキを破棄して再計算する。後続ラウンドの状態を保持したまま過去ラウンドだけを差し替える仕様にはしない。

不正な提出案、重複 `deckId`、存在しない `deckId`、割当数不足などは提出UIのバリデーションで開始不可にする。候補生成側も重複IDを候補として二重表示せず、候補数が期待値と異なる場合は警告として扱う。

## Matchup

デッキ同士の相性を表す。Issue #64 では読込や評価は行わず、保存可能な形だけを固定する。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `deckIdA` | yes | A側デッキID。 |
| `deckIdB` | yes | B側デッキID。 |
| `winRateForA` | yes | A側の勝率。0.0から1.0の数値。 |
| `note` | no | 補足メモ。 |

## BattleRoundLog

1ラウンド分の候補、選出、勝率、勝敗、スコア、使用済みデッキを表す。再生UI、分岐再シミュレーション、1枚スクショ向けサマリー表示の入力にするため、各ラウンド開始時点の候補とラウンド終了後の状態を両方残す。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `roundNumber` | yes | 1始まりのラウンド番号。 |
| `selfCandidateDeckIds` | yes | 自分側で選出可能だったデッキID配列。後方互換用の平坦フィールド。 |
| `opponentCandidateDeckIds` | yes | 相手側で選出可能だったデッキID配列。後方互換用の平坦フィールド。 |
| `candidateDeckIds` | yes | `self` / `opponent` ごとの候補デッキID配列。 |
| `selfSelectedDeckId` | yes | 自分側の選出デッキ。 |
| `opponentSelectedDeckId` | yes | 相手側の選出デッキ。 |
| `selectedDeckIds` | yes | `self` / `opponent` ごとの選出デッキID。 |
| `selfWinRate` | yes | そのラウンドの自分側勝率。0.0から1.0の数値。 |
| `winRate` | yes | `self` / `opponent` ごとの勝率。 |
| `winRateSource` | yes | 勝率の由来。`type` は `matchup`, `reverseMatchup`, `fallback`, `manual`, `unknown` のいずれか。 |
| `winRateNote` | yes | UI表示向けの短い由来説明。 |
| `result` | yes | `self_win` または `opponent_win`。未確定ラウンドでは `null`。 |
| `resultDecisionMethod` | yes | 勝敗決定方法。確定済みラウンドでは `random` または `manual`。未確定ラウンドでは `null`。 |
| `resultDecision` | yes | `method`, `randomValue`, `seedInput`, `note` を持つ決定詳細。手動決定では `randomValue` は `null`。未確定ラウンドでは `null`。 |
| `scoreAfterRound` | yes | ラウンド終了後のスコア。`self` / `opponent` の勝ち数を持つ。 |
| `usedDeckIdsAfterRound` | yes | ラウンド終了後の使用済みデッキ。`self` / `opponent` の配列を持つ。 |
| `remainingDeckIdsAfterRound` | yes | ラウンド終了後の残りデッキ。`self` / `opponent` の配列を持つ。 |
| `candidateWarnings` | yes | 候補数不足など、ログ生成時に検知した警告。問題がなければ空配列。 |

`winRateSource.type = manual` は将来の手入力勝率用の予約値とする。現行UIでは生成しない。現行UIが生成する値は、選出前の `unknown`、相性表の正方向 `matchup`、逆方向 `reverseMatchup`、相性表未接続時の `fallback` である。

### BattleRoundLog canonical / alias 方針

BattleLog v1では、後続UIが読みやすいネストフィールドと、既存UI・簡易参照・後方互換のための平坦フィールドを両方保持する。ネストフィールドをcanonicalとし、平坦フィールドはaliasとする。canonicalとaliasは常に同値でなければならない。将来の振り返りUIや1枚スクショ向けサマリーカード実装では、原則としてcanonical側を参照する。

| canonical | alias |
| --- | --- |
| `candidateDeckIds.self` | `selfCandidateDeckIds` |
| `candidateDeckIds.opponent` | `opponentCandidateDeckIds` |
| `selectedDeckIds.self` | `selfSelectedDeckId` |
| `selectedDeckIds.opponent` | `opponentSelectedDeckId` |
| `scoreAfterRound` | `score` |
| `usedDeckIdsAfterRound.self` | `selfUsedDeckIds` |
| `usedDeckIdsAfterRound.opponent` | `opponentUsedDeckIds` |
| `remainingDeckIdsAfterRound.self` | `selfRemainingDeckIds` |
| `remainingDeckIdsAfterRound.opponent` | `opponentRemainingDeckIds` |

aliasを残す理由は、既存のJSONプレビュー、単純な検証、軽量なUI実装から直接参照しやすくするためである。新規実装ではcanonical側を優先し、aliasは表示や後方互換の補助として扱う。

## BattleLog

バトル全体の再現に必要な情報を表す。MVPで永続保存しない場合でも、保存・共有・後続UIへ渡せるJSON形式として固定する。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `logVersion` | yes | BattleLogの互換性を判断するためのバージョン。初期値は `ps-battle-log.v1`。 |
| `createdAt` | yes | 現在のBattleLog状態が生成・初期化された時刻。ISO 8601文字列。 |
| `seed` | yes | 抽選勝敗の再現に使う文字列。 |
| `selfSubmissionId` | yes | 自分側提出案ID。 |
| `opponentSubmissionId` | yes | 相手側提出案ID。 |
| `selfSubmissionSnapshot` | yes | 自分側提出案のスナップショット。担当選手、割当デッキ、表示名を含む。 |
| `opponentSubmissionSnapshot` | yes | 相手側提出案のスナップショット。担当選手、割当デッキ、表示名を含む。 |
| `rounds` | yes | `BattleRoundLog` 配列。R1〜R5の進行済みラウンドを順番に持つ。 |
| `finalResult` | yes | 最終結果。未完了なら `null`。完了時は `winner`, `result`, `selfWins`, `opponentWins`, `score`, `finishedAtRound` を持つ。 |
| `finishedAtRound` | yes | 3勝先取またはR5到達で試合が確定したラウンド番号。未完了なら `null`。 |

`selfSubmissionSnapshot` / `opponentSubmissionSnapshot` の `assignments` は、`role`, `playerId`, `playerSnapshot`, `deckIds`, `deckSnapshots` を持つ。`deckSnapshots` には `deckId`, `className`, `deckName`, `source`, `sourceDeckKey` を残す。後からデッキ名が変わっても、BattleLog単体で当時の選出と表示名を復元できるようにする。

`createdAt` は、現在のBattleLog状態が生成・初期化された時刻を表す。現行UIではバトル状態の初期化時とリセット時に更新する。これは試合開始時刻やJSON export時刻とは限らない。将来的に必要になった場合は、`startedAt` や `exportedAt` を別フィールドとして追加する。

## BattleLog JSON preview / export

PSシミュレーターUIのJSONプレビューでは、提出案、バリデーション結果、BattleLogを同時に確認できる。`battleLog` / `battle` には同じBattleLog payloadを出し、`BattleLog JSONを保存` ボタンはBattleLog単体を `.json` としてダウンロードする。

#69ではブラウザ内stateからBattleLogを組み立て、JSONとして人間が読めることを確認できる範囲に留める。永続DB保存、再生UI、サマリーカードUI、Canvas/PNG export、Discord連携、Google Sheets連携、相性表本実装、自動選出、最適化は扱わない。

## 将来の1枚スクショ向けサマリーカード設計メモ

後続Issueでは、BattleLogを入力として、R1〜R5の流れを1画面に収まりやすいサマリー表示へ変換する。#69のBattleLogから、次を追加問い合わせなしで取り出せる前提にする。

- 試合全体の最終結果、勝者、スコア、`finishedAtRound`。
- R1〜R5の自分側/相手側の候補、選出、勝敗、勝率、勝率由来。
- 各ラウンド後のスコア推移、使用済みデッキ、残りデッキ。
- R4/R5の候補デッキ。
- `seed` と、各ラウンドの勝敗が `random` か `manual` か。
- 提出案snapshot内の担当選手名、デッキ名、クラス。

サマリーカード側はBattleLogを表示専用入力として扱う。初期段階では、ブラウザ上で人間が手動スクショを撮れる1画面表示を作るだけでよい。PNG export、自動画像生成、Discord API連携、SNS投稿機能、分岐再シミュレーション、複雑なアニメーション、スマホ最適化は後続のさらに別Issueに分ける。

## 外部入力との境界

Google Sheetsなどの外部入力は、列名や表記揺れを含む生データとして扱う。WebUIやバトル処理は生データを直接読まない。

将来の取込層は次を担当する。

- デッキ名、クラス表記、選手名の表記揺れを安定IDへ変換する。
- 既存 `data/decks.csv` と対応するデッキは `deck_key` を `deckId` に写す。
- シミュレーター専用の新規デッキには安定した `deckId` を割り当てる。
- `status` や `side` などの列値を許可値へ正規化する。
- 正規化後のJSONをこの文書の形でWebUIへ渡す。
