from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from common import (
    DEFAULT_DB_PATH,
    classify_shadowverse,
    connect,
    create_run,
    finish_run,
    init_schema,
    parse_iso8601_duration,
    require_env,
    youtube_api,
)


def youtube_channels(conn: sqlite3.Connection, player_name: str | None = None) -> list[sqlite3.Row]:
    params: list[str] = []
    where = "c.platform = 'youtube' AND c.is_owned = 1"
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


def resolve_channel(conn: sqlite3.Connection, channel: sqlite3.Row, api_key: str) -> tuple[str, str]:
    identifier = channel["platform_identifier"]
    if identifier.startswith("UC"):
        params = {"part": "contentDetails", "id": identifier}
    else:
        params = {"part": "contentDetails", "forHandle": identifier}
    payload = youtube_api("channels", params, api_key)
    items = payload.get("items", [])
    if not items:
        raise RuntimeError(f"YouTube channel not found: {channel['player_name']} {identifier}")
    item = items[0]
    external_channel_id = item["id"]
    uploads_playlist_id = item["contentDetails"]["relatedPlaylists"]["uploads"]
    conn.execute(
        """
        UPDATE channels
        SET external_channel_id = ?, uploads_playlist_id = ?, updated_at = datetime('now')
        WHERE channel_id = ?
        """,
        (external_channel_id, uploads_playlist_id, channel["channel_id"]),
    )
    conn.commit()
    return external_channel_id, uploads_playlist_id


def list_playlist_video_ids(uploads_playlist_id: str, api_key: str, max_pages: int) -> list[str]:
    video_ids: list[str] = []
    page_token = ""
    for _ in range(max_pages):
        params = {
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        payload = youtube_api("playlistItems", params, api_key)
        for item in payload.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            break
    return video_ids


def fetch_videos(video_ids: list[str], api_key: str) -> list[dict]:
    videos: list[dict] = []
    for idx in range(0, len(video_ids), 50):
        payload = youtube_api(
            "videos",
            {
                "part": "snippet,contentDetails,liveStreamingDetails",
                "id": ",".join(video_ids[idx : idx + 50]),
                "maxResults": 50,
            },
            api_key,
        )
        videos.extend(payload.get("items", []))
    return videos


def upsert_video(conn: sqlite3.Connection, channel: sqlite3.Row, video: dict) -> int:
    snippet = video.get("snippet", {})
    content = video.get("contentDetails", {})
    live = video.get("liveStreamingDetails", {})
    title = snippet.get("title", "")
    description = snippet.get("description", "")
    started_at = live.get("actualStartTime") or snippet.get("publishedAt")
    ended_at = live.get("actualEndTime")
    duration_sec = parse_iso8601_duration(content.get("duration"))
    is_live_archive = 1 if live else 0
    is_related, reason = classify_shadowverse(title, description)
    video_id = video["id"]
    cur = conn.execute(
        """
        INSERT INTO stream_sessions(
            platform, player_id, channel_id, external_stream_id, title, url,
            started_at, ended_at, published_at, duration_sec, game_or_category,
            is_live_archive, is_shadowverse_related, shadowverse_match_reason, raw_json, collected_at
        )
        VALUES ('youtube', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(platform, external_stream_id) DO UPDATE SET
            player_id = excluded.player_id,
            channel_id = excluded.channel_id,
            title = excluded.title,
            url = excluded.url,
            started_at = excluded.started_at,
            ended_at = excluded.ended_at,
            published_at = excluded.published_at,
            duration_sec = excluded.duration_sec,
            is_live_archive = excluded.is_live_archive,
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
            f"https://www.youtube.com/watch?v={video_id}",
            started_at,
            ended_at,
            snippet.get("publishedAt"),
            duration_sec,
            is_live_archive,
            is_related,
            reason,
            json.dumps(video, ensure_ascii=False),
        ),
    )
    return cur.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent YouTube uploads/archive metadata for player channels.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--max-pages", type=int, default=1, help="50 videos per page per channel.")
    parser.add_argument("--player", help="Limit to a single player_name.")
    parser.add_argument(
        "--include-non-live",
        action="store_true",
        help="Also store normal uploads. By default only live archives are inserted.",
    )
    args = parser.parse_args()

    api_key = require_env("YOUTUBE_API_KEY")
    conn = connect(args.db)
    init_schema(conn)
    run_id = create_run(conn, "youtube", Path(__file__).name)
    channels_checked = items_seen = items_upserted = 0
    try:
        for channel in youtube_channels(conn, args.player):
            channels_checked += 1
            uploads_playlist_id = channel["uploads_playlist_id"]
            if not uploads_playlist_id:
                _, uploads_playlist_id = resolve_channel(conn, channel, api_key)
            video_ids = list_playlist_video_ids(uploads_playlist_id, api_key, args.max_pages)
            videos = fetch_videos(video_ids, api_key)
            items_seen += len(videos)
            for video in videos:
                if not args.include_non_live and not video.get("liveStreamingDetails"):
                    continue
                items_upserted += upsert_video(conn, channel, video)
            conn.commit()
        finish_run(
            conn,
            run_id,
            status="success",
            channels_checked=channels_checked,
            items_seen=items_seen,
            items_upserted=items_upserted,
        )
        print(f"youtube channels={channels_checked} videos={items_seen} upserts={items_upserted}")
    except Exception as exc:
        finish_run(conn, run_id, status="failed", channels_checked=channels_checked, items_seen=items_seen, error_message=str(exc))
        raise


if __name__ == "__main__":
    main()
