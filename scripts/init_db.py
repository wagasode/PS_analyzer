from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from common import DEFAULT_DB_PATH, DEFAULT_PLAYERS_CSV, connect, init_schema, is_real_channel, read_players_csv


def upsert_player(conn: sqlite3.Connection, row: dict[str, str]) -> int:
    conn.execute(
        """
        INSERT INTO players(team, player_name, roster_status, x_handle, confidence, source_url, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(player_name, x_handle) DO UPDATE SET
            team = excluded.team,
            roster_status = excluded.roster_status,
            confidence = excluded.confidence,
            source_url = excluded.source_url,
            notes = excluded.notes,
            updated_at = datetime('now')
        """,
        (
            row["team"],
            row["player_name"],
            row["roster_status_as_of_2026-04-28"],
            row["x_handle"],
            row["confidence"],
            row["source_url"],
            row["notes"],
        ),
    )
    return int(
        conn.execute(
            "SELECT player_id FROM players WHERE player_name = ? AND x_handle = ?",
            (row["player_name"], row["x_handle"]),
        ).fetchone()["player_id"]
    )


def upsert_channel(
    conn: sqlite3.Connection,
    *,
    player_id: int,
    platform: str,
    url: str,
    identifier: str,
    is_owned: bool,
) -> None:
    if not identifier:
        identifier = url
    conn.execute(
        """
        INSERT INTO channels(player_id, platform, channel_url, platform_identifier, is_owned, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(platform, platform_identifier) DO UPDATE SET
            player_id = excluded.player_id,
            channel_url = excluded.channel_url,
            is_owned = excluded.is_owned,
            updated_at = datetime('now')
        """,
        (player_id, platform, url, identifier, 1 if is_owned else 0),
    )


def import_master(conn: sqlite3.Connection, csv_path: Path) -> tuple[int, int]:
    rows = read_players_csv(csv_path)
    player_count = 0
    channel_count = 0
    active_channels: set[tuple[str, str]] = set()
    for row in rows:
        player_id = upsert_player(conn, row)
        player_count += 1

        youtube_url = row.get("youtube_url", "").strip()
        youtube_identifier = row.get("youtube_identifier", "").strip()
        if is_real_channel(youtube_url):
            upsert_channel(
                conn,
                player_id=player_id,
                platform="youtube",
                url=youtube_url,
                identifier=youtube_identifier,
                is_owned=True,
            )
            active_channels.add(("youtube", youtube_identifier))
            channel_count += 1

        twitch_url = row.get("twitch_url", "").strip()
        twitch_login = row.get("twitch_login", "").strip()
        if is_real_channel(twitch_url):
            upsert_channel(
                conn,
                player_id=player_id,
                platform="twitch",
                url=twitch_url,
                identifier=twitch_login,
                is_owned=True,
            )
            active_channels.add(("twitch", twitch_login))
            channel_count += 1

    stale_channels = conn.execute("SELECT channel_id, platform, platform_identifier FROM channels").fetchall()
    for channel in stale_channels:
        key = (channel["platform"], channel["platform_identifier"])
        if key in active_channels:
            continue
        has_sessions = conn.execute(
            "SELECT 1 FROM stream_sessions WHERE channel_id = ? LIMIT 1",
            (channel["channel_id"],),
        ).fetchone()
        if has_sessions:
            conn.execute(
                "UPDATE channels SET is_owned = 0, updated_at = datetime('now') WHERE channel_id = ?",
                (channel["channel_id"],),
            )
        else:
            conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel["channel_id"],))

    conn.commit()
    return player_count, channel_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize SQLite DB and import player/channel master CSV.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--players-csv", type=Path, default=DEFAULT_PLAYERS_CSV)
    args = parser.parse_args()

    conn = connect(args.db)
    init_schema(conn)
    players, channels = import_master(conn, args.players_csv)
    print(f"initialized {args.db}")
    print(f"players={players} channels={channels}")


if __name__ == "__main__":
    main()
