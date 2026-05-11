from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from common import DEFAULT_DB_PATH, ROOT_DIR, connect, init_schema


REPORTS_DIR = ROOT_DIR / "reports"


def hours_expr(column: str = "duration_sec") -> str:
    return f"ROUND(SUM({column}) / 3600.0, 2)"


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

    by_player = conn.execute(
        f"""
        WITH player_streams AS (
            SELECT
                player_id,
                COUNT(*) AS stream_count,
                {hours_expr()} AS total_hours,
                ROUND(SUM(CASE WHEN is_shadowverse_related = 1 THEN duration_sec ELSE 0 END) / 3600.0, 2) AS shadowverse_hours,
                ROUND(SUM(CASE WHEN platform = 'youtube' THEN duration_sec ELSE 0 END) / 3600.0, 2) AS youtube_hours,
                ROUND(SUM(CASE WHEN platform = 'twitch' THEN duration_sec ELSE 0 END) / 3600.0, 2) AS twitch_hours
            FROM stream_sessions
            WHERE is_live_archive = 1
            GROUP BY player_id
        ),
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
        )
        SELECT
            p.team,
            p.player_name,
            COALESCE(ps.stream_count, 0) AS stream_count,
            COALESCE(ps.total_hours, 0.0) AS total_hours,
            COALESCE(ps.shadowverse_hours, 0.0) AS shadowverse_hours,
            COALESCE(ps.youtube_hours, 0.0) AS youtube_hours,
            COALESCE(ps.twitch_hours, 0.0) AS twitch_hours,
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
        LEFT JOIN player_streams ps USING(player_id)
        LEFT JOIN channel_status cs USING(player_id)
        ORDER BY total_hours DESC, p.team, p.player_name
        """
    ).fetchall()
    player_fields = [
        "team",
        "player_name",
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

    by_team = conn.execute(
        f"""
        WITH player_streams AS (
            SELECT
                player_id,
                COUNT(*) AS stream_count,
                SUM(duration_sec) AS total_duration_sec,
                SUM(CASE WHEN is_shadowverse_related = 1 THEN duration_sec ELSE 0 END) AS shadowverse_duration_sec,
                SUM(CASE WHEN platform = 'youtube' THEN duration_sec ELSE 0 END) AS youtube_duration_sec,
                SUM(CASE WHEN platform = 'twitch' THEN duration_sec ELSE 0 END) AS twitch_duration_sec
            FROM stream_sessions
            WHERE is_live_archive = 1
            GROUP BY player_id
        )
        SELECT
            p.team,
            COALESCE(SUM(ps.stream_count), 0) AS stream_count,
            ROUND(COALESCE(SUM(ps.total_duration_sec), 0) / 3600.0, 2) AS total_hours,
            ROUND(COALESCE(SUM(ps.shadowverse_duration_sec), 0) / 3600.0, 2) AS shadowverse_hours,
            ROUND(COALESCE(SUM(ps.youtube_duration_sec), 0) / 3600.0, 2) AS youtube_hours,
            ROUND(COALESCE(SUM(ps.twitch_duration_sec), 0) / 3600.0, 2) AS twitch_hours
        FROM players p
        LEFT JOIN player_streams ps USING(player_id)
        GROUP BY p.team
        ORDER BY total_hours DESC, p.team
        """
    ).fetchall()
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
