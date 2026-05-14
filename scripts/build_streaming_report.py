from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

from common import DEFAULT_DB_PATH, ROOT_DIR, connect, dedupe_simulcast_groups, init_schema


REPORTS_DIR = ROOT_DIR / "reports"


def hours_expr(column: str = "duration_sec") -> str:
    return f"ROUND(SUM({column}) / 3600.0, 2)"


def hours(seconds: int) -> float:
    return round(seconds / 3600.0, 2)


def build_player_stream_metrics(stream_rows: list[dict[str, Any]]) -> dict[int, dict[str, float | int]]:
    streams_by_player: dict[int, list[dict[str, Any]]] = {}
    for row in stream_rows:
        streams_by_player.setdefault(int(row["player_id"]), []).append(row)

    metrics: dict[int, dict[str, float | int]] = {}
    for player_id, streams in streams_by_player.items():
        stream_count = 0
        total_duration = 0
        shadowverse_duration = 0
        youtube_duration = 0
        twitch_duration = 0
        for group in dedupe_simulcast_groups(streams):
            stream_count += 1
            group_duration = max(int(stream.get("duration_sec") or 0) for stream in group)
            total_duration += group_duration
            if any(int(stream.get("is_shadowverse_related") or 0) == 1 for stream in group):
                shadowverse_duration += group_duration
            youtube_duration += sum(int(stream.get("duration_sec") or 0) for stream in group if stream.get("platform") == "youtube")
            twitch_duration += sum(int(stream.get("duration_sec") or 0) for stream in group if stream.get("platform") == "twitch")

        metrics[player_id] = {
            "stream_count": stream_count,
            "total_hours": hours(total_duration),
            "shadowverse_hours": hours(shadowverse_duration),
            "youtube_hours": hours(youtube_duration),
            "twitch_hours": hours(twitch_duration),
        }
    return metrics


def write_csv(path: Path, rows, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)


def markdown_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(rows, fieldnames: list[str], *, limit: int | None = None) -> str:
    selected_rows = list(rows)
    if limit is not None:
        selected_rows = selected_rows[:limit]
    if not selected_rows:
        return "_No rows._\n"

    lines = [
        "| " + " | ".join(fieldnames) + " |",
        "| " + " | ".join("---" for _ in fieldnames) + " |",
    ]
    for row in selected_rows:
        row_dict = dict(row)
        lines.append("| " + " | ".join(markdown_escape(row_dict.get(name, "")) for name in fieldnames) + " |")
    if limit is not None and len(rows) > limit:
        lines.append(f"\n_Showing top {limit} of {len(rows)} rows. Download the CSV artifact for the full table._")
    return "\n".join(lines) + "\n"


