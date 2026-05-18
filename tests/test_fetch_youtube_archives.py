from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import fetch_youtube_archives  # noqa: E402
from common import ApiError, connect, init_schema  # noqa: E402


class FetchYouTubeArchivesTest(unittest.TestCase):
    def create_db(
        self,
        db_path: Path,
        *,
        identifier: str = "@missing",
        external_channel_id: str = "",
        uploads_playlist_id: str = "",
        image_url: str = "",
    ) -> sqlite3.Connection:
        conn = connect(db_path)
        init_schema(conn)
        conn.execute(
            """
            INSERT INTO players(team, player_name, roster_status, x_handle, confidence, source_url, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("DetonatioN FocusMe", "ユーリ", "確定", "yuuri8540", "medium", "https://example.test", ""),
        )
        player_id = conn.execute(
            "SELECT player_id FROM players WHERE player_name = ?",
            ("ユーリ",),
        ).fetchone()["player_id"]
        conn.execute(
            """
            INSERT INTO channels(
                player_id, platform, channel_url, platform_identifier,
                external_channel_id, uploads_playlist_id, image_url, is_owned
            )
            VALUES (?, 'youtube', ?, ?, ?, ?, ?, 1)
            """,
            (
                player_id,
                f"https://www.youtube.com/{identifier}",
                identifier,
                external_channel_id,
                uploads_playlist_id,
                image_url,
            ),
        )
        conn.commit()
        return conn

    def run_fetch(self, db_path: Path, temp_dir: Path, fake_api) -> str:
        skipped_report = temp_dir / "youtube_skipped_channels.csv"
        summary_path = temp_dir / "summary.md"
        stdout = io.StringIO()
        with (
            patch.object(fetch_youtube_archives, "youtube_api", fake_api),
            patch.object(fetch_youtube_archives, "SKIPPED_CHANNELS_REPORT", skipped_report),
            patch.object(sys, "argv", ["fetch_youtube_archives.py", "--db", str(db_path), "--player", "ユーリ"]),
            patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake-key", "GITHUB_STEP_SUMMARY": str(summary_path)}),
            redirect_stdout(stdout),
        ):
            fetch_youtube_archives.main()
        return stdout.getvalue()

    def skipped_rows(self, temp_dir: Path) -> list[dict[str, str]]:
        with (temp_dir / "youtube_skipped_channels.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def status_row(self, conn: sqlite3.Connection) -> sqlite3.Row:
        return conn.execute(
            """
            SELECT last_status, last_reason, last_detail, last_items_seen
            FROM channel_collection_status
            """
        ).fetchone()

    def test_missing_channel_is_skipped_without_failing_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            db_path = temp_dir / "streams.sqlite"
            conn = self.create_db(db_path, identifier="@missing")
            conn.close()
            calls: list[tuple[str, dict[str, str]]] = []

            def fake_api(path: str, params: dict[str, str], api_key: str) -> dict:
                calls.append((path, params))
                self.assertEqual(api_key, "fake-key")
                self.assertEqual(path, "channels")
                self.assertEqual(params["forHandle"], "@missing")
                return {"items": []}

            output = self.run_fetch(db_path, temp_dir, fake_api)

            self.assertEqual([path for path, _ in calls], ["channels"])
            self.assertIn("skipped_channels=1", output)
            self.assertIn("::warning title=Skipped YouTube channel::", output)

            rows = self.skipped_rows(temp_dir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["player_name"], "ユーリ")
            self.assertEqual(rows[0]["platform_identifier"], "@missing")
            self.assertEqual(rows[0]["reason"], "channelNotFound")
            self.assertIn("channels.list returned no items", rows[0]["detail"])

            check_conn = connect(db_path)
            status = self.status_row(check_conn)
            self.assertEqual(status["last_status"], "skipped")
            self.assertEqual(status["last_reason"], "channelNotFound")
            self.assertEqual(status["last_items_seen"], 0)
            run = check_conn.execute("SELECT status FROM collection_runs").fetchone()
            self.assertEqual(run["status"], "success")

    def test_playlist_not_found_skip_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            db_path = temp_dir / "streams.sqlite"
            conn = self.create_db(
                db_path,
                identifier="UC123",
                external_channel_id="UC123",
                uploads_playlist_id="UU123",
                image_url="https://example.test/icon.jpg",
            )
            conn.close()

            def fake_api(path: str, params: dict[str, str], api_key: str) -> dict:
                self.assertEqual(api_key, "fake-key")
                self.assertEqual(path, "playlistItems")
                self.assertEqual(params["playlistId"], "UU123")
                body = json.dumps({"error": {"errors": [{"reason": "playlistNotFound"}]}})
                raise ApiError(404, "https://example.test/youtube", body)

            output = self.run_fetch(db_path, temp_dir, fake_api)

            self.assertIn("skipped_channels=1", output)
            rows = self.skipped_rows(temp_dir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reason"], "playlistNotFound")
            self.assertEqual(rows[0]["external_channel_id"], "UC123")
            self.assertEqual(rows[0]["uploads_playlist_id"], "UU123")

            check_conn = connect(db_path)
            status = self.status_row(check_conn)
            self.assertEqual(status["last_status"], "skipped")
            self.assertEqual(status["last_reason"], "playlistNotFound")


if __name__ == "__main__":
    unittest.main()
