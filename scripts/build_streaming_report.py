from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import DEFAULT_DB_PATH, ROOT_DIR, connect


REPORTS_DIR = ROOT_DIR / "reports"


def hours_expr(column: str = "duration_sec") -> str:
    return f"ROUND(SUM({column}) / 3600.0, 2)"


def write_csv(path: Path, rows, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build aggregate streaming reports from stream_sessions.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args()

    conn = connect(args.db)

    by_player = conn.execute(
        f"""
        SELECT
            p.team,
            p.player_name,
            COUNT(*) AS stream_count,
            {hours_expr()} AS total_hours,
            ROUND(SUM(CASE WHEN s.is_shadowverse_related = 1 THEN s.duration_sec ELSE 0 END) / 3600.0, 2) AS shadowverse_hours,
            ROUND(SUM(CASE WHEN s.platform = 'youtube' THEN s.duration_sec ELSE 0 END) / 3600.0, 2) AS youtube_hours,
            ROUND(SUM(CASE WHEN s.platform = 'twitch' THEN s.duration_sec ELSE 0 END) / 3600.0, 2) AS twitch_hours
        FROM stream_sessions s
        JOIN players p USING(player_id)
        WHERE s.is_live_archive = 1
        GROUP BY p.team, p.player_name
        ORDER BY total_hours DESC
        """
    ).fetchall()
    write_csv(
        args.out_dir / "streaming_by_player.csv",
        by_player,
        ["team", "player_name", "stream_count", "total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"],
    )

    by_team = conn.execute(
        f"""
        SELECT
            p.team,
            COUNT(*) AS stream_count,
            {hours_expr()} AS total_hours,
            ROUND(SUM(CASE WHEN s.is_shadowverse_related = 1 THEN s.duration_sec ELSE 0 END) / 3600.0, 2) AS shadowverse_hours,
            ROUND(SUM(CASE WHEN s.platform = 'youtube' THEN s.duration_sec ELSE 0 END) / 3600.0, 2) AS youtube_hours,
            ROUND(SUM(CASE WHEN s.platform = 'twitch' THEN s.duration_sec ELSE 0 END) / 3600.0, 2) AS twitch_hours
        FROM stream_sessions s
        JOIN players p USING(player_id)
        WHERE s.is_live_archive = 1
        GROUP BY p.team
        ORDER BY total_hours DESC
        """
    ).fetchall()
    write_csv(
        args.out_dir / "streaming_by_team.csv",
        by_team,
        ["team", "stream_count", "total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"],
    )

    print(f"wrote {args.out_dir / 'streaming_by_player.csv'}")
    print(f"wrote {args.out_dir / 'streaming_by_team.csv'}")


if __name__ == "__main__":
    main()
