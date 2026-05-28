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


class PsSimulatorUiTest(unittest.TestCase):
    def test_rendered_ui_fetches_repo_local_sample_dataset_copy(self) -> None:
        html = render_ps_simulator_html()

        self.assertIn('const datasetUrl = "data/ps_simulator/sample_dataset.json";', html)
        self.assertIn("fetch(datasetUrl)", html)
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
        self.assertIn("現在の提出案をセット", html)
        self.assertIn('id="set-self-submission" type="button">自分側</button>', html)
        self.assertIn('id="set-opponent-submission" type="button">相手側</button>', html)
        self.assertIn('id="set-both-submission" type="button">両側</button>', html)
        self.assertNotIn("サンプル提出でラウンドをリセット", html)
        self.assertIn("暫定勝率", html)
        self.assertIn("相性表未接続のため暫定0.5を使用しています。", html)
        self.assertIn("function rollBattleRound()", html)
        self.assertIn("function buildBattleLog()", html)
        self.assertIn("function buildBattleRoundLog(round)", html)
        self.assertIn("function battlePreviewPayload()", html)
        self.assertIn("function downloadBattleLogJson()", html)
        self.assertIn('id="download-battle-log"', html)
        self.assertIn("BattleLog JSONを保存", html)
        self.assertIn('logVersion: "ps-battle-log.v1"', html)
        self.assertIn("createdAt: state.battle.createdAt", html)
        self.assertIn("selfSubmissionSnapshot", html)
        self.assertIn("opponentSubmissionSnapshot", html)
        self.assertIn("winRateSource", html)
        self.assertIn('type: "matchup"', html)
        self.assertIn('type: "reverseMatchup"', html)
        self.assertIn('type: "fallback"', html)
        self.assertIn('type: "unknown"', html)
        self.assertIn("resultDecisionMethod", html)
        self.assertIn('method: "random"', html)
        self.assertIn('decision.method || "manual"', html)
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
        self.assertIn("現在バトル", html)
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
        self.assertNotIn("teamLabel", html)
        self.assertNotIn("各担当選手の使用可能度を見ながら選択します。", html)
        self.assertNotIn("提出条件と使用可能度リスクを分けて表示します。", html)

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
            public_dataset_path = out_dir / PS_SIMULATOR_PUBLIC_DATASET_PATH
            self.assertTrue(public_dataset_path.exists())
            copied_dataset = json.loads(public_dataset_path.read_text(encoding="utf-8"))
            self.assertEqual(copied_dataset, source_dataset)

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