def write_summary(by_player, by_team, *, player_limit: int) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        print("GITHUB_STEP_SUMMARY is not set; skipped Actions summary output.")
        return

    player_fields = [
        "team",
        "player_name",
        "stream_count",
        "total_hours",
        "shadowverse_hours",
        "youtube_hours",
        "twitch_hours",
        "youtube_channel_status",
        "youtube_skipped_reason",
    ]
    team_fields = ["team", "stream_count", "total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"]
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("## Streaming report\n\n")
        f.write("### By team\n\n")
        f.write(markdown_table(by_team, team_fields))
        f.write("\n### By player\n\n")
        f.write(markdown_table(by_player, player_fields, limit=player_limit))
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build aggregate streaming reports from stream_sessions.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--summary", action="store_true", help="Append aggregate tables to GITHUB_STEP_SUMMARY.")
    parser.add_argument("--summary-player-limit", type=int, default=30, help="Maximum player rows to show in the Actions summary.")
    args = parser.parse_args()

    conn = connect(args.db)
    init_schema(conn)

    stream_rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                player_id,
                platform,
                external_stream_id,
                title,
                started_at,
                published_at,
                COALESCE(started_at, published_at, '') AS occurred_at,
                duration_sec,
                is_shadowverse_related
            FROM stream_sessions
            WHERE is_live_archive = 1
            ORDER BY player_id, COALESCE(started_at, published_at, '') DESC, stream_session_id DESC
            """
        ).fetchall()
    ]
    player_metrics = build_player_stream_metrics(stream_rows)

    player_rows = conn.execute(
        """
        WITH
        channel_status AS (
            SELECT
                player_id,
                MAX(CASE WHEN platform = 'youtube' THEN 1 ELSE 0 END) AS has_youtube_channel,
                MAX(CASE WHEN platform = 'twitch' THEN 1 ELSE 0 END) AS has_twitch_channel,
                MAX(CASE WHEN platform = 'youtube' THEN COALESCE(last_status, 'not_checked') END) AS youtube_channel_status,
                MAX(CASE WHEN platform = 'twitch' THEN COALESCE(last_status, 'not_checked') END) AS twitch_channel_status,
                MAX(CASE WHEN platform = 'youtube' THEN COALESCE(last_reason, '') END) AS youtube_skipped_reason,
                MAX(CASE WHEN platform = 'twitch' THEN COALESCE(last_reason, '') END) AS twitch_skipped_reason
            FROM channels
            LEFT JOIN channel_collection_status USING(channel_id)
            WHERE is_owned = 1
            GROUP BY player_id
        ),
        channel_icons AS (
            SELECT
                player_id,
                COALESCE(
                    MAX(CASE WHEN platform = 'youtube' THEN NULLIF(image_url, '') END),
                    MAX(CASE WHEN platform = 'twitch' THEN NULLIF(image_url, '') END),
                    ''
                ) AS player_icon_url
            FROM channels
            WHERE is_owned = 1
            GROUP BY player_id
        )
        SELECT
            p.player_id,
            p.team,
            p.player_name,
            COALESCE(ci.player_icon_url, '') AS player_icon_url,
            COALESCE(cs.has_youtube_channel, 0) AS has_youtube_channel,
            COALESCE(cs.has_twitch_channel, 0) AS has_twitch_channel,
            CASE
                WHEN COALESCE(cs.has_youtube_channel, 0) = 0 THEN 'no_channel'
                ELSE COALESCE(cs.youtube_channel_status, 'not_checked')
            END AS youtube_channel_status,
            CASE
                WHEN COALESCE(cs.has_twitch_channel, 0) = 0 THEN 'no_channel'
                ELSE COALESCE(cs.twitch_channel_status, 'not_checked')
            END AS twitch_channel_status,
            COALESCE(cs.youtube_skipped_reason, '') AS youtube_skipped_reason,
            COALESCE(cs.twitch_skipped_reason, '') AS twitch_skipped_reason
        FROM players p
        LEFT JOIN channel_status cs USING(player_id)
        LEFT JOIN channel_icons ci USING(player_id)
        """
    ).fetchall()
    by_player = []
    for row in player_rows:
        row_dict = dict(row)
        metrics = player_metrics.get(
            int(row_dict["player_id"]),
            {"stream_count": 0, "total_hours": 0.0, "shadowverse_hours": 0.0, "youtube_hours": 0.0, "twitch_hours": 0.0},
        )
        row_dict.update(metrics)
        row_dict.pop("player_id")
        by_player.append(row_dict)
    by_player.sort(key=lambda row: (-float(row["total_hours"]), row["team"], row["player_name"]))
    player_fields = [
        "team",
        "player_name",
        "player_icon_url",
        "stream_count",
        "total_hours",
        "shadowverse_hours",
        "youtube_hours",
        "twitch_hours",
        "has_youtube_channel",
        "has_twitch_channel",
        "youtube_channel_status",
        "twitch_channel_status",
        "youtube_skipped_reason",
        "twitch_skipped_reason",
    ]
    write_csv(
        args.out_dir / "streaming_by_player.csv",
        by_player,
        player_fields,
    )

    by_team_map: dict[str, dict[str, float | int | str]] = {}
    for row in by_player:
        team = str(row["team"])
        team_row = by_team_map.setdefault(
            team,
            {"team": team, "stream_count": 0, "total_hours": 0.0, "shadowverse_hours": 0.0, "youtube_hours": 0.0, "twitch_hours": 0.0},
        )
        team_row["stream_count"] = int(team_row["stream_count"]) + int(row["stream_count"])
        for field in ("total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"):
            team_row[field] = round(float(team_row[field]) + float(row[field]), 2)
    by_team = sorted(by_team_map.values(), key=lambda row: (-float(row["total_hours"]), str(row["team"])))
    write_csv(
        args.out_dir / "streaming_by_team.csv",
        by_team,
        ["team", "stream_count", "total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"],
    )

    print(f"wrote {args.out_dir / 'streaming_by_player.csv'}")
    print(f"wrote {args.out_dir / 'streaming_by_team.csv'}")
    if args.summary:
        write_summary(by_player, by_team, player_limit=args.summary_player_limit)


if __name__ == "__main__":
    main()
