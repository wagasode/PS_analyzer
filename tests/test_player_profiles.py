from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from player_profiles import (  # noqa: E402
    PLAYER_PROFILES_SCHEMA_VERSION,
    PLAYER_PROFILE_SOURCE,
    build_player_profiles,
)


class PlayerProfilesTest(unittest.TestCase):
    def test_profiles_are_generated_from_streaming_player_master(self) -> None:
        payload = build_player_profiles(generated_at="2026-05-31T00:00:00Z", icon_urls={})
        players = payload["players"]
        by_id = {player["playerId"]: player for player in players}

        self.assertEqual(payload["schemaVersion"], PLAYER_PROFILES_SCHEMA_VERSION)
        self.assertEqual(payload["source"], PLAYER_PROFILE_SOURCE)
        self.assertGreater(len(players), 4)
        self.assertIn("player-maito", by_id)
        self.assertIn("player-glory", by_id)
        self.assertIn("player-toby", by_id)
        self.assertIn("player-spicies", by_id)

        maito = by_id["player-maito"]
        self.assertEqual(maito["displayName"], "マイト")
        self.assertEqual(maito["playerName"], "マイト")
        self.assertEqual(maito["teamName"], "MURASH GAMING")
        self.assertEqual(maito["team"], "MURASH GAMING")
        self.assertIn("iconUrl", maito)
        self.assertIn("playerIconUrl", maito)
        self.assertIn("マイト", maito["aliases"])
        self.assertIn("maito", maito["aliases"])
        self.assertEqual(maito["source"], PLAYER_PROFILE_SOURCE)

    def test_icon_urls_can_be_overlaid_by_player_key(self) -> None:
        payload = build_player_profiles(
            generated_at="2026-05-31T00:00:00Z",
            icon_urls={("MURASH GAMING", "Toby"): "https://example.com/toby.png"},
        )
        by_id = {player["playerId"]: player for player in payload["players"]}

        self.assertEqual(by_id["player-toby"]["iconUrl"], "https://example.com/toby.png")
        self.assertEqual(by_id["player-toby"]["playerIconUrl"], "https://example.com/toby.png")


if __name__ == "__main__":
    unittest.main()
