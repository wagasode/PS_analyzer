from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from common import DEFAULT_DB_PATH, DEFAULT_PLAYERS_CSV, connect, init_schema, read_players_csv, utc_now


PLAYER_PROFILES_SCHEMA_VERSION = "player-profiles.v1"
PLAYER_PROFILES_PUBLIC_PATH = Path("data") / "player_profiles.json"
PLAYER_PROFILE_SOURCE = "players_channels_csv"

PLAYER_ID_OVERRIDES: dict[tuple[str, str], str] = {
    ("MURASH GAMING", "マイト"): "player-maito",
    ("MURASH GAMING", "glory"): "player-glory",
    ("MURASH GAMING", "Toby"): "player-toby",
    ("MURASH GAMING", "Spicies"): "player-spicies",
}


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _short_digest(*values: str) -> str:
    joined = "\0".join(values)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def player_profile_key(team_name: str, player_name: str) -> tuple[str, str]:
    return team_name.strip(), player_name.strip()


def player_id_for_row(row: dict[str, str]) -> str:
    team_name = row.get("team", "").strip()
    player_name = row.get("player_name", "").strip()
    override = PLAYER_ID_OVERRIDES.get(player_profile_key(team_name, player_name))
    if override:
        return override

    base = row.get("x_handle", "").strip() or player_name
    slug = _slugify(base)
    if slug:
        return f"player-{slug}"
    return f"player-{_short_digest(team_name, player_name)}"


def aliases_for_row(row: dict[str, str], player_id: str) -> list[str]:
    player_name = row.get("player_name", "")
    x_handle = row.get("x_handle", "")
    id_alias = player_id.removeprefix("player-")
    return _unique_strings(
        [
            player_name,
            x_handle,
            x_handle.removeprefix("@"),
            id_alias,
            _slugify(player_name),
        ]
    )


def read_player_icon_urls(db_path: Path = DEFAULT_DB_PATH) -> dict[tuple[str, str], str]:
    if not db_path.exists():
        return {}

    conn = connect(db_path)
    try:
        init_schema(conn)
        rows = conn.execute(
            """
            WITH channel_icons AS (
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
                p.team,
                p.player_name,
                COALESCE(ci.player_icon_url, '') AS player_icon_url
            FROM players p
            LEFT JOIN channel_icons ci USING(player_id)
            """
        ).fetchall()
    except sqlite3.DatabaseError:
        return {}
    finally:
        conn.close()

    return {
        player_profile_key(str(row["team"]), str(row["player_name"])): str(row["player_icon_url"] or "")
        for row in rows
        if row["team"] is not None and row["player_name"] is not None
    }


def build_player_profiles(
    *,
    players_csv_path: Path = DEFAULT_PLAYERS_CSV,
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: str | None = None,
    icon_urls: dict[tuple[str, str], str] | None = None,
) -> dict[str, Any]:
    rows = read_players_csv(players_csv_path)
    icon_urls_by_key = read_player_icon_urls(db_path) if icon_urls is None else icon_urls

    profiles: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for row in rows:
        team_name = row.get("team", "").strip()
        player_name = row.get("player_name", "").strip()
        if not player_name:
            continue

        player_id = player_id_for_row(row)
        if player_id in used_ids:
            player_id = f"{player_id}-{_short_digest(team_name, player_name)}"
        used_ids.add(player_id)

        icon_url = icon_urls_by_key.get(player_profile_key(team_name, player_name), "")
        profiles.append(
            {
                "playerId": player_id,
                "playerName": player_name,
                "displayName": player_name,
                "teamName": team_name,
                "team": team_name,
                "iconUrl": icon_url,
                "playerIconUrl": icon_url,
                "aliases": aliases_for_row(row, player_id),
                "source": PLAYER_PROFILE_SOURCE,
            }
        )

    return {
        "schemaVersion": PLAYER_PROFILES_SCHEMA_VERSION,
        "source": PLAYER_PROFILE_SOURCE,
        "generatedAt": generated_at or utc_now(),
        "players": profiles,
    }


def write_player_profiles_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build shared player display profiles.")
    parser.add_argument("--players-csv", type=Path, default=DEFAULT_PLAYERS_CSV)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--out", type=Path, default=Path("public") / PLAYER_PROFILES_PUBLIC_PATH)
    args = parser.parse_args()

    payload = build_player_profiles(players_csv_path=args.players_csv, db_path=args.db)
    write_player_profiles_json(args.out, payload)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
