from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from ps_simulator_ui import (  # noqa: E402
    PS_SIMULATOR_PUBLIC_DATASET_PATH,
    read_ps_simulator_sample_dataset,
    render_ps_simulator_html,
    write_ps_simulator_assets,
    battle_candidate_deck_ids_for_round,
)


class PsSimulatorUiTest(unittest.TestCase):
    def test_rendered_ui_fetches_repo_local_sample_dataset_copy(self) -> None:
        html = render_ps_simulator_html()

        self.assertIn('const datasetUrl = "data/ps_simulator/sample_dataset.json";', html)
        self.assertIn("fetch(datasetUrl)", html)
        self.assertIn("function validateSubmission(submission)", html)
        self.assertIn("function candidateDeckIdsForRound(submission, roundNumber, usedDeckIds)", html)
        self.assertIn("PSルール戦略シミュレータ", html)
        self.assertIn("バトル進行シミュレータ", html)
        self.assertNotIn("バトル進行MVP", html)
        self.assertNotIn("提出案を自分側・相手側にセットして、R1〜R5を手動選出で進めます。", html)
        self.assertIn("現在の提出案を自分側にセット", html)
        self.assertIn("暫定勝率", html)
        self.assertIn("相性表未接続のため暫定0.5を使用しています。", html)
        self.assertIn("function rollBattleRound()", html)
        self.assertIn("function battlePreviewPayload()", html)
        self.assertIn("PlayerDeckStatus 行なし", html)
        self.assertIn("データなし / 要確認", html)
        self.assertIn("deck-class-group", html)
        self.assertIn("role-selection-summary", html)
        self.assertIn("summary-deck-chip", html)
        self.assertIn("deck-status-details", html)
        self.assertIn("function compactClassBadgeHtml(className)", html)
        self.assertIn("function statusSummaryHtml(playerId, deckId)", html)
        self.assertIn("class-coverage-badge", html)
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
        self.assertIn("function avatarHtml(name, imageUrl)", html)
        self.assertIn('class="player-select-row"', html)
        self.assertIn('class="player-avatar"', html)
        self.assertIn("function deckTokenHtml(deckId)", html)
        self.assertIn('class="battle-assignment"', html)
        self.assertIn('class="battle-main-grid"', html)
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

        self.assertEqual(len(r1_candidates), 3)
        self.assertEqual(len(r2_candidates), 2)
        self.assertEqual(len(r3_candidates), 2)

        used_after_r3 = {r1_candidates[0], r2_candidates[0], r3_candidates[0]}
        r4_candidates = battle_candidate_deck_ids_for_round(submission, 4, used_after_r3)
        self.assertEqual(len(r4_candidates), 4)
        self.assertTrue(used_after_r3.isdisjoint(r4_candidates))

        used_after_r4 = used_after_r3 | {r4_candidates[0]}
        r5_candidates = battle_candidate_deck_ids_for_round(submission, 5, used_after_r4)
        self.assertEqual(len(r5_candidates), 3)
        self.assertTrue(used_after_r4.isdisjoint(r5_candidates))


if __name__ == "__main__":
    unittest.main()
