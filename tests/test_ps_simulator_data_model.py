from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DATASET_PATH = ROOT_DIR / "data" / "ps_simulator" / "sample_dataset.json"

EXPECTED_CLASSES = {"E", "R", "W", "D", "Ni", "B", "Nm"}
EXPECTED_SUBMISSION_COUNTS = {"A": 3, "B": 2, "C": 2}
ALLOWED_STATUSES = {"confident", "available", "trainable", "hard"}
ALLOWED_SIDES = {"self", "opponent"}
ALLOWED_RESULTS = {"self_win", "opponent_win"}
ALLOWED_WIN_RATE_SOURCE_TYPES = {"matchup", "reverseMatchup", "fallback", "manual", "unknown"}
ALLOWED_RESULT_DECISION_METHODS = {"random", "manual"}


def load_sample_dataset() -> dict:
    with SAMPLE_DATASET_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class PsSimulatorDataModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = load_sample_dataset()
        self.decks = self.dataset["decks"]
        self.players = self.dataset["players"]
        self.deck_ids = {deck["deckId"] for deck in self.decks}
        self.player_ids = {player["playerId"] for player in self.players}

    def test_sample_dataset_uses_expected_schema_version(self) -> None:
        self.assertEqual(self.dataset["schemaVersion"], "ps-simulator.v1")

    def test_class_definitions_are_the_issue32_seven_classes(self) -> None:
        class_names = {definition["className"] for definition in self.dataset["classDefinitions"]}

        self.assertEqual(class_names, EXPECTED_CLASSES)

    def test_decks_use_unique_stable_ids_and_cover_seven_classes(self) -> None:
        self.assertEqual(len(self.deck_ids), len(self.decks))
        self.assertNotIn("", self.deck_ids)
        self.assertEqual({deck["className"] for deck in self.decks}, EXPECTED_CLASSES)

        for deck in self.decks:
            self.assertTrue(deck["deckId"].startswith(("deck-", "ps-")))
            self.assertNotEqual(deck["deckId"], deck["deckName"])
            self.assertIn(deck["className"], EXPECTED_CLASSES)
            self.assertIsInstance(deck["deckName"], str)
            self.assertIsInstance(deck["weaknessTags"], list)
            self.assertIsInstance(deck["note"], str)
            if deck.get("source") == "repo_csv":
                self.assertEqual(deck["sourceDeckKey"], deck["deckId"])

    def test_players_use_unique_stable_ids(self) -> None:
        self.assertEqual(len(self.player_ids), len(self.players))
        self.assertNotIn("", self.player_ids)

        for player in self.players:
            self.assertIsInstance(player["playerName"], str)
            self.assertTrue(player["playerName"])

    def test_player_deck_statuses_reference_known_players_and_decks(self) -> None:
        statuses = self.dataset["playerDeckStatuses"]
        pairs = {(status["playerId"], status["deckId"]) for status in statuses}

        self.assertEqual(len(pairs), len(statuses))
        self.assertIn("hard", {status["status"] for status in statuses})
        self.assertIn("trainable", {status["status"] for status in statuses})

        for status in statuses:
            self.assertIn(status["playerId"], self.player_ids)
            self.assertIn(status["deckId"], self.deck_ids)
            self.assertIn(status["status"], ALLOWED_STATUSES)
            self.assertIsInstance(status["practiceCost"], int)
            self.assertGreaterEqual(status["practiceCost"], 0)
            self.assertIsInstance(status["note"], str)

    def test_sample_submission_is_valid_3_2_2_with_seven_unique_classes(self) -> None:
        submission = self.dataset["sampleSubmission"]
        deck_by_id = {deck["deckId"]: deck for deck in self.decks}

        self.assertIn(submission["side"], ALLOWED_SIDES)
        self.assertEqual({assignment["role"] for assignment in submission["assignments"]}, {"A", "B", "C"})

        selected_deck_ids: list[str] = []
        for assignment in submission["assignments"]:
            role = assignment["role"]
            self.assertIn(assignment["playerId"], self.player_ids)
            self.assertEqual(len(assignment["deckIds"]), EXPECTED_SUBMISSION_COUNTS[role])
            selected_deck_ids.extend(assignment["deckIds"])

        self.assertEqual(len(selected_deck_ids), 7)
        self.assertEqual(len(set(selected_deck_ids)), 7)
        self.assertTrue(set(selected_deck_ids).issubset(self.deck_ids))
        self.assertEqual({deck_by_id[deck_id]["className"] for deck_id in selected_deck_ids}, EXPECTED_CLASSES)

    def test_matchups_reference_known_decks_and_normalized_win_rates(self) -> None:
        for matchup in self.dataset["sampleMatchups"]:
            self.assertIn(matchup["deckIdA"], self.deck_ids)
            self.assertIn(matchup["deckIdB"], self.deck_ids)
            self.assertNotEqual(matchup["deckIdA"], matchup["deckIdB"])
            self.assertGreaterEqual(matchup["winRateForA"], 0.0)
            self.assertLessEqual(matchup["winRateForA"], 1.0)

    def test_battle_log_rounds_are_replayable_and_reference_known_decks(self) -> None:
        battle_log = self.dataset["sampleBattleLog"]
        used_self: set[str] = set()
        used_opponent: set[str] = set()
        running_score = {"self": 0, "opponent": 0}
        seen_win_rate_source_types: set[str] = set()
        seen_result_decision_methods: set[str] = set()
        submitted_deck_ids = {
            deck_id
            for assignment in self.dataset["sampleSubmission"]["assignments"]
            for deck_id in assignment["deckIds"]
        }
        expected_candidate_counts = {1: 3, 2: 2, 3: 2, 4: 4, 5: 3}

        self.assertEqual(battle_log["logVersion"], "ps-battle-log.v1")
        self.assertRegex(battle_log["createdAt"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(battle_log["seed"], "sample-seed-001")
        self.assertEqual(battle_log["selfSubmissionId"], self.dataset["sampleSubmission"]["submissionId"])
        self.assertEqual(battle_log["opponentSubmissionId"], "sample-opponent-submission")
        self.assertEqual(battle_log["selfSubmissionSnapshot"]["side"], "self")
        self.assertEqual(battle_log["opponentSubmissionSnapshot"]["side"], "opponent")
        self.assertEqual([round_log["roundNumber"] for round_log in battle_log["rounds"]], [1, 2, 3, 4, 5])

        for snapshot_key in ["selfSubmissionSnapshot", "opponentSubmissionSnapshot"]:
            snapshot = battle_log[snapshot_key]
            self.assertEqual({assignment["role"] for assignment in snapshot["assignments"]}, {"A", "B", "C"})
            for assignment in snapshot["assignments"]:
                self.assertIn(assignment["playerId"], self.player_ids)
                self.assertEqual(assignment["playerSnapshot"]["playerId"], assignment["playerId"])
                self.assertTrue(assignment["playerSnapshot"]["playerName"])
                self.assertEqual(len(assignment["deckIds"]), len(assignment["deckSnapshots"]))
                for deck_snapshot in assignment["deckSnapshots"]:
                    self.assertIn(deck_snapshot["deckId"], self.deck_ids)
                    self.assertIn(deck_snapshot["className"], EXPECTED_CLASSES)
                    self.assertTrue(deck_snapshot["deckName"])

        for round_log in battle_log["rounds"]:
            round_number = round_log["roundNumber"]
            self.assertTrue(set(round_log["selfCandidateDeckIds"]).issubset(self.deck_ids))
            self.assertTrue(set(round_log["opponentCandidateDeckIds"]).issubset(self.deck_ids))
            self.assertEqual(round_log["candidateDeckIds"]["self"], round_log["selfCandidateDeckIds"])
            self.assertEqual(round_log["candidateDeckIds"]["opponent"], round_log["opponentCandidateDeckIds"])
            self.assertEqual(len(round_log["selfCandidateDeckIds"]), expected_candidate_counts[round_number])
            self.assertEqual(len(round_log["opponentCandidateDeckIds"]), expected_candidate_counts[round_number])
            self.assertTrue(used_self.isdisjoint(round_log["selfCandidateDeckIds"]))
            self.assertTrue(used_opponent.isdisjoint(round_log["opponentCandidateDeckIds"]))
            self.assertIn(round_log["selfSelectedDeckId"], round_log["selfCandidateDeckIds"])
            self.assertIn(round_log["opponentSelectedDeckId"], round_log["opponentCandidateDeckIds"])
            self.assertEqual(round_log["selectedDeckIds"]["self"], round_log["selfSelectedDeckId"])
            self.assertEqual(round_log["selectedDeckIds"]["opponent"], round_log["opponentSelectedDeckId"])
            self.assertGreaterEqual(round_log["selfWinRate"], 0.0)
            self.assertLessEqual(round_log["selfWinRate"], 1.0)
            self.assertAlmostEqual(round_log["winRate"]["self"], round_log["selfWinRate"])
            self.assertAlmostEqual(round_log["winRate"]["self"] + round_log["winRate"]["opponent"], 1.0)
            self.assertIn(round_log["winRateSource"]["type"], ALLOWED_WIN_RATE_SOURCE_TYPES)
            seen_win_rate_source_types.add(round_log["winRateSource"]["type"])
            if round_log["winRateSource"]["type"] in {"matchup", "reverseMatchup"}:
                self.assertIn(round_log["winRateSource"]["deckIdA"], self.deck_ids)
                self.assertIn(round_log["winRateSource"]["deckIdB"], self.deck_ids)
            self.assertIn(round_log["result"], ALLOWED_RESULTS)
            self.assertIn(round_log["resultDecisionMethod"], ALLOWED_RESULT_DECISION_METHODS)
            seen_result_decision_methods.add(round_log["resultDecisionMethod"])
            self.assertEqual(round_log["resultDecision"]["method"], round_log["resultDecisionMethod"])
            if round_log["resultDecisionMethod"] == "random":
                self.assertIsInstance(round_log["resultDecision"]["randomValue"], float)
                self.assertIn(battle_log["seed"], round_log["resultDecision"]["seedInput"])
            else:
                self.assertIsNone(round_log["resultDecision"]["randomValue"])

            used_self.add(round_log["selfSelectedDeckId"])
            used_opponent.add(round_log["opponentSelectedDeckId"])
            if round_log["result"] == "self_win":
                running_score["self"] += 1
            if round_log["result"] == "opponent_win":
                running_score["opponent"] += 1
            self.assertEqual(set(round_log["usedDeckIdsAfterRound"]["self"]), used_self)
            self.assertEqual(set(round_log["usedDeckIdsAfterRound"]["opponent"]), used_opponent)
            self.assertEqual(round_log["usedDeckIdsAfterRound"]["self"], round_log["selfUsedDeckIds"])
            self.assertEqual(round_log["usedDeckIdsAfterRound"]["opponent"], round_log["opponentUsedDeckIds"])
            self.assertEqual(set(round_log["selfUsedDeckIds"]), used_self)
            self.assertEqual(set(round_log["opponentUsedDeckIds"]), used_opponent)
            self.assertEqual(set(round_log["remainingDeckIdsAfterRound"]["self"]), submitted_deck_ids - used_self)
            self.assertEqual(set(round_log["remainingDeckIdsAfterRound"]["opponent"]), submitted_deck_ids - used_opponent)
            self.assertEqual(round_log["remainingDeckIdsAfterRound"]["self"], round_log["selfRemainingDeckIds"])
            self.assertEqual(round_log["remainingDeckIdsAfterRound"]["opponent"], round_log["opponentRemainingDeckIds"])
            self.assertEqual(set(round_log["selfRemainingDeckIds"]), submitted_deck_ids - used_self)
            self.assertEqual(set(round_log["opponentRemainingDeckIds"]), submitted_deck_ids - used_opponent)
            self.assertEqual(round_log["scoreAfterRound"], running_score)
            self.assertEqual(round_log["score"], running_score)

        final_result = battle_log["finalResult"]
        self.assertEqual(final_result["winner"], "self")
        self.assertEqual(final_result["result"], "self_win")
        self.assertEqual(final_result["selfWins"], 3)
        self.assertEqual(final_result["opponentWins"], 2)
        self.assertEqual(final_result["score"], {"self": 3, "opponent": 2})
        self.assertEqual(final_result["finishedAtRound"], 5)
        self.assertEqual(battle_log["finishedAtRound"], 5)
        self.assertIn("matchup", seen_win_rate_source_types)
        self.assertIn("reverseMatchup", seen_win_rate_source_types)
        self.assertEqual(seen_result_decision_methods, {"random", "manual"})


if __name__ == "__main__":
    unittest.main()
