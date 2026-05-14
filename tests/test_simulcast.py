from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from build_streaming_dashboard import merge_simulcast_streams  # noqa: E402
from build_streaming_report import build_player_stream_metrics  # noqa: E402
from common import dedupe_simulcast_groups, streams_are_simulcast  # noqa: E402


def stream(
    platform: str,
    external_stream_id: str,
    *,
    player_id: int = 1,
    player_name: str = "Toby",
    title: str = "Shadowverse practice",
    occurred_at: str = "2026-05-13T10:00:00Z",
    duration_sec: int = 7200,
    deck_key: str = "",
) -> dict:
    decks = []
    if deck_key:
        decks.append(
            {
                "deck_key": deck_key,
                "deck_name": deck_key,
                "class_name": "",
                "archetype": "",
                "deck_url": "",
                "deck_code": "",
                "notes": "",
                "confidence": "",
                "source_note": "",
                "display_order": 1,
            }
        )
    return {
        "stream_session_id": 1 if platform == "youtube" else 2,
        "player_id": player_id,
        "player_name": player_name,
        "team": "MURASH GAMING",
        "platform": platform,
        "external_stream_id": external_stream_id,
        "title": title,
        "url": f"https://example.com/{external_stream_id}",
        "thumbnail_url": "",
        "started_at": occurred_at,
        "published_at": occurred_at,
        "occurred_at": occurred_at,
        "duration_sec": duration_sec,
        "is_shadowverse_related": 1,
        "decks": decks,
    }


class SimulcastTest(unittest.TestCase):
    def test_same_player_close_youtube_and_twitch_are_simulcast(self) -> None:
        youtube = stream("youtube", "yt-1")
        twitch = stream("twitch", "tw-1", occurred_at="2026-05-13T10:04:00Z")

        self.assertTrue(streams_are_simulcast(youtube, twitch))
        self.assertEqual(len(dedupe_simulcast_groups([youtube, twitch])), 1)

    def test_different_players_are_not_simulcast(self) -> None:
        youtube = stream("youtube", "yt-1", player_id=1, player_name="Toby")
        twitch = stream("twitch", "tw-1", player_id=2, player_name="glory")

        self.assertFalse(streams_are_simulcast(youtube, twitch))
        self.assertEqual(len(dedupe_simulcast_groups([youtube, twitch])), 2)

    def test_far_apart_streams_are_not_simulcast(self) -> None:
        youtube = stream("youtube", "yt-1")
        twitch = stream("twitch", "tw-1", occurred_at="2026-05-13T11:00:00Z")

        self.assertFalse(streams_are_simulcast(youtube, twitch))
        self.assertEqual(len(dedupe_simulcast_groups([youtube, twitch])), 2)

    def test_report_metrics_count_simulcast_once(self) -> None:
        youtube = stream("youtube", "yt-1")
        twitch = stream("twitch", "tw-1", occurred_at="2026-05-13T10:03:00Z", duration_sec=7000)
        solo = stream("youtube", "yt-2", occurred_at="2026-05-14T10:00:00Z", duration_sec=3600)

        metrics = build_player_stream_metrics([youtube, twitch, solo])[1]

        self.assertEqual(metrics["stream_count"], 2)
        self.assertEqual(metrics["total_hours"], 3.0)
        self.assertEqual(metrics["youtube_hours"], 3.0)
        self.assertEqual(metrics["twitch_hours"], 1.94)

    def test_dashboard_group_merges_links_and_decks(self) -> None:
        youtube = stream("youtube", "yt-1", deck_key="deck-a")
        twitch = stream("twitch", "tw-1", occurred_at="2026-05-13T10:02:00Z", deck_key="deck-a")

        merged = merge_simulcast_streams([youtube, twitch])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["platform"], "youtube")
        self.assertEqual(len(merged[0]["simulcast_streams"]), 2)
        self.assertEqual([deck["deck_key"] for deck in merged[0]["decks"]], ["deck-a"])


if __name__ == "__main__":
    unittest.main()
