from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from ps_simulator_ui import (  # noqa: E402
    EXPECTED_ROUND_CANDIDATE_COUNTS,
    HTML2CANVAS_PUBLIC_LICENSE_PATH,
    HTML2CANVAS_PUBLIC_PATH,
    PS_SIMULATOR_PUBLIC_DATASET_PATH,
    battle_remaining_deck_ids_for_side,
    read_ps_simulator_sample_dataset,
    render_ps_simulator_html,
    reset_battle_rounds_from,
    write_ps_simulator_assets,
    battle_candidate_deck_ids_for_round,
    battle_used_deck_ids_for_side,
    validate_round_candidate_count,
)
from player_profiles import PLAYER_PROFILES_PUBLIC_PATH  # noqa: E402


class PsSimulatorUiTest(unittest.TestCase):
    def test_rendered_ui_fetches_repo_local_sample_dataset_copy(self) -> None:
        html = render_ps_simulator_html()

        self.assertIn('const datasetUrl = "data/ps_simulator/sample_dataset.json";', html)
        self.assertIn('const playerProfilesUrl = "data/player_profiles.json";', html)
        self.assertIn("fetch(datasetUrl)", html)
        self.assertIn("async function loadPlayerProfiles()", html)
        self.assertIn("function mergePlayerProfilesIntoDataset(dataset, profilePayload)", html)
        self.assertIn("function playerDisplayName(player)", html)
        self.assertIn("function playerTeamName(player)", html)
        self.assertIn("function validateSubmission(submission)", html)
        self.assertIn("function candidateDeckIdsForRound(submission, roundNumber, usedDeckIds)", html)
        self.assertIn("function usedDeckIdsForSideFromRounds(rounds, side, options = {})", html)
        self.assertIn("function resetRoundsFrom(roundNumber, shouldRender = true)", html)
        self.assertIn("function validateRoundCandidates(roundNumber, candidateDeckIds)", html)
        self.assertIn("usedDeckIdsAfterRound", html)
        self.assertIn("remainingDeckIdsAfterRound", html)
        self.assertIn("将来編集可能にする場合", html)
        self.assertIn("PSルール戦略シミュレータ", html)
        self.assertIn('<nav class="site-nav" aria-label="主要ページ">', html)
        self.assertIn('<a class="nav-link" href="index.html">トップ</a>', html)
        self.assertIn('<a class="nav-link" href="streaming-report.html">配信レポート</a>', html)
        self.assertIn('<a class="nav-link active" aria-current="page" href="ps-simulator.html">PSルール戦略シミュレータ</a>', html)
        self.assertNotIn('<a class="button" href="index.html">トップへ戻る</a>', html)
        self.assertNotIn("配信レポートへ戻る", html)
        self.assertIn("ラウンド進行シミュレータ", html)
        self.assertNotIn("バトル進行MVP", html)
        self.assertNotIn("提出案を自分側・相手側にセットして、R1〜R5を手動選出で進めます。", html)
        self.assertNotIn('<label class="field">提出側', html)
        self.assertNotIn('id="submission-side"', html)
        self.assertIn('id="set-active-submission" type="button">提出案をセット</button>', html)
        self.assertNotIn("各側の提出案をセット", html)
        self.assertNotIn('id="set-self-submission" type="button">自分側</button>', html)
        self.assertNotIn('id="set-opponent-submission" type="button">相手側</button>', html)
        self.assertNotIn('id="set-both-submission" type="button">両側</button>', html)
        self.assertIn('id="team-filter-grid"', html)
        self.assertIn("自分側チーム", html)
        self.assertIn("相手側チーム", html)
        self.assertIn("全選手", html)
        self.assertIn("未設定", html)
        self.assertIn("assignmentDrafts", html)
        self.assertIn("teamFilters", html)
        self.assertIn("function availableTeamOptions()", html)
        self.assertIn("function playersForSide(side)", html)
        self.assertIn("function ensureAssignmentPlayersMatchTeam(side)", html)
        self.assertIn("function currentSubmission(side = state.side)", html)
        self.assertIn("data-side-team", html)
        self.assertIn("data-side-picker", html)
        self.assertIn("aria-pressed", html)
        self.assertNotIn("A/B/Cの候補", html)
        self.assertNotIn("候補 ${candidatePlayers.length}選手", html)
        self.assertIn("teamFilter", html)
        self.assertIn("teamName", html)
        self.assertNotIn("サンプル提出でラウンドをリセット", html)
        self.assertIn("相性表における勝率", html)
        self.assertNotIn("採用勝率", html)
        self.assertIn("相性表未定義のため0.5", html)
        self.assertIn("function buildMatchupIndex(dataset, options = {})", html)
        self.assertIn("function lookupSelfWinRate(selfDeckId, opponentDeckId)", html)
        self.assertIn("function matchupStatus()", html)
        self.assertIn("相性表fixtureの行デッキ視点を使用しています。", html)
        self.assertNotIn('id="battle-throw-advice"', html)
        self.assertNotIn("3/2/2 投げ判定", html)
        self.assertIn("参考評価", html)
        self.assertIn("active-throw-advice-details", html)
        self.assertIn("throwAdviceDetailsOpen", html)
        self.assertIn("const matchupStatsThresholds", html)
        self.assertIn("function buildMatchupStatsForCandidate(selfDeckId, opponentDeckIds, options = {})", html)
        self.assertIn("function buildOpponentMatchupStatsForCandidate(opponentDeckId, selfDeckIds)", html)
        self.assertIn("function buildBattleThrowAdvice(deckSet)", html)
        self.assertIn("function activeThrowAdviceDetailsHtml(advice)", html)
        self.assertIn("function autoSelectOpponentLikelyDeck()", html)
        self.assertIn("function battleThrowDeckSetForRound(roundOrNumber)", html)
        self.assertIn("round.selfCandidateDeckIds", html)
        self.assertIn("round.opponentCandidateDeckIds", html)
        self.assertIn('id="auto-opponent-pick"', html)
        self.assertIn("相手自動選択", html)
        self.assertIn("buildBattleThrowAdvice(battleThrowDeckSetForRound(active))", html)
        self.assertNotIn("candidateDeckIdsForRound(state.battle?.selfSubmission, roundNumber, [])", html)
        self.assertNotIn("candidateDeckIdsForRound(state.battle?.opponentSubmission, roundNumber, [])", html)
        self.assertIn('document.querySelector("#battle-current-round .active-throw-advice-details")?.addEventListener("toggle"', html)
        self.assertIn('document.getElementById("auto-opponent-pick")?.addEventListener("click", autoSelectOpponentLikelyDeck)', html)
        self.assertNotIn("function renderBattleThrowAdvice()", html)
        self.assertIn("function buildOpponentLikelyPick(selfDeckIds, opponentDeckIds)", html)
        self.assertIn("総合おすすめ", html)
        self.assertIn("安定投げ", html)
        self.assertIn("攻撃的投げ", html)
        self.assertIn("不利候補", html)
        self.assertIn("相手有力候補", html)
        self.assertIn("参考評価を見る", html)
        self.assertIn("評価基準", html)
        self.assertIn("候補別の数値", html)
        self.assertIn("Score = 平均勝率(%)", html)
        self.assertIn("5分: 50% / 微有利: 51%〜59% / 有利: 60%以上 / 微不利: 41%〜49% / 不利: 40%以下。", html)
        self.assertIn("function winRateCategoryCounts(details)", html)
        self.assertIn("neutralCount", html)
        self.assertIn("slightFavorableCount", html)
        self.assertIn("slightUnfavorableCount", html)
        self.assertIn("favorableCount: details.filter(detail => detail.winRate >= matchupStatsThresholds.strong).length", html)
        self.assertIn("unfavorableCount: details.filter(detail => detail.winRate <= matchupStatsThresholds.danger).length", html)
        self.assertIn("throw-advice-candidate-card", html)
        self.assertIn("throw-advice-metric-grid", html)
        self.assertIn("throw-advice-breakdown-grid", html)
        self.assertIn("function throwAdviceCandidateBreakdownMetricsHtml(candidate)", html)
        self.assertIn("function throwAdviceMetricIfNonZeroHtml(label, value)", html)
        self.assertIn('Number(value) === 0 ? ""', html)
        self.assertIn("throwAdviceCandidateBreakdownMetricsHtml(lowest)", html)
        self.assertIn("throw-advice-modal-button", html)
        self.assertIn("throw-advice-modal-backdrop", html)
        self.assertIn("throw-advice-modal-subject", html)
        self.assertIn("対象デッキ", html)
        self.assertIn("${label}の内訳: ${deckDisplayNameById(candidate.deckId)}", html)
        self.assertIn(".active-throw-advice-details[open] > summary::before", html)
        self.assertIn(".throw-advice-disclosure[open] > summary::before", html)
        self.assertNotIn(".active-throw-advice-details[open] summary::before", html)
        self.assertNotIn(".throw-advice-disclosure[open] summary::before", html)
        self.assertIn("data-throw-advice-modal-id", html)
        self.assertIn("function openThrowAdviceModal(modalId)", html)
        self.assertIn("function closeThrowAdviceModal()", html)
        self.assertNotIn("Score内訳", html)
        self.assertNotIn("throw-advice-table", html)
        self.assertNotIn("function throwAdviceDisclosureHtml", html)
        self.assertNotIn("勝率40%以下候補", html)
        self.assertNotIn("40%以下対面を含む候補です。", html)
        self.assertNotIn("40%以下対面はありません。", html)
        self.assertNotIn("まとめて見た候補です。", html)
        self.assertNotIn("強有利", html)
        self.assertNotIn("危険候補", html)
        self.assertNotIn("危険数", html)
        self.assertNotIn("欠損数 × 5", html)
        self.assertNotIn("missingCount: -5", html)
        self.assertNotIn("throwAdviceScoreWeights", html)
        self.assertNotIn("最低勝率(%) × 0.3", html)
        self.assertNotIn("有利: 50%以上 / 不利: 50%未満", html)
        self.assertNotIn("favorable: 0.5", html)
        self.assertIn("40%以下", html)
        self.assertNotIn("相手CPU", html)
        self.assertNotIn("40%未満", html)
        self.assertNotIn("参考評価: 総合", html)
        self.assertNotIn("一部の相性データが欠損しているため、評価は参考値です。", html)
        self.assertIn("仮デッキを含むため、正式デッキ定義確定前の参考値です。", html)
        self.assertIn("function rollBattleRound()", html)
        self.assertIn("function buildBattleLog()", html)
        self.assertIn("function buildBattleRoundLog(round)", html)
        self.assertIn("function battlePreviewPayload()", html)
        self.assertIn("function downloadBattleLogJson()", html)
        self.assertIn("スクショ共有用サマリー", html)
        self.assertIn('id="battle-summary-card"', html)
        self.assertIn("function battleSummaryCardHtml(battleLog)", html)
        self.assertIn("7デッキ概観", html)
        self.assertIn("function battleSummaryOverviewHtml(battleLog)", html)
        self.assertIn("function summarySubmissionDeckItems(logSubmission)", html)
        self.assertIn("function summaryDeckProvisionalLabelHtml(deck)", html)
        self.assertIn('class="battle-summary-overview"', html)
        self.assertIn("summary-overview-grid", html)
        self.assertIn("summary-overview-deck", html)
        self.assertIn("flex-wrap: wrap;", html)
        self.assertIn("display: inline-flex;", html)
        self.assertIn("summary-provisional-label", html)
        self.assertIn("（仮）", html)
        self.assertNotIn("summary-overview-index", html)
        self.assertNotIn("summary-overview-deck-meta", html)
        self.assertNotIn("summarySubmissionMetaText", html)
        self.assertNotIn(".summary-overview-list {\n      display: grid;", html)
        self.assertNotIn("${deckItems.length}/7デッキ", html)
        self.assertNotIn("${item.role ? `${item.role}担当` : \"\"}", html)
        self.assertIn("${battleSummaryOverviewHtml(battleLog)}", html)
        self.assertLess(
            html.index("${battleSummaryOverviewHtml(battleLog)}"),
            html.index("${battleSummaryHeroHtml(battleLog)}"),
        )
        self.assertIn("function renderBattleSummaryCard()", html)
        self.assertIn("roundCandidateDeckIds(round, side)", html)
        self.assertIn('id="download-battle-summary-png"', html)
        self.assertIn("共有用画像を保存", html)
        self.assertIn('id="copy-battle-summary-png"', html)
        self.assertIn("画像をコピー", html)
        self.assertIn('id="battle-summary-export-status"', html)
        self.assertIn('<script src="vendor/html2canvas.min.js"></script>', html)
        self.assertIn("function downloadBattleSummaryPng()", html)
        self.assertIn("async function copyBattleSummaryPng()", html)
        self.assertIn("async function copyPngBlobToClipboard(blob)", html)
        self.assertIn("navigator.clipboard.write", html)
        self.assertIn('new ClipboardItem({ "image/png": blob })', html)
        self.assertIn("async function battleSummaryCardToPngBlob(card)", html)
        self.assertIn('document.querySelector("#battle-summary-card .battle-summary-card")', html)
        self.assertIn("window.html2canvas(card", html)
        self.assertIn("onclone: clonedDocument =>", html)
        self.assertIn("PNG生成に失敗しました。", html)
        self.assertIn("画像コピーに失敗しました。", html)
        self.assertIn("画像をコピーしました。", html)
        self.assertIn("PNG保存ライブラリを読み込めません。", html)
        self.assertIn("完了済みBattleLogでPNG保存できます。", html)
        self.assertNotIn("共有カード本体だけをPNG保存できます。", html)
        self.assertIn("開始時候補", html)
        self.assertIn("function summaryRoundCandidatesHtml(battleLog, round)", html)
        self.assertIn("grid-template-columns: repeat(5, minmax(190px, 1fr));", html)
        self.assertNotIn("round.roundNumber < 4", html)
        self.assertIn(".summary-result-badge.self-win", html)
        self.assertIn(".summary-result-badge.opponent-win", html)
        self.assertNotIn('<span class="badge">BattleLog</span>', html)
        self.assertNotIn("summaryCandidateRoundHtml(battleLog, 4)", html)
        self.assertNotIn("summaryCandidateRoundHtml(battleLog, 5)", html)
        self.assertNotIn("最終デッキ状況", html)
        self.assertNotIn("<span class=\"badge\">seed:", html)
        self.assertNotIn("<span class=\"badge\">finishedAtRound:", html)
        self.assertNotIn("<span class=\"badge\">score:", html)
        self.assertNotIn("<span class=\"badge\">winRateSource:", html)
        self.assertNotIn("<span class=\"badge\">resultDecisionMethod:", html)
        self.assertIn('id="download-battle-log"', html)
        self.assertIn("BattleLog JSONを保存", html)
        self.assertIn('logVersion: "ps-battle-log.v1"', html)
        self.assertIn("createdAt: state.battle.createdAt", html)
        self.assertIn("selfSubmissionSnapshot", html)
        self.assertIn("opponentSubmissionSnapshot", html)
        self.assertIn("winRateSource", html)
        self.assertIn('type: "matchup"', html)
        self.assertIn('type: "fallback"', html)
        self.assertIn('type: "unknown"', html)
        self.assertIn("resultDecisionMethod", html)
        self.assertIn('method: "random"', html)
        self.assertIn('decision.method || "manual"', html)
        self.assertIn("result: round.result || null", html)
        self.assertIn('resultDecisionMethod: round.result ? (round.resultDecisionMethod || "manual") : null', html)
        self.assertIn("resultDecision: round.result ? cloneJson", html)
        self.assertIn("scoreAfterRound", html)
        self.assertIn("finishedAtRound", html)
        self.assertIn("PlayerDeckStatus 行なし", html)
        self.assertIn("データなし / 要確認", html)
        self.assertIn("deck-class-group", html)
        self.assertIn("role-selection-summary", html)
        self.assertIn("summary-deck-chip", html)
        self.assertIn("deck-status-details", html)
        self.assertIn("function compactClassBadgeHtml(className)", html)
        self.assertIn("function statusSummaryHtml(playerId, deckId)", html)
        self.assertIn("class-coverage-badge", html)
        self.assertIn("status-mini.confident", html)
        self.assertIn("status-mini.available", html)
        self.assertIn("頑張れば可", html)
        self.assertIn("きつそう", html)
        self.assertNotIn("自信あり 1", html)
        self.assertNotIn("使用可能 1", html)
        self.assertNotIn("きつそうあり", html)
        self.assertNotIn("要確認あり", html)
        self.assertNotIn("強い注意", html)
        self.assertNotIn("強い警告として扱います", html)
        self.assertNotIn("はhardです", html)
        self.assertNotIn("はtrainableです", html)
        self.assertNotIn("hard / trainable", html)
        self.assertNotIn("担当: データなし", html)
        self.assertIn("function shouldShowClassForRole(role, className)", html)
        self.assertIn("selectedRoles.length === 0 || selectedRoles.includes(role)", html)
        self.assertNotIn("他担当で選択中", html)
        self.assertNotIn("この担当で選択中", html)
        self.assertNotIn('<span class="badge ok">選択中</span>', html)
        self.assertIn("ルール上の制約", html)
        self.assertIn("運用上の注意", html)
        self.assertIn("<details>", html)
        self.assertIn("<summary>開発者向け設定</summary>", html)
        self.assertIn('id="battle-seed"', html)
        self.assertIn("className:", html)
        self.assertIn("debug-dataset-meta", html)
        self.assertIn("schemaVersion", html)
        self.assertIn("function avatarHtml(name, imageUrl, extraClass = \"\")", html)
        self.assertIn("teamName", html)
        self.assertIn("aliases", html)
        self.assertIn('class="player-select-row"', html)
        self.assertIn('"player-avatar", extraClass', html)
        self.assertIn("function playerForDeckInSubmission(submission, deckId)", html)
        self.assertIn("function groupedDeckIdsByPlayer(submission, deckIds)", html)
        self.assertIn("function playerSideHtml(player, fallbackSide)", html)
        self.assertIn("function deckTokenHtml(deckId, options = {})", html)
        self.assertIn("function classOrderIndex(className)", html)
        self.assertIn("function sortDeckIdsByClassOrder(deckIds)", html)
        self.assertIn("function selectedProgressDeckHtml(submission, deckId)", html)
        self.assertIn("function battleSideResultHtml(result, side)", html)
        self.assertIn('class="battle-assignment"', html)
        self.assertIn('class="battle-main-grid"', html)
        self.assertIn('class="deck-token-list"', html)
        self.assertIn('class="battle-result-badge ${won ? "win" : "loss"}"', html)
        self.assertIn('id="battle-self-deck-list"', html)
        self.assertIn('id="battle-opponent-deck-list"', html)
        self.assertIn("function playerSideText(player, fallbackSide)", html)
        self.assertIn("手動: ${escapeHtml(playerSideText", html)
        self.assertIn("function battleLabel(roundNumber)", html)
        self.assertIn("現在:", html)
        self.assertNotIn("現在バトル", html)
        self.assertNotIn("最大5バトルで終了します。", html)
        self.assertNotIn("候補: ${deckDisplayNameById(opponentLikelyDeckId)}", html)
        self.assertIn("ラウンド条件", html)
        self.assertNotIn('id="battle-state-badge"', html)
        self.assertNotIn("マッチ状態", html)
        self.assertNotIn("マッチ終了", html)
        self.assertNotIn("未進行", html)
        self.assertNotIn("function resultLabel", html)
        self.assertNotIn("deck-token-class", html)
        self.assertNotIn("${usedDeckIds.length}デッキ", html)
        self.assertNotIn("${remainingDeckIds.length}デッキ", html)
        self.assertNotIn("${active.selfCandidateDeckIds.length}デッキ", html)
        self.assertNotIn("${active.opponentCandidateDeckIds.length}デッキ", html)
        self.assertNotIn('items.length ? `${items.length}件` : "なし"', html)
        self.assertNotIn("各担当選手の使用可能度を見ながら選択します。", html)
        self.assertNotIn("提出条件と使用可能度リスクを分けて表示します。", html)

    def test_rendered_ui_loads_google_sheets_matchups_with_reload_and_fallback(self) -> None:
        html = render_ps_simulator_html()

        self.assertIn('const matchupApiUrl = "/api/ps-simulator/matchups";', html)
        self.assertIn('id="reload-matchups" type="button">相性表を再読み込み</button>', html)
        self.assertIn('id="matchup-load-status"', html)
        self.assertIn("async function fetchMatchupApiPayload()", html)
        self.assertIn("fetch(matchupApiUrl", html)
        self.assertIn("function buildMatchupIndexFromApiPayload(dataset, payload)", html)
        self.assertIn('sourceMeta.type === "google_sheets"', html)
        self.assertIn('if (source === "google_sheets") return "Google Sheets";', html)
        self.assertIn("function provisionalDeckCandidatesFromPayload(payload)", html)
        self.assertIn("function mergeProvisionalDecksFromMatchupPayload(payload)", html)
        self.assertIn("function deckClassGroupDefinitions()", html)
        self.assertIn('deckKind: "provisional"', html)
        self.assertIn("仮デッキ", html)
        self.assertIn("クラス不明", html)
        self.assertIn("warnings ${status.warningCount}件", html)
        self.assertIn("sourceMeta.spreadsheetIdSource", html)
        self.assertIn("Google Sheets相性表の取得に失敗したため、repo-local fixtureを使用しています。", html)
        self.assertIn("既存の相性表を維持しています。", html)
        self.assertIn("safeMatchupFetchError(error)", html)
        self.assertIn("matchupStatus: battleLogMatchupStatus()", html)
        self.assertIn("matchupLoadFallback", html)
        self.assertIn('fetchedAt: winRateSource.fetchedAt || ""', html)
        self.assertIn("matchupSourceWarnings", html)
        self.assertIn("function refreshActiveRoundWinRate()", html)
        self.assertIn("apiFallback: Boolean(index.apiFallback)", html)
        self.assertIn("以降に updateRoundWinRate() で勝率を確定するバトルから新しい相性表を使う", html)

    def test_sample_dataset_keeps_missing_status_player_supported_by_ui(self) -> None:
        dataset = read_ps_simulator_sample_dataset()
        player_ids = {player["playerId"] for player in dataset["players"]}
        status_player_ids = {status["playerId"] for status in dataset["playerDeckStatuses"]}

        self.assertIn("player-spicies", player_ids)
        self.assertNotIn("player-spicies", status_player_ids)

    def test_write_assets_copies_sample_dataset_for_static_fetch(self) -> None:
        source_dataset = read_ps_simulator_sample_dataset()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)

            write_ps_simulator_assets(out_dir)

            self.assertTrue((out_dir / "ps-simulator.html").exists())
            self.assertTrue((out_dir / HTML2CANVAS_PUBLIC_PATH).exists())
            self.assertTrue((out_dir / HTML2CANVAS_PUBLIC_LICENSE_PATH).exists())
            self.assertIn("html2canvas 1.4.1", (out_dir / HTML2CANVAS_PUBLIC_PATH).read_text(encoding="utf-8"))
            self.assertIn("MIT License", (out_dir / HTML2CANVAS_PUBLIC_PATH).read_text(encoding="utf-8"))
            self.assertIn("Permission is hereby granted", (out_dir / HTML2CANVAS_PUBLIC_LICENSE_PATH).read_text(encoding="utf-8"))
            public_dataset_path = out_dir / PS_SIMULATOR_PUBLIC_DATASET_PATH
            self.assertTrue(public_dataset_path.exists())
            copied_dataset = json.loads(public_dataset_path.read_text(encoding="utf-8"))
            self.assertEqual(copied_dataset, source_dataset)
            public_profiles_path = out_dir / PLAYER_PROFILES_PUBLIC_PATH
            self.assertTrue(public_profiles_path.exists())
            player_profiles = json.loads(public_profiles_path.read_text(encoding="utf-8"))
            self.assertEqual(player_profiles["schemaVersion"], "player-profiles.v1")
            self.assertIn("player-maito", {player["playerId"] for player in player_profiles["players"]})

    def test_battle_candidate_generation_supports_r4_r5_minimum_flow(self) -> None:
        submission = read_ps_simulator_sample_dataset()["sampleSubmission"]

        r1_candidates = battle_candidate_deck_ids_for_round(submission, 1, set())
        r2_candidates = battle_candidate_deck_ids_for_round(submission, 2, set())
        r3_candidates = battle_candidate_deck_ids_for_round(submission, 3, set())

        self.assertEqual(len(r1_candidates), EXPECTED_ROUND_CANDIDATE_COUNTS[1])
        self.assertEqual(len(r2_candidates), EXPECTED_ROUND_CANDIDATE_COUNTS[2])
        self.assertEqual(len(r3_candidates), EXPECTED_ROUND_CANDIDATE_COUNTS[3])

        used_after_r3 = {r1_candidates[0], r2_candidates[0], r3_candidates[0]}
        r4_candidates = battle_candidate_deck_ids_for_round(submission, 4, used_after_r3)
        self.assertEqual(len(r4_candidates), EXPECTED_ROUND_CANDIDATE_COUNTS[4])
        self.assertTrue(used_after_r3.isdisjoint(r4_candidates))

        used_after_r4 = used_after_r3 | {r4_candidates[0]}
        r5_candidates = battle_candidate_deck_ids_for_round(submission, 5, used_after_r4)
        self.assertEqual(len(r5_candidates), EXPECTED_ROUND_CANDIDATE_COUNTS[5])
        self.assertTrue(used_after_r4.isdisjoint(r5_candidates))

    def test_used_deck_management_is_independent_by_side(self) -> None:
        submission = read_ps_simulator_sample_dataset()["sampleSubmission"]
        r1_candidates = battle_candidate_deck_ids_for_round(submission, 1, set())
        r2_candidates = battle_candidate_deck_ids_for_round(submission, 2, set())
        r3_candidates = battle_candidate_deck_ids_for_round(submission, 3, set())
        rounds = [
            {
                "roundNumber": 1,
                "selfSelectedDeckId": r1_candidates[0],
                "opponentSelectedDeckId": r1_candidates[1],
                "result": "self_win",
            },
            {
                "roundNumber": 2,
                "selfSelectedDeckId": r2_candidates[0],
                "opponentSelectedDeckId": r2_candidates[1],
                "result": "opponent_win",
            },
            {
                "roundNumber": 3,
                "selfSelectedDeckId": r3_candidates[0],
                "opponentSelectedDeckId": r3_candidates[1],
                "result": "self_win",
            },
        ]

        self_used = battle_used_deck_ids_for_side(rounds, "self")
        opponent_used = battle_used_deck_ids_for_side(rounds, "opponent")
        self.assertEqual(self_used, [r1_candidates[0], r2_candidates[0], r3_candidates[0]])
        self.assertEqual(opponent_used, [r1_candidates[1], r2_candidates[1], r3_candidates[1]])

        self_r4_candidates = battle_candidate_deck_ids_for_round(submission, 4, set(self_used))
        opponent_r4_candidates = battle_candidate_deck_ids_for_round(submission, 4, set(opponent_used))

        self.assertNotIn(r1_candidates[0], self_r4_candidates)
        self.assertIn(r1_candidates[1], self_r4_candidates)
        self.assertNotIn(r1_candidates[1], opponent_r4_candidates)
        self.assertIn(r1_candidates[0], opponent_r4_candidates)

    def test_remaining_decks_and_reset_from_round_follow_used_constraints(self) -> None:
        submission = read_ps_simulator_sample_dataset()["sampleSubmission"]
        r1_candidates = battle_candidate_deck_ids_for_round(submission, 1, set())
        r2_candidates = battle_candidate_deck_ids_for_round(submission, 2, set())
        rounds = [
            {"roundNumber": 1, "selfSelectedDeckId": r1_candidates[0], "opponentSelectedDeckId": r1_candidates[1]},
            {"roundNumber": 2, "selfSelectedDeckId": r2_candidates[0], "opponentSelectedDeckId": r2_candidates[1]},
        ]

        self.assertEqual(
            battle_used_deck_ids_for_side(rounds, "self", through_round_number=1),
            [r1_candidates[0]],
        )
        remaining_after_r2 = battle_remaining_deck_ids_for_side(
            submission,
            battle_used_deck_ids_for_side(rounds, "self"),
        )
        self.assertEqual(len(remaining_after_r2), 5)
        self.assertNotIn(r1_candidates[0], remaining_after_r2)
        self.assertNotIn(r2_candidates[0], remaining_after_r2)

        self.assertEqual(reset_battle_rounds_from(rounds, 2), [rounds[0]])
        self.assertEqual(reset_battle_rounds_from(rounds, 1), [])

    def test_invalid_submission_candidate_generation_does_not_crash(self) -> None:
        invalid_submission = {
            "assignments": [
                {"role": "A", "deckIds": ["missing-deck", "missing-deck", ""]},
                {"role": "B", "deckIds": []},
            ]
        }

        self.assertEqual(
            battle_candidate_deck_ids_for_round(invalid_submission, 1, set()),
            ["missing-deck"],
        )
        self.assertEqual(battle_candidate_deck_ids_for_round(invalid_submission, 2, set()), [])
        self.assertEqual(
            battle_candidate_deck_ids_for_round(invalid_submission, 4, set()),
            ["missing-deck"],
        )
        self.assertEqual(
            validate_round_candidate_count(1, ["missing-deck"]),
            ["R1候補は3デッキ想定です。現在は1デッキです。"],
        )


if __name__ == "__main__":
    unittest.main()
