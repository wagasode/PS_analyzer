# PS 7デッキ制シミュレーター データモデル

この文書は、PS 7デッキ制シミュレーターのWebUI、将来のGoogle Sheets取込、相性表、バトルログで共有する正規化済みJSONのデータモデルを定義する。

Issue #64 の範囲では、Google Sheets API連携、提出UI、相性表読込、バトル実行は実装しない。後続Issueが同じIDとJSON形を参照できるように、repo-localのサンプルJSONを固定する。

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

## Matchup

デッキ同士の相性を表す。Issue #64 では読込や評価は行わず、保存可能な形だけを固定する。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `deckIdA` | yes | A側デッキID。 |
| `deckIdB` | yes | B側デッキID。 |
| `winRateForA` | yes | A側の勝率。0.0から1.0の数値。 |
| `note` | no | 補足メモ。 |

## BattleRoundLog

1ラウンド分の候補、選出、勝敗、使用済みデッキを表す。再生UIと将来の分岐再シミュレーションのため、各ラウンド開始時点の候補と選出結果を両方残す。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `roundNumber` | yes | 1始まりのラウンド番号。 |
| `selfCandidateDeckIds` | yes | 自分側で選出可能だったデッキID配列。 |
| `opponentCandidateDeckIds` | yes | 相手側で選出可能だったデッキID配列。 |
| `selfSelectedDeckId` | yes | 自分側の選出デッキ。 |
| `opponentSelectedDeckId` | yes | 相手側の選出デッキ。 |
| `selfWinRate` | yes | そのラウンドの自分側勝率。0.0から1.0の数値。 |
| `result` | yes | `self_win` または `opponent_win`。 |
| `usedDeckIdsAfterRound` | yes | ラウンド終了後の使用済みデッキ。`self` と `opponent` の配列を持つ。 |

## BattleLog

バトル全体の再現に必要な情報を表す。MVPで永続保存しない場合でも、保存可能なJSON形式として固定する。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `seed` | yes | 乱数や手動選出の再現に使う文字列。 |
| `selfSubmissionId` | no | 自分側提出案ID。 |
| `opponentSubmissionId` | no | 相手側提出案ID。 |
| `rounds` | yes | `BattleRoundLog` 配列。 |
| `finalResult` | yes | 最終結果。`winner`, `selfWins`, `opponentWins` を持つ。 |

## 外部入力との境界

Google Sheetsなどの外部入力は、列名や表記揺れを含む生データとして扱う。WebUIやバトル処理は生データを直接読まない。

将来の取込層は次を担当する。

- デッキ名、クラス表記、選手名の表記揺れを安定IDへ変換する。
- 既存 `data/decks.csv` と対応するデッキは `deck_key` を `deckId` に写す。
- シミュレーター専用の新規デッキには安定した `deckId` を割り当てる。
- `status` や `side` などの列値を許可値へ正規化する。
- 正規化後のJSONをこの文書の形でWebUIへ渡す。
