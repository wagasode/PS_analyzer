from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FUNCTION_PATH = ROOT_DIR / "functions" / "api" / "ps-simulator" / "matchups.js"
SAMPLE_DATASET_PATH = ROOT_DIR / "data" / "ps_simulator" / "sample_dataset.json"
NODE = shutil.which("node")


def run_matchup_module(script: str) -> dict:
    if NODE is None:
        raise unittest.SkipTest("node is required to exercise the Pages Function helpers")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        module_path = tmp_path / "matchups.mjs"
        runner_path = tmp_path / "runner.mjs"
        module_path.write_text(FUNCTION_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        runner_path.write_text(
            textwrap.dedent(
                f"""
                const mod = await import({json.dumps(module_path.as_uri())});
                const result = await (async () => {{
                {textwrap.indent(script, "  ")}
                }})();
                console.log(JSON.stringify(result));
                """
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [NODE, str(runner_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    return json.loads(result.stdout)


class PsMatchupApiFunctionTest(unittest.TestCase):
    def test_function_file_exists(self) -> None:
        self.assertTrue(FUNCTION_PATH.exists())

    def test_default_decks_match_sample_dataset_definitions(self) -> None:
        dataset = json.loads(SAMPLE_DATASET_PATH.read_text(encoding="utf-8"))
        expected = {
            deck["deckId"]: {
                "deckName": deck["deckName"],
                "sourceDeckKey": deck.get("sourceDeckKey"),
            }
            for deck in dataset["decks"]
        }
        actual = run_matchup_module("return mod.__test.DEFAULT_DECKS;")
        actual_by_id = {
            deck["deckId"]: {
                "deckName": deck["deckName"],
                "sourceDeckKey": deck.get("sourceDeckKey"),
            }
            for deck in actual
        }

        self.assertEqual(actual_by_id, expected)

    def test_env_missing_response_is_safe_and_no_store(self) -> None:
        result = run_matchup_module(
            """
            const response = await mod.__test.handleRequest({}, {
              fetchImpl: async () => {
                throw new Error("fetch should not be called");
              },
              now: () => new Date("2026-05-29T00:00:00Z")
            });
            return {
              status: response.status,
              cacheControl: response.headers.get("Cache-Control"),
              contentType: response.headers.get("Content-Type"),
              body: await response.json()
            };
            """
        )

        self.assertEqual(result["status"], 500)
        self.assertEqual(result["cacheControl"], "no-store")
        self.assertIn("application/json", result["contentType"])
        self.assertEqual(result["body"]["error"]["code"], "google_sheets_env_missing")
        self.assertNotIn("PS_MATCHUP_SPREADSHEET_ID", json.dumps(result["body"], ensure_ascii=False))
        self.assertNotIn("GOOGLE_PRIVATE_KEY", json.dumps(result["body"], ensure_ascii=False))

    def test_win_rate_normalization(self) -> None:
        result = run_matchup_module(
            """
            return {
              decimal: mod.__test.normalizeWinRate("0.55"),
              percent: mod.__test.normalizeWinRate("55%"),
              wholeNumber: mod.__test.normalizeWinRate("55"),
              empty: mod.__test.normalizeWinRate(""),
              invalid: mod.__test.normalizeWinRate("bad"),
              outOfRange: mod.__test.normalizeWinRate("101")
            };
            """
        )

        self.assertEqual(result["decimal"]["value"], 0.55)
        self.assertEqual(result["percent"]["value"], 0.55)
        self.assertEqual(result["wholeNumber"]["value"], 0.55)
        self.assertTrue(result["empty"]["missing"])
        self.assertIn("数値として読めません", result["invalid"]["warning"])
        self.assertIn("範囲外", result["outOfRange"]["warning"])

    def test_matrix_parse_normalizes_and_warns_without_reverse_completion(self) -> None:
        result = run_matchup_module(
            """
            const values = [
              ["担当者", "使用デッキ", "進化E", "連携R", "ランプD", "未知列", ""],
              ["memo", "memo", "", "", "", "", ""],
              ["alice", "進化E", "0.5", "55%", "", "0.4", "0.3"],
              ["bob", "連携R", "62%", "0.5", "", "", ""],
              ["carol", "ランプD", "", "", "0.7", "", ""],
              ["dave", "未知デッキ", "0.5", "", "", "", ""],
              ["erin", "", "0.4", "", "", "", ""],
              ["frank", "進化E", "50", "", "", "", ""]
            ];
            return mod.__test.parseMatchupMatrix(values, {
              range: "'相性表'!A1:Z100",
              fetchedAt: "2026-05-29T00:00:00.000Z"
            });
            """
        )

        self.assertEqual(result["source"]["type"], "google_sheets")
        self.assertEqual(result["source"]["spreadsheetIdSource"], "env")
        self.assertEqual(result["source"]["range"], "'相性表'!A1:Z100")
        self.assertNotIn("spreadsheetId", result["source"])

        matchups = {
            (entry["sourceDeckId"], entry["targetDeckId"]): entry
            for entry in result["matchups"]
        }
        provisional_by_name = {
            deck["deckName"]: deck
            for deck in result["provisionalDecks"]
        }
        self.assertEqual(set(provisional_by_name), {"未知列", "未知デッキ"})
        self.assertEqual(result["deckCandidates"], result["provisionalDecks"])
        self.assertEqual(result["unresolvedDecks"], result["provisionalDecks"])

        unknown_column_deck = provisional_by_name["未知列"]
        unknown_row_deck = provisional_by_name["未知デッキ"]
        self.assertTrue(unknown_column_deck["provisional"])
        self.assertTrue(unknown_row_deck["temporary"])
        self.assertEqual(unknown_column_deck["source"], "matchup_matrix")
        self.assertEqual(unknown_column_deck["sourceType"], "google_sheets_matchup")
        self.assertEqual(unknown_column_deck["className"], "")
        self.assertEqual(unknown_column_deck["sourceCells"], ["'相性表'!F1"])
        self.assertEqual(unknown_row_deck["sourceCells"], ["'相性表'!B6"])
        self.assertTrue(unknown_column_deck["deckId"].startswith("sheet-deck-"))
        self.assertTrue(unknown_row_deck["deckId"].startswith("sheet-deck-"))
        self.assertIn("classNameを推定できない", "\n".join(unknown_column_deck["warnings"]))

        self.assertEqual(
            matchups[("deck-e-1779172826463", "deck-r-1778681117704")]["winRate"],
            0.55,
        )
        self.assertEqual(
            matchups[("deck-e-1779172826463", "deck-r-1778681117704")]["sourceCell"],
            "'相性表'!D3",
        )
        self.assertEqual(
            matchups[("deck-r-1778681117704", "deck-e-1779172826463")]["winRate"],
            0.62,
        )
        self.assertEqual(matchups[("ps-d-ramp", "ps-d-ramp")]["winRate"], 0.7)
        self.assertEqual(
            matchups[("deck-e-1779172826463", unknown_column_deck["deckId"])]["winRate"],
            0.4,
        )
        self.assertEqual(
            matchups[(unknown_row_deck["deckId"], "deck-e-1779172826463")]["winRate"],
            0.5,
        )
        self.assertNotIn(("deck-r-1778681117704", "ps-d-ramp"), matchups)

        warnings = "\n".join(result["warnings"])
        self.assertIn("仮デッキ候補 未知列", warnings)
        self.assertIn("仮デッキ候補 未知デッキ", warnings)
        self.assertNotIn("列デッキをdeckIdへ解決できません", warnings)
        self.assertNotIn("行デッキをdeckIdへ解決できません", warnings)
        self.assertIn("列デッキ名が空", warnings)
        self.assertIn("自己対面は0.5が原則", warnings)
        self.assertIn("行デッキ名が空", warnings)
        self.assertIn("重複matchup", warnings)

    def test_function_does_not_log_secrets(self) -> None:
        source = FUNCTION_PATH.read_text(encoding="utf-8")

        self.assertNotIn("console.log", source)
        self.assertNotIn("console.error", source)
        self.assertNotIn("console.warn", source)


if __name__ == "__main__":
    unittest.main()
