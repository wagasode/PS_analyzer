from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from common import twitch_archive_url, youtube_archive_url  # noqa: E402


class ArchiveUrlTest(unittest.TestCase):
    def test_youtube_video_id_becomes_watch_url(self) -> None:
        self.assertEqual(
            youtube_archive_url("eqOEUv01ceU"),
            "https://www.youtube.com/watch?v=eqOEUv01ceU",
        )

    def test_youtube_live_url_becomes_watch_url(self) -> None:
        self.assertEqual(
            youtube_archive_url("https://www.youtube.com/live/eqOEUv01ceU?si=abc"),
            "https://www.youtube.com/watch?v=eqOEUv01ceU",
        )

    def test_youtube_short_url_becomes_watch_url(self) -> None:
        self.assertEqual(
            youtube_archive_url("https://youtu.be/eqOEUv01ceU?t=30"),
            "https://www.youtube.com/watch?v=eqOEUv01ceU",
        )

    def test_twitch_video_id_becomes_vod_url(self) -> None:
        self.assertEqual(
            twitch_archive_url("1234567890"),
            "https://www.twitch.tv/videos/1234567890",
        )

    def test_twitch_vod_url_is_canonicalized(self) -> None:
        self.assertEqual(
            twitch_archive_url("1234567890", "https://www.twitch.tv/videos/1234567890?filter=archives&sort=time"),
            "https://www.twitch.tv/videos/1234567890",
        )


if __name__ == "__main__":
    unittest.main()
