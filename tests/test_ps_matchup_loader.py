from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from ps_matchup_loader import build_matchup_index, get_win_rate  # noqa: E402


SAMPLE_DATASET_PATH = ROOT_DIR / "data" / "ps_simulator" / "sample_dataset.json"


def load_sample_dataset() -> dict:
    with SAMPLE_DATASET_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class PsMatchupLoaderTest(unittest.TestCase):
    def test_sample_fixture_builds_row_deck_matchup_index(self) -> None:
        dataset = load_sample_dataset()
        index = build_matchup_index(dataset)

        self.assertEqual(index.source, "repo-local fixture")
        self.assertEqual(len(index.entries), 15)
        self.assertEqual(index.warnings, [])

        result = get_win_rate(index, "deck-e-1779172826463", "deck-r-1778681117704")
        self.assertEqual(result["winRate"], 0.4)
        self.assertEqual(result["winRateSource"]["type"], "matchup")
        self.assertEqual(result["winRateSource"]["perspective"], "rowDeck")
        self.assertEqual(result["winRateSource"]["sourceCell"], "matchup_matrix!D3")
        self.assertEqual(result["warnings"], [])

    def test_reverse_direction_is_not_completed_from_inverse_cell(self) -> None:
        dataset = load_sample_dataset()
        index = build_matchup_index(dataset)

        direct_reverse_row = get_win_rate(index, "deck-r-1778681117704", "deck-e-1779172826463")
        self.assertEqual(direct_reverse_row["winRate"], 0.62)
        self.assertEqual(direct_reverse_row["winRateSource"]["type"], "matchup")

        fallback = get_win_rate(index, "deck-b-1778743160748", "ps-w-earth-rite")
        self.assertEqual(fallback["winRate"], 0.5)
        self.assertEqual(fallback["winRateSource"]["type"], "fallback")
        self.assertEqual(fallback["winRateNote"], "相性表未定義のため0.5")
        self.assertEqual(fallback["warnings"], ["matchup not found: deck-b-1778743160748 vs ps-w-earth-rite"])

    def test_validation_warnings_cover_duplicate_unknown_invalid_and_self_matchup(self) -> None:
        dataset = {
            "decks": [
                {"deckId": "deck-a", "deckName": "A"},
                {"deckId": "deck-b", "deckName": "B"},
            ],
            "matchupFixture": {
                "source": "test fixture",
                "perspective": "rowDeck",
                "matchups": [
                    {"sourceDeckName": "A", "targetDeckName": "B", "winRate": "55%", "sourceCell": "D3"},
                    {"sourceDeckId": "deck-a", "targetDeckId": "deck-b", "winRate": "0.6", "sourceCell": "D4"},
                    {"sourceDeckName": "A", "targetDeckName": "missing", "winRate": "0.4", "sourceCell": "D5"},
                    {"sourceDeckName": "B", "targetDeckName": "A", "winRate": "bad", "sourceCell": "D6"},
                    {"sourceDeckName": "B", "targetDeckName": "B", "winRate": "0.7", "sourceCell": "D7"},
                ],
            },
        }

        index = build_matchup_index(dataset)

        self.assertEqual(index.entries[("deck-a", "deck-b")].win_rate, 0.55)
        self.assertEqual(index.entries[("deck-b", "deck-b")].win_rate, 0.7)
        self.assertTrue(any("重複matchup" in warning for warning in index.warnings))
        self.assertTrue(any("列デッキをdeckIdへ解決" in warning for warning in index.warnings))
        self.assertTrue(any("winRateを数値として読めません" in warning for warning in index.warnings))
        self.assertTrue(any("自己対面は0.5が原則" in warning for warning in index.warnings))


if __name__ == "__main__":
    unittest.main()
