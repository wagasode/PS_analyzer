from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.parse
from pathlib import Path

from common import (
    DEFAULT_DB_PATH,
    classify_shadowverse,
    connect,
    create_run,
    finish_run,
    http_json,
    init_schema,
    parse_twitch_duration,
    require_env,
)


def twitch_channels(conn: sqlite3.Connection, player_name: str | None = None) -> list[sqlite3.Row]:
    params: list[str] = []
    where = "c.platform = 'twitch' AND c.is_owned = 1"
    if player_name:
        where += " AND p.player_name = ?"
        params.append(player_name)
    return conn.execute(
        f"""
        SELECT c.*, p.player_name, p.team
        FROM channels c
        JOIN players p USING(player_id)
        WHERE {where}
        ORDER BY p.team, p.player_name
        """,
        params,
    ).fetchall()


def get_app_token(client_id: str, client_secret: str) -> str:
    payload = http_json(
        "https://id.twitch.tv/oauth2/token",
        method="POST",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
    )
    return payload["access_token"]


def twitch_api(path: str, params: dict[str, str | int], client_id: str, token: str) -> dict:
    query = urllib.parse.urlencode(params)
    return http_json(
        f"https://api.twitch.tv/helix/{path}?{query}",
        headers={"Client-Id": client_id, "Authorization": f"Bearer {token}"},
    )


def resolve_users(channels: list[sqlite3.Row], client_id: str, token: str) -> dict[str, dict]:
    users: dict[str, dict] = {}
    for idx in range(0, len(channels), 100):
        chunk = channels[idx : idx + 100]
        params = [("login", ch["platform_identifier"]) for ch in chunk]
        query = urllib.parse.urlencode(params)
        payload = http_json(
            f"https://api.twitch.tv/helix/users?{query}",
            headers={"Client-Id": client_id, "Authorization": f"Bearer {token}"},
        )
        for item in payload.get("data", []):
            users[item["login"].lower()] = item
    return users


def fetch_archives(user_id: str, client_id: str, token: str, max_pages: int) -> list[dict]:
    videos: list[dict] = []
    after = ""
    for _ in range(max_pages):
        params: dict[str, str | int] = {"user_id": user_id, "type": "archive", "first": 100}
        if after:
            params["after"] = after
        payload = twitch_api("videos", params, client_id, token)
        videos.extend(payload.get("data", []))
        after = payload.get("pagination", {}).get("cursor", "")
        if not after:
            break
    return videos


def update_channel_status(conn: sqlite3.Connection, channel_id: int, status: str, reason: str, detail: str, items_seen: int) -> None:
    conn.execute(
        """
        INSERT INTO channel_collection_status(
            channel_id, last_checked_at, last_status, last_reason, last_detail, last_items_seen
        )
        VALUES (?, datetime('now'), ?, ?, ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            last_checked_at = datetime('now'),
            last_status = excluded.last_status,
            last_reason = excluded.last_reason,
            last_detail = excluded.last_detail,
            last_items_seen = excluded.last_items_seen
        """,
        (channel_id, status, reason, detail, items_seen),
    )


def upsert_video(conn: sqlite3.Connection, channel: sqlite3.Row, video: dict) -> int:
    title = video.get("title", "")
    game_or_category = video.get("game_name", "") or video.get("type", "")
    is_related, reason = classify_shadowverse(title, game_or_category=game_or_category)
    video_id = video["id"]
    cur = conn.execute(
        """
        INSERT INTO stream_sessions(
            platform, player_id, channel_id, external_stream_id, title, url,
            started_at, ended_at, published_at, duration_sec, game_or_category,
            is_live_archive, is_shadowverse_related, shadowverse_match_reason, raw_json, collected_at
        )
        VALUES ('twitch', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 1, ?, ?, ?, datetime('now'))
        ON CONFLICT(platform, external_stream_id) DO UPDATE SET
            player_id = excluded.player_id,
            channel_id = excluded.channel_id,
            title = excluded.title,
            url = excluded.url,
            started_at = excluded.started_at,
            published_at = excluded.published_at,
            duration_sec = excluded.duration_sec,
            game_or_category = excluded.game_or_category,
            is_shadowverse_related = excluded.is_shadowverse_related,
            shadowverse_match_reason = excluded.shadowverse_match_reason,
            raw_json = excluded.raw_json,
            collected_at = datetime('now')
        """,
        (
            channel["player_id"],
            channel["channel_id"],
            video_id,
            title,
            video.get("url", ""),
            video.get("created_at"),
            video.get("published_at"),
            parse_twitch_duration(video.get("duration")),
            game_or_category,
            is_related,
            reason,
            json.dumps(video, ensure_ascii=False),
        ),
    )
    return cur.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Twitch VOD archive metadata for player channels.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--max-pages", type=int, default=1, help="100 VODs per page per channel.")
    parser.add_argument("--player", help="Limit to a single player_name.")
    args = parser.parse_args()

    client_id = require_env("TWITCH_CLIENT_ID")
    client_secret = require_env("TWITCH_CLIENT_SECRET")
    conn = connect(args.db)
    init_schema(conn)
    run_id = create_run(conn, "twitch", Path(__file__).name)
    channels_checked = items_seen = items_upserted = 0
    try:
        token = get_app_token(client_id, client_secret)
        channels = twitch_channels(conn, args.player)
        users = resolve_users(channels, client_id, token)
        for channel in channels:
            channels_checked += 1
            login = channel["platform_identifier"].lower()
            user = users.get(login)
            if not user:
                raise RuntimeError(f"Twitch user not found: {channel['player_name']} {login}")
            conn.execute(
                """
                UPDATE channels
                SET external_channel_id = ?, updated_at = datetime('now')
                WHERE channel_id = ?
                """,
                (user["id"], channel["channel_id"]),
            )
            videos = fetch_archives(user["id"], client_id, token, args.max_pages)
            items_seen += len(videos)
            for video in videos:
                items_upserted += upsert_video(conn, channel, video)
            update_channel_status(conn, channel["channel_id"], "ok", "", "", len(videos))
            conn.commit()
        finish_run(
            conn,
            run_id,
            status="success",
            channels_checked=channels_checked,
            items_seen=items_seen,
            items_upserted=items_upserted,
        )
        print(f"twitch channels={channels_checked} vods={items_seen} upserts={items_upserted}")
    except Exception as exc:
        finish_run(conn, run_id, status="failed", channels_checked=channels_checked, items_seen=items_seen, error_message=str(exc))
        raise


if __name__ == "__main__":
    main()
