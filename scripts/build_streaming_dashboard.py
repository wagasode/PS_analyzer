from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import DEFAULT_DB_PATH, ROOT_DIR, connect, dedupe_simulcast_groups, init_schema
from player_profiles import PLAYER_PROFILES_PUBLIC_PATH
from ps_simulator_ui import write_ps_simulator_assets


REPORTS_DIR = ROOT_DIR / "reports"
PUBLIC_DIR = ROOT_DIR / "public"
FUNCTIONS_DIR = ROOT_DIR / "functions"

INT_FIELDS = {"stream_count", "has_youtube_channel", "has_twitch_channel"}
FLOAT_FIELDS = {"total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"}

DECK_CLASS_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "value": "E",
        "display_name": "エルフ",
        "color_name": "緑",
        "css_class": "deck-class-e",
        "aliases": ("E", "ELF", "エルフ"),
    },
    {
        "value": "R",
        "display_name": "ロイヤル",
        "color_name": "黄色",
        "css_class": "deck-class-r",
        "aliases": ("R", "ROYAL", "ロイヤル"),
    },
    {
        "value": "W",
        "display_name": "ウィッチ",
        "color_name": "青",
        "css_class": "deck-class-w",
        "aliases": ("W", "WITCH", "ウィッチ"),
    },
    {
        "value": "D",
        "display_name": "ドラゴン",
        "color_name": "オレンジ",
        "css_class": "deck-class-d",
        "aliases": ("D", "DRAGON", "ドラゴン"),
    },
    {
        "value": "Ni",
        "display_name": "ナイトメア",
        "color_name": "茶色",
        "css_class": "deck-class-ni",
        "aliases": (
            "Ni",
            "NI",
            "NIGHTMARE",
            "ナイトメア",
            "Nc",
            "NC",
            "NECRO",
            "NECROMANCER",
            "ネクロ",
            "ネクロマンサー",
            "V",
            "VAMPIRE",
            "ヴァンプ",
            "ヴァンパイア",
        ),
    },
    {
        "value": "B",
        "display_name": "ビショップ",
        "color_name": "灰色",
        "css_class": "deck-class-b",
        "aliases": ("B", "BISHOP", "ビショップ"),
    },
    {
        "value": "Nm",
        "display_name": "ネメシス",
        "color_name": "水色",
        "css_class": "deck-class-nm",
        "aliases": ("Nm", "NM", "NEMESIS", "ネメシス"),
    },
)
DECK_CLASS_VALUES = tuple(definition["value"] for definition in DECK_CLASS_DEFINITIONS)
DECK_CLASS_DEFINITIONS_JSON = json.dumps(DECK_CLASS_DEFINITIONS, ensure_ascii=False, indent=6)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_value(field: str, value: str) -> Any:
    if field in INT_FIELDS:
        return int(value or 0)
    if field in FLOAT_FIELDS:
        return float(value or 0)
    return value


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [{field: parse_value(field, value) for field, value in row.items()} for row in reader]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def best_thumbnail_url(thumbnails: dict[str, Any]) -> str:
    for key in ("maxres", "standard", "high", "medium", "default"):
        value = thumbnails.get(key)
        if isinstance(value, dict) and value.get("url"):
            return str(value["url"])
    return ""


def thumbnail_from_raw_json(platform: str, raw_json: str | None) -> str:
    if not raw_json:
        return ""
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return ""
    if platform == "youtube":
        thumbnails = payload.get("snippet", {}).get("thumbnails", {})
        return best_thumbnail_url(thumbnails) if isinstance(thumbnails, dict) else ""
    if platform == "twitch":
        url = payload.get("thumbnail_url", "")
        if isinstance(url, str):
            return url.replace("%{width}", "320").replace("%{height}", "180")
    return ""


def github_run_url() -> str:
    explicit = os.environ.get("GITHUB_RUN_URL")
    if explicit:
        return explicit
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return ""


def build_metadata(player_rows: list[dict[str, Any]], team_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_streams = sum(row["stream_count"] for row in player_rows)
    total_hours = round(sum(row["total_hours"] for row in player_rows), 2)
    shadowverse_hours = round(sum(row["shadowverse_hours"] for row in player_rows), 2)
    return {
        "generated_at": utc_now(),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_url": github_run_url(),
        "commit_sha": os.environ.get("GITHUB_SHA", ""),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "branch_name": os.environ.get("GITHUB_REF_NAME", ""),
        "save_api_endpoint": os.environ.get("SAVE_API_ENDPOINT", ""),
        "player_count": len(player_rows),
        "team_count": len(team_rows),
        "total_streams": total_streams,
        "total_hours": total_hours,
        "shadowverse_hours": shadowverse_hours,
    }


def deck_payload(row) -> dict[str, Any]:
    return {
        "deck_key": row["deck_key"],
        "deck_name": row["deck_name"],
        "class_name": row["class_name"],
        "archetype": row["archetype"],
        "deck_url": row["deck_url"],
        "deck_code": row["deck_code"],
        "notes": row["notes"],
        "confidence": row["confidence"],
        "source_note": row["source_note"],
        "display_order": int(row["display_order"] or 0),
    }


def build_decks_by_stream(conn) -> dict[int, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT
            ssd.stream_session_id,
            d.deck_key,
            d.deck_name,
            d.class_name,
            d.archetype,
            d.deck_url,
            d.deck_code,
            d.notes,
            ssd.confidence,
            ssd.source_note,
            ssd.display_order
        FROM stream_session_decks ssd
        JOIN decks d USING(deck_id)
        ORDER BY ssd.stream_session_id, ssd.display_order, d.deck_name
        """
    ).fetchall()

    decks_by_stream: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        decks_by_stream.setdefault(int(row["stream_session_id"]), []).append(deck_payload(row))
    return decks_by_stream


def dedupe_decks(decks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for deck in decks:
        key = str(deck.get("deck_key") or deck.get("deck_name") or json.dumps(deck, ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        merged.append(deck)
    return merged


def stream_has_deck_info(stream: dict[str, Any]) -> bool:
    decks = stream.get("decks") or []
    if not isinstance(decks, list):
        return False
    return any(
        str(deck.get("deck_key") or deck.get("deck_name") or "").strip()
        for deck in decks
        if isinstance(deck, dict)
    )


def stream_missing_deck_info(stream: dict[str, Any]) -> bool:
    return int(stream.get("is_shadowverse_related") or 0) == 1 and not stream_has_deck_info(stream)


def stream_component(stream: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": stream["platform"],
        "external_stream_id": stream["external_stream_id"],
        "title": stream["title"],
        "url": stream["url"],
        "thumbnail_url": stream["thumbnail_url"],
        "started_at": stream["started_at"],
        "published_at": stream["published_at"],
        "occurred_at": stream["occurred_at"],
        "duration_sec": int(stream["duration_sec"] or 0),
        "is_shadowverse_related": int(stream["is_shadowverse_related"] or 0),
        "decks": stream.get("decks", []),
    }


def primary_stream(streams: list[dict[str, Any]]) -> dict[str, Any]:
    for stream in streams:
        if stream.get("platform") == "youtube":
            return stream
    return streams[0]


def merge_stream_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    primary = primary_stream(group)
    merged = dict(primary)
    merged["duration_sec"] = max(int(stream.get("duration_sec") or 0) for stream in group)
    merged["is_shadowverse_related"] = 1 if any(int(stream.get("is_shadowverse_related") or 0) == 1 for stream in group) else 0
    merged["decks"] = dedupe_decks([deck for stream in group for deck in stream.get("decks", [])])
    merged["missing_deck_info"] = 1 if stream_missing_deck_info(merged) else 0
    if len(group) > 1:
        merged["simulcast_streams"] = [stream_component(stream) for stream in group]
    return merged


def merge_simulcast_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [merge_stream_group(group) for group in dedupe_simulcast_groups(streams)]


def build_player_timelines(db_path: Path) -> list[dict[str, Any]]:
    conn = connect(db_path)
    init_schema(conn)
    decks_by_stream = build_decks_by_stream(conn)
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
            s.stream_session_id,
            p.team,
            p.player_name,
            COALESCE(ci.player_icon_url, '') AS player_icon_url,
            s.platform,
            s.external_stream_id,
            s.title,
            s.url,
            s.started_at,
            s.published_at,
            COALESCE(s.started_at, s.published_at, '') AS occurred_at,
            s.duration_sec,
            s.is_shadowverse_related,
            s.raw_json
        FROM players p
        LEFT JOIN stream_sessions s
          ON s.player_id = p.player_id
         AND s.is_live_archive = 1
        LEFT JOIN channel_icons ci
          ON ci.player_id = p.player_id
        ORDER BY
            p.team,
            p.player_name,
            CASE WHEN COALESCE(s.started_at, s.published_at, '') = '' THEN 1 ELSE 0 END,
            COALESCE(s.started_at, s.published_at, '') DESC,
            s.stream_session_id DESC
        """
    ).fetchall()

    timelines: list[dict[str, Any]] = []
    current_key: tuple[str, str] | None = None
    current_timeline: dict[str, Any] | None = None

    for row in rows:
        team = row["team"]
        player_name = row["player_name"]
        key = (team, player_name)
        if key != current_key:
            current_timeline = {
                "team": team,
                "player_name": player_name,
                "player_icon_url": row["player_icon_url"],
                "streams": [],
            }
            timelines.append(current_timeline)
            current_key = key

        if row["url"] is None:
            continue

        assert current_timeline is not None
        current_timeline["streams"].append(
            {
                "platform": row["platform"],
                "external_stream_id": row["external_stream_id"],
                "title": row["title"],
                "url": row["url"],
                "thumbnail_url": thumbnail_from_raw_json(row["platform"], row["raw_json"]),
                "started_at": row["started_at"],
                "published_at": row["published_at"],
                "occurred_at": row["occurred_at"],
                "duration_sec": int(row["duration_sec"] or 0),
                "is_shadowverse_related": int(row["is_shadowverse_related"] or 0),
                "decks": decks_by_stream.get(int(row["stream_session_id"]), []),
            }
        )

    conn.close()
    for timeline in timelines:
        timeline["streams"] = merge_simulcast_streams(timeline["streams"])
    return timelines


def finalize_deck_usage(deck: dict[str, Any] | None, players: set[str]) -> None:
    if deck is None:
        return
    deck["streams"] = merge_simulcast_streams(deck["streams"])
    deck["stream_count"] = len(deck["streams"])
    deck["player_count"] = len(players)
    deck["players"] = sorted(players)


def build_deck_usage(db_path: Path) -> list[dict[str, Any]]:
    conn = connect(db_path)
    init_schema(conn)
    rows = conn.execute(
        """
        SELECT
            d.deck_key,
            d.deck_name,
            d.class_name,
            d.archetype,
            d.deck_url,
            d.deck_code,
            d.notes,
            s.stream_session_id,
            s.platform,
            s.external_stream_id,
            s.title,
            s.url,
            s.started_at,
            s.published_at,
            COALESCE(s.started_at, s.published_at, '') AS occurred_at,
            s.duration_sec,
            s.is_shadowverse_related,
            s.raw_json,
            p.team,
            p.player_name,
            ssd.confidence,
            ssd.source_note,
            ssd.display_order
        FROM decks d
        LEFT JOIN stream_session_decks ssd USING(deck_id)
        LEFT JOIN stream_sessions s USING(stream_session_id)
        LEFT JOIN players p ON p.player_id = s.player_id
        ORDER BY
            d.class_name,
            d.archetype,
            d.deck_name,
            CASE WHEN COALESCE(s.started_at, s.published_at, '') = '' THEN 1 ELSE 0 END,
            COALESCE(s.started_at, s.published_at, '') DESC,
            s.stream_session_id DESC
        """
    ).fetchall()

    deck_usage: list[dict[str, Any]] = []
    current_key: str | None = None
    current_deck: dict[str, Any] | None = None
    current_players: set[str] = set()

    for row in rows:
        deck_key = row["deck_key"]
        if deck_key != current_key:
            finalize_deck_usage(current_deck, current_players)
            current_deck = {
                "deck_key": deck_key,
                "deck_name": row["deck_name"],
                "class_name": row["class_name"],
                "archetype": row["archetype"],
                "deck_url": row["deck_url"],
                "deck_code": row["deck_code"],
                "notes": row["notes"],
                "stream_count": 0,
                "player_count": 0,
                "players": [],
                "streams": [],
            }
            deck_usage.append(current_deck)
            current_key = deck_key
            current_players = set()

        if row["stream_session_id"] is None:
            continue

        assert current_deck is not None
        player_name = row["player_name"] or ""
        if player_name:
            current_players.add(player_name)
        current_deck["streams"].append(
            {
                "team": row["team"] or "",
                "player_name": player_name,
                "platform": row["platform"],
                "external_stream_id": row["external_stream_id"],
                "title": row["title"],
                "url": row["url"],
                "thumbnail_url": thumbnail_from_raw_json(row["platform"], row["raw_json"]),
                "started_at": row["started_at"],
                "published_at": row["published_at"],
                "occurred_at": row["occurred_at"],
                "duration_sec": int(row["duration_sec"] or 0),
                "is_shadowverse_related": int(row["is_shadowverse_related"] or 0),
                "confidence": row["confidence"],
                "source_note": row["source_note"],
                "display_order": int(row["display_order"] or 0),
            }
        )

    finalize_deck_usage(current_deck, current_players)

    conn.close()
    return deck_usage


INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PS_analyzer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #64748b;
      --border: #d7dde6;
      --accent: #0f766e;
      --accent-soft: #dff7f3;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }

    header {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
    }

    .shell {
      width: min(960px, calc(100% - 32px));
      margin: 0 auto;
    }

    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      padding: 28px 0 22px;
    }

    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.2;
      letter-spacing: 0;
    }

    .meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }

    .site-nav {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .nav-link {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 12px;
      border: 1px solid transparent;
      border-radius: 6px;
      color: var(--muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 700;
    }

    .nav-link:hover,
    .nav-link:focus-visible {
      border-color: var(--border);
      background: var(--panel);
      color: var(--text);
      outline: none;
    }

    .nav-link.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
    }

    main {
      padding: 24px 0 40px;
    }

    .feature-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }

    .feature-card {
      display: grid;
      gap: 10px;
      min-height: 142px;
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      color: inherit;
      text-decoration: none;
      box-shadow: var(--shadow);
    }

    .feature-card:focus-visible,
    .feature-card:hover {
      border-color: var(--accent);
      outline: none;
    }

    .feature-card h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
      letter-spacing: 0;
    }

    .feature-card p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }

    .feature-action {
      align-self: end;
      color: var(--accent);
      font-size: 14px;
      font-weight: 700;
    }

    @media (max-width: 720px) {
      .feature-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="shell topbar">
      <div>
        <h1>PS_analyzer</h1>
        <div class="meta">機能一覧</div>
      </div>
      <nav class="site-nav" aria-label="主要ページ">
        <a class="nav-link active" aria-current="page" href="index.html">トップ</a>
        <a class="nav-link" href="streaming-report.html">配信レポート</a>
        <a class="nav-link" href="ps-simulator.html">PSルール戦略シミュレータ</a>
      </nav>
    </div>
  </header>

  <main>
    <div class="shell">
      <div class="feature-grid" aria-label="機能一覧">
        <a class="feature-card" href="streaming-report.html">
          <h2>配信レポート</h2>
          <p>配信、選手、デッキ別の集計とデッキ情報の確認。</p>
          <span class="feature-action">開く</span>
        </a>
        <a class="feature-card" href="ps-simulator.html">
          <h2>PSルール戦略シミュレータ</h2>
          <p>7デッキ制の提出案とラウンド進行の確認。</p>
          <span class="feature-action">開く</span>
        </a>
      </div>
    </div>
  </main>
</body>
</html>
"""


HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>配信レポート</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #64748b;
      --border: #d7dde6;
      --accent: #0f766e;
      --accent-soft: #dff7f3;
      --warn: #9a3412;
      --warn-soft: #ffedd5;
      --bad: #991b1b;
      --bad-soft: #fee2e2;
      --none: #475569;
      --none-soft: #e2e8f0;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    [hidden] {
      display: none !important;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }

    header {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
    }

    .shell {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
    }

    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      padding: 28px 0 22px;
    }

    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.2;
      letter-spacing: 0;
    }

    .meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }

    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    a.button {
      display: inline-flex;
      align-items: center;
      min-height: 36px;
      padding: 0 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      text-decoration: none;
      font-size: 14px;
      box-shadow: var(--shadow);
    }

    .debug-info {
      margin-top: 10px;
      font-size: 13px;
      color: var(--muted);
    }

    .debug-info summary {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      cursor: pointer;
      color: var(--muted);
      font-weight: 700;
    }

    .debug-list {
      display: grid;
      grid-template-columns: max-content minmax(0, 1fr);
      gap: 4px 10px;
      margin: 8px 0 10px;
      max-width: 720px;
    }

    .debug-list dt {
      color: var(--text);
      font-weight: 700;
    }

    .debug-list dd {
      margin: 0;
      overflow-wrap: anywhere;
    }

    .debug-links {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .site-nav {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .nav-link {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 12px;
      border: 1px solid transparent;
      border-radius: 6px;
      color: var(--muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 700;
    }

    .nav-link:hover,
    .nav-link:focus-visible {
      border-color: var(--border);
      background: var(--panel);
      color: var(--text);
      outline: none;
    }

    .nav-link.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
    }

    main {
      padding: 24px 0 40px;
    }

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin: 18px 0;
    }

    .tabs {
      display: inline-flex;
      padding: 3px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
    }

    .tab {
      min-height: 34px;
      border: 0;
      border-radius: 6px;
      padding: 0 14px;
      background: transparent;
      color: var(--muted);
      font: inherit;
      cursor: pointer;
    }

    .tab.active {
      background: var(--accent);
      color: #fff;
    }

    .search {
      width: min(380px, 100%);
      min-height: 40px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0 12px;
      color: var(--text);
      font: inherit;
      box-shadow: var(--shadow);
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) clamp(320px, 34vw, 440px);
      gap: 16px;
      align-items: start;
    }

    .timeline-panel {
      display: none;
    }

    .workspace.player-mode .timeline-panel,
    .workspace.deck-mode .timeline-panel {
      display: block;
    }

    .workspace.team-mode {
      grid-template-columns: 1fr;
    }

    .workspace.team-mode .timeline-panel {
      display: none;
    }

    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
    }

    .panel-actions {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
      white-space: nowrap;
    }

    .toggle input {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
    }

    h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
      letter-spacing: 0;
    }

    .count {
      color: var(--muted);
      font-size: 14px;
    }

    .table-wrap {
      overflow: auto;
      max-height: calc(100vh - 300px);
    }

    .player-table-wrap {
      max-height: calc(100vh - 250px);
    }

    .player-table-wrap table {
      min-width: 520px;
    }

    .deck-table-wrap table {
      min-width: 640px;
    }

    .player-detail-table-wrap table {
      min-width: 980px;
    }

    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      min-width: 980px;
      font-size: 14px;
    }

    th,
    td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      white-space: nowrap;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #eef2f7;
      color: #334155;
      font-weight: 700;
      user-select: none;
    }

    th.sortable {
      cursor: pointer;
    }

    th.sortable::after {
      content: "↕";
      margin-left: 6px;
      color: #94a3b8;
      font-size: 12px;
    }

    th.sorted-asc::after {
      content: "↑";
      color: var(--accent);
    }

    th.sorted-desc::after {
      content: "↓";
      color: var(--accent);
    }

    tbody tr:hover {
      background: #f8fafc;
    }

    tbody tr.deck-class-row {
      background: linear-gradient(90deg, var(--deck-class-border, var(--border)) 0 6px, var(--deck-class-row, #fff) 6px 38px, #fff 38px);
    }

    tbody tr.deck-class-row:hover {
      background: linear-gradient(90deg, var(--deck-class-border, var(--border)) 0 6px, var(--deck-class-soft, #f8fafc) 6px 38px, #f8fafc 38px);
    }

    tbody tr.missing-deck-row {
      background: linear-gradient(90deg, #fdba74 0 6px, #fff7ed 6px);
    }

    tbody tr.missing-deck-row:hover {
      background: linear-gradient(90deg, #fb923c 0 6px, #ffedd5 6px);
    }

    td.num {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    td.action {
      text-align: center;
    }

    .player-label {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      color: inherit;
    }

    .player-label.heading {
      gap: 12px;
    }

    .avatar {
      position: relative;
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      width: 28px;
      height: 28px;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--none-soft);
      color: var(--none);
      font-size: 11px;
      font-weight: 700;
      line-height: 1;
    }

    .player-label.heading .avatar {
      width: 40px;
      height: 40px;
      font-size: 13px;
    }

    .avatar img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      background: var(--panel);
    }

    .detail-button {
      min-height: 30px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
      cursor: pointer;
    }

    .detail-button.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
    }

    .status {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }

    .status.ok {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .status.skipped {
      background: var(--warn-soft);
      color: var(--warn);
    }

    .status.failed {
      background: var(--bad-soft);
      color: var(--bad);
    }

    .status.no_channel,
    .status.not_checked {
      background: var(--none-soft);
      color: var(--none);
    }

    .empty {
      padding: 28px 16px;
      color: var(--muted);
      text-align: center;
    }

    .timeline-summary {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
      flex-wrap: wrap;
    }

    .timeline-list {
      display: grid;
      gap: 0;
      max-height: calc(100vh - 300px);
      overflow: auto;
    }

    .timeline-item {
      display: grid;
      gap: 12px;
      align-items: start;
      padding: 16px;
      border-bottom: 1px solid var(--border);
    }

    .timeline-item.missing-deck-info {
      background: linear-gradient(90deg, #fdba74 0 5px, #fff7ed 5px);
    }

    .timeline-item:last-child {
      border-bottom: 0;
    }

    .timeline-date {
      display: grid;
      gap: 4px;
      font-variant-numeric: tabular-nums;
    }

    .timeline-date strong {
      font-size: 14px;
      line-height: 1.4;
    }

    .timeline-date span,
    .timeline-meta {
      color: var(--muted);
      font-size: 13px;
    }

    .timeline-thumbnail {
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #eef2f7;
      color: var(--muted);
      text-decoration: none;
    }

    .timeline-thumbnail img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
    }

    .timeline-thumbnail.missing {
      display: grid;
      place-items: center;
      font-size: 13px;
      font-weight: 700;
    }

    .timeline-main {
      min-width: 0;
      display: grid;
      gap: 8px;
    }

    .timeline-title {
      color: var(--text);
      text-decoration: none;
      font-weight: 700;
      white-space: normal;
      overflow-wrap: anywhere;
    }

    .timeline-title:hover {
      text-decoration: underline;
    }

    .timeline-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border-radius: 999px;
      padding: 0 8px;
      background: var(--none-soft);
      color: var(--none);
      font-size: 12px;
      font-weight: 700;
    }

    .pill.youtube {
      background: #fee2e2;
      color: #b91c1c;
    }

    .pill.twitch {
      background: #ede9fe;
      color: #6d28d9;
    }

    .pill.related {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .pill.missing-deck {
      border: 1px solid #fdba74;
      background: var(--warn-soft);
      color: var(--warn);
    }

    .pill.deck {
      border: 1px solid var(--deck-class-border, #bae6fd);
      background: var(--deck-class-soft, #e0f2fe);
      color: var(--deck-class-color, #075985);
      text-decoration: none;
    }

    .deck-class-e {
      --deck-class-color: #166534;
      --deck-class-soft: #dcfce7;
      --deck-class-border: #86efac;
      --deck-class-row: #f2fbf4;
    }

    .deck-class-r {
      --deck-class-color: #854d0e;
      --deck-class-soft: #fef9c3;
      --deck-class-border: #fde047;
      --deck-class-row: #fffbea;
    }

    .deck-class-w {
      --deck-class-color: #1d4ed8;
      --deck-class-soft: #dbeafe;
      --deck-class-border: #93c5fd;
      --deck-class-row: #f1f7ff;
    }

    .deck-class-d {
      --deck-class-color: #c2410c;
      --deck-class-soft: #ffedd5;
      --deck-class-border: #fdba74;
      --deck-class-row: #fff7ed;
    }

    .deck-class-ni {
      --deck-class-color: #78350f;
      --deck-class-soft: #f3e4d0;
      --deck-class-border: #d6a977;
      --deck-class-row: #fbf4ec;
    }

    .deck-class-b {
      --deck-class-color: #475569;
      --deck-class-soft: #e2e8f0;
      --deck-class-border: #94a3b8;
      --deck-class-row: #f4f7fb;
    }

    .deck-class-nm {
      --deck-class-color: #0e7490;
      --deck-class-soft: #cffafe;
      --deck-class-border: #67e8f9;
      --deck-class-row: #ecfeff;
    }

    .deck-class-unknown {
      --deck-class-color: var(--none);
      --deck-class-soft: var(--none-soft);
      --deck-class-border: var(--border);
      --deck-class-row: #f8fafc;
    }

    .deck-cell {
      display: grid;
      gap: 4px;
      min-width: 0;
    }

    .deck-cell-main {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex-wrap: wrap;
    }

    .deck-cell-meta {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
      white-space: normal;
    }

    .missing-deck-count {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border: 1px solid #fdba74;
      border-radius: 999px;
      padding: 0 8px;
      background: var(--warn-soft);
      color: var(--warn);
      font-size: 12px;
      font-weight: 700;
    }

    .missing-deck-zero {
      color: var(--muted);
    }

    .deck-class-badge,
    .deck-legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 24px;
      max-width: 100%;
      border: 1px solid var(--deck-class-border, var(--border));
      border-radius: 999px;
      padding: 0 8px;
      background: var(--deck-class-soft, var(--none-soft));
      color: var(--deck-class-color, var(--none));
      font-size: 12px;
      font-weight: 700;
      line-height: 1.2;
      white-space: nowrap;
    }

    .deck-class-dot {
      flex: 0 0 auto;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--deck-class-color, var(--none));
    }

    .deck-class-badge strong,
    .deck-legend-item strong {
      font-size: 11px;
      font-weight: 800;
    }

    .deck-class-legend {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
      flex-wrap: wrap;
    }

    .timeline-note {
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
      white-space: normal;
    }

    .timeline-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 12px;
      color: var(--text);
      text-decoration: none;
      box-shadow: var(--shadow);
      white-space: nowrap;
      justify-self: start;
    }

    .stream-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .change-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin: 0 0 18px;
      padding: 12px 14px;
      border: 1px solid #bae6fd;
      border-radius: 8px;
      background: #f0f9ff;
      color: #075985;
      box-shadow: var(--shadow);
      font-size: 14px;
    }

    .change-actions,
    .modal-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .save-status {
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .save-status[hidden] {
      display: none;
    }

    .save-feedback {
      margin: -4px 0 12px;
    }

    .modal-save-feedback {
      margin-top: 6px;
    }

    .save-status.ok {
      color: var(--accent);
      font-weight: 700;
    }

    .save-status.error {
      color: var(--bad);
      font-weight: 700;
    }

    .status-details {
      margin-top: 6px;
      color: var(--text);
      font-weight: 400;
    }

    .status-details summary {
      cursor: pointer;
      color: var(--muted);
      font-weight: 700;
    }

    .status-details pre {
      margin: 6px 0 0;
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #f8fafc;
      color: var(--text);
      font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .draft-panel {
      margin: -6px 0 18px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .draft-panel h3 {
      margin: 0;
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      font-size: 15px;
    }

    .draft-list {
      display: grid;
      gap: 0;
    }

    .draft-item {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
      color: var(--muted);
      font-size: 14px;
    }

    .draft-item:last-child {
      border-bottom: 0;
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 20;
      display: grid;
      place-items: center;
      padding: 20px;
      background: rgba(15, 23, 42, 0.42);
    }

    .modal {
      width: min(920px, 100%);
      max-height: min(820px, calc(100vh - 40px));
      display: grid;
      grid-template-rows: auto 1fr;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 24px 80px rgba(15, 23, 42, 0.25);
    }

    #deck-editor-modal .modal {
      width: min(1180px, 100%);
    }

    .modal-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      padding: 16px;
      border-bottom: 1px solid var(--border);
    }

    .modal-body {
      display: grid;
      gap: 18px;
      padding: 16px;
      overflow: auto;
    }

    .deck-editor-layout {
      display: grid;
      grid-template-columns: minmax(340px, 0.95fr) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }

    .editor-form-stack {
      display: grid;
      gap: 18px;
      min-width: 0;
    }

    .editor-section {
      display: grid;
      gap: 10px;
    }

    .editor-section h3 {
      margin: 0;
      font-size: 15px;
    }

    .video-panel {
      display: grid;
      gap: 12px;
      min-width: 0;
      position: sticky;
      top: 0;
      align-self: start;
    }

    .video-platforms,
    .video-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .platform-choice.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
    }

    .video-frame {
      display: grid;
      place-items: center;
      width: 100%;
      aspect-ratio: 16 / 9;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #0f172a;
      color: #e2e8f0;
    }

    .video-frame iframe {
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
    }

    .video-placeholder {
      display: grid;
      gap: 6px;
      padding: 18px;
      text-align: center;
      color: #e2e8f0;
    }

    .video-placeholder strong {
      font-size: 15px;
    }

    .video-placeholder span,
    .video-meta {
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .field {
      display: grid;
      gap: 5px;
      min-width: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .field.full {
      grid-column: 1 / -1;
    }

    .field input,
    .field select,
    .field textarea,
    .editor-input {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 7px 9px;
      color: var(--text);
      font: inherit;
      background: var(--panel);
    }

    .field textarea {
      min-height: 76px;
      resize: vertical;
    }

    .linked-decks,
    .search-results {
      display: grid;
      gap: 8px;
    }

    .linked-deck,
    .search-result {
      display: grid;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f8fafc;
    }

    .deck-card {
      border-color: var(--deck-class-border, var(--border));
      background: linear-gradient(90deg, var(--deck-class-border, var(--border)) 0 5px, var(--deck-class-row, #f8fafc) 5px);
    }

    .linked-deck-head,
    .search-result {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .linked-deck-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .deck-heading {
      display: grid;
      gap: 2px;
      min-width: 0;
    }

    .deck-heading-title {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex-wrap: wrap;
    }

    .deck-heading-title > strong,
    .deck-heading > span {
      overflow-wrap: anywhere;
    }

    .deck-heading > span {
      color: var(--muted);
      font-size: 13px;
    }

    .primary-button,
    .secondary-button,
    .danger-button {
      min-height: 34px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
    }

    .primary-button {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }

    .danger-button {
      border-color: #fecaca;
      background: #fff1f2;
      color: #be123c;
    }

    @media (max-width: 820px) {
      .workspace,
      .workspace.team-mode,
      .workspace.deck-mode {
        grid-template-columns: 1fr;
      }

      .timeline-list,
      .deck-table-wrap,
      .player-table-wrap {
        max-height: none;
      }

      .modal-backdrop {
        align-items: stretch;
        padding: 10px;
      }

      .modal {
        max-height: calc(100vh - 20px);
      }

      .deck-editor-layout {
        grid-template-columns: 1fr;
      }

      .video-panel {
        position: static;
      }

      .form-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 760px) {
      .shell {
        width: min(100% - 20px, 1180px);
      }

      .topbar,
      .toolbar,
      .change-bar,
      .panel-head {
        align-items: stretch;
        flex-direction: column;
      }

      .actions {
        justify-content: flex-start;
      }

      h1 {
        font-size: 24px;
      }

      .table-wrap {
        max-height: none;
      }

    }
  </style>
</head>
<body>
  <header>
    <div class="shell topbar">
      <div>
        <h1>配信レポート</h1>
        <div class="meta" id="metadata">読み込み中...</div>
        <details class="debug-info" id="debug-info" hidden>
          <summary>運用情報</summary>
          <dl class="debug-list" id="debug-list"></dl>
          <div class="debug-links" id="debug-links">
            <a class="button" href="data/streaming_by_team.json">チームJSON</a>
            <a class="button" href="data/streaming_by_player.json">選手JSON</a>
            <a class="button" href="data/streaming_timeline_by_player.json">タイムラインJSON</a>
            <a class="button" href="data/streaming_deck_usage.json">デッキJSON</a>
            <a class="button" id="run-link" href="#" hidden>ワークフロー実行</a>
          </div>
        </details>
      </div>
      <nav class="site-nav" aria-label="主要ページ">
        <a class="nav-link" href="index.html">トップ</a>
        <a class="nav-link active" aria-current="page" href="streaming-report.html">配信レポート</a>
        <a class="nav-link" href="ps-simulator.html">PSルール戦略シミュレータ</a>
      </nav>
    </div>
  </header>

  <main>
    <div class="shell">
      <div class="toolbar">
        <div class="tabs" role="tablist" aria-label="表示切り替え">
          <button class="tab active" type="button" data-view="team">チーム別</button>
          <button class="tab" type="button" data-view="player">選手別</button>
          <button class="tab" type="button" data-view="deck">デッキ別</button>
        </div>
        <input class="search" id="search" type="search" placeholder="チーム、選手、デッキ、ステータスで絞り込み" autocomplete="off">
      </div>

      <div class="save-status save-feedback" id="save-status" data-save-status role="status" aria-live="polite" hidden></div>

      <section class="change-bar" id="change-bar" hidden>
        <div id="change-summary">未保存の変更はありません。</div>
        <div class="change-actions">
          <button class="primary-button save-button" id="save-changes" type="button">変更を保存</button>
          <button class="secondary-button" id="toggle-draft-panel" type="button">変更内容を確認</button>
          <button class="danger-button" id="clear-draft" type="button">下書きを破棄</button>
        </div>
      </section>

      <section class="draft-panel" id="draft-panel" hidden>
        <h3>未保存の変更</h3>
        <div class="draft-list" id="draft-list"></div>
      </section>

      <div class="workspace team-mode" id="workspace">
        <section class="panel">
          <div class="panel-head">
            <h2 id="table-title">チーム別</h2>
            <div class="panel-actions">
              <label class="toggle" id="player-details-control" hidden>
                <input id="show-player-details" type="checkbox">
                詳細を表示
              </label>
              <div class="deck-class-legend" id="deck-class-legend" hidden></div>
              <div class="count" id="row-count">0行</div>
            </div>
          </div>
          <div class="table-wrap" id="table-wrap">
            <table>
              <thead id="table-head"></thead>
              <tbody id="table-body"></tbody>
            </table>
            <div class="empty" id="empty" hidden>一致する行はありません。</div>
          </div>
        </section>

        <section class="panel timeline-panel" id="timeline-panel">
          <div class="panel-head">
            <div>
              <h2 id="timeline-title">選手タイムライン</h2>
              <div class="timeline-summary" id="timeline-summary"></div>
            </div>
            <div class="count" id="timeline-count">0配信</div>
          </div>
          <div class="timeline-list" id="timeline-list"></div>
          <div class="empty" id="timeline-empty" hidden>収集済みの配信アーカイブはありません。</div>
        </section>
      </div>
    </div>
  </main>

  <div class="modal-backdrop" id="deck-editor-modal" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="deck-editor-title">
      <div class="modal-head">
        <div>
          <h2 id="deck-editor-title">アーカイブのデッキ情報追加</h2>
          <div class="timeline-summary" id="deck-editor-summary"></div>
          <div class="save-status modal-save-feedback" id="deck-editor-save-status" data-save-status role="status" aria-live="polite" hidden></div>
        </div>
        <div class="modal-actions">
          <button class="primary-button save-button" type="button">変更を保存</button>
          <button class="secondary-button" id="close-deck-editor" type="button">閉じる</button>
        </div>
      </div>
      <div class="modal-body">
        <div class="deck-editor-layout">
          <section class="editor-section video-panel" aria-label="アーカイブ視聴">
            <h3>アーカイブ視聴</h3>
            <div class="video-platforms" id="video-platforms"></div>
            <div class="video-frame" id="video-frame"></div>
            <div class="video-meta" id="video-meta"></div>
            <div class="video-actions" id="video-actions"></div>
          </section>

          <div class="editor-form-stack">
            <section class="editor-section">
              <h3>使用デッキ一覧</h3>
              <div class="linked-decks" id="linked-decks"></div>
            </section>

            <section class="editor-section">
              <h3>登録済みデッキから追加</h3>
              <input class="editor-input" id="deck-search-input" type="search" placeholder="デッキを検索" autocomplete="off">
              <div class="search-results" id="deck-search-results"></div>
            </section>

            <section class="editor-section">
              <h3>新規デッキを作成</h3>
              <label class="field">デッキ名
                <input id="new-deck-name" type="text" placeholder="連携R" autocomplete="off">
              </label>
              <div class="timeline-summary" id="new-deck-class-hint"></div>
              <div class="modal-actions">
                <button class="secondary-button" id="toggle-new-deck-advanced" type="button" aria-expanded="false">詳細入力</button>
              </div>
              <div class="form-grid">
                <label class="field advanced-deck-field" hidden>デッキキー
                  <input id="new-deck-key" type="text" autocomplete="off">
                </label>
                <label class="field advanced-deck-field" hidden>クラス
                  <input id="new-deck-class" type="text" autocomplete="off">
                </label>
                <label class="field advanced-deck-field" hidden>アーキタイプ
                  <input id="new-deck-archetype" type="text" autocomplete="off">
                </label>
                <label class="field advanced-deck-field" hidden>デッキURL
                  <input id="new-deck-url" type="url" autocomplete="off">
                </label>
                <label class="field advanced-deck-field" hidden>デッキコード
                  <input id="new-deck-code" type="text" autocomplete="off">
                </label>
                <label class="field full advanced-deck-field" hidden>メモ
                  <textarea id="new-deck-notes"></textarea>
                </label>
              </div>
              <div class="modal-actions">
                <button class="primary-button" id="create-deck" type="button">作成して動画内使用デッキとして追加</button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  </div>

  <script>
    const numberFields = new Set(["stream_count", "player_count", "missing_deck_stream_count", "total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"]);
    const statusFields = new Set(["youtube_channel_status", "twitch_channel_status"]);
    const missingDeckKey = "__missing_deck_info__";
    const state = {
      view: "team",
      query: "",
      sortKey: "total_hours",
      sortDirection: "desc",
      team: [],
      player: [],
      deck: [],
      timelines: [],
      missingDeckStreams: [],
      timelineByPlayer: new Map(),
      decksByKey: new Map(),
      originalDecksByKey: new Map(),
      linksByKey: new Map(),
      originalLinksByKey: new Map(),
      streamsByKey: new Map(),
      deckByKey: new Map(),
      selectedPlayerKey: "",
      selectedDeckKey: "",
      editingStreamKey: "",
      previewStreamKey: "",
      deckSearchQuery: "",
      expandedLinkedDeckKeys: new Set(),
      showDraftPanel: false,
      showNewDeckAdvanced: false,
      newDeckClassManual: false,
      saving: false,
      saveStatus: "",
      saveStatusKind: "",
      saveStatusDetail: "",
      newDeckDraft: {
        deck_key: "",
        deck_name: "",
        class_name: "",
        archetype: "",
        deck_url: "",
        deck_code: "",
        notes: ""
      },
      showPlayerDetails: false,
      metadata: {}
    };

    const columns = {
      team: [
        ["team", "チーム"],
        ["stream_count", "配信数"],
        ["total_hours", "総配信時間"],
        ["shadowverse_hours", "SV時間"],
        ["missing_deck_stream_count", "デッキ未付与"],
        ["youtube_hours", "YouTube時間"],
        ["twitch_hours", "Twitch時間"]
      ],
      playerCompact: [
        ["team", "チーム"],
        ["player_name", "選手"],
        ["timeline", "タイムライン"],
        ["missing_deck_stream_count", "デッキ未付与"],
        ["stream_count", "配信数"],
        ["total_hours", "総配信時間"],
        ["shadowverse_hours", "SV時間"]
      ],
      playerDetail: [
        ["team", "チーム"],
        ["player_name", "選手"],
        ["timeline", "タイムライン"],
        ["missing_deck_stream_count", "デッキ未付与"],
        ["stream_count", "配信数"],
        ["total_hours", "総配信時間"],
        ["shadowverse_hours", "SV時間"],
        ["youtube_hours", "YouTube時間"],
        ["twitch_hours", "Twitch時間"],
        ["youtube_channel_status", "YouTube"],
        ["twitch_channel_status", "Twitch"],
        ["youtube_skipped_reason", "YouTube理由"],
        ["twitch_skipped_reason", "Twitch理由"]
      ],
      deck: [
        ["deck_name", "デッキ"],
        ["deck_usage", "利用状況"],
        ["stream_count", "配信数"],
        ["player_count", "選手数"]
      ]
    };

    const viewLabels = {
      team: "チーム別",
      player: "選手別",
      deck: "デッキ別"
    };

    const statusLabels = {
      ok: "正常",
      skipped: "スキップ",
      failed: "失敗",
      no_channel: "チャンネルなし",
      not_checked: "未確認",
      unknown: "不明"
    };
    const deckClassDefinitions = __DECK_CLASS_DEFINITIONS__;
    const deckClassByValue = new Map(deckClassDefinitions.map(definition => [definition.value, definition]));

    function activeColumns() {
      if (state.view === "player") {
        return state.showPlayerDetails ? columns.playerDetail : columns.playerCompact;
      }
      return columns[state.view];
    }

    function formatNumber(value) {
      return new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 }).format(value ?? 0);
    }

    function formatDate(value) {
      if (!value) return "不明";
      return new Intl.DateTimeFormat("ja-JP", {
        dateStyle: "medium",
        timeStyle: "short"
      }).format(new Date(value));
    }

    function statusLabel(value) {
      const key = String(value || "unknown");
      return statusLabels[key] || key.replaceAll("_", " ");
    }

    function confidenceLabel(value) {
      const labels = {
        "": "未設定",
        low: "低",
        medium: "中",
        high: "高"
      };
      return labels[value] || value;
    }

    function playerKey(row) {
      return JSON.stringify([row.team, row.player_name]);
    }

    function streamKey(stream) {
      return JSON.stringify([stream.platform || "", stream.external_stream_id || ""]);
    }

    function streamComponents(stream) {
      const components = Array.isArray(stream.simulcast_streams) && stream.simulcast_streams.length > 0
        ? stream.simulcast_streams
        : [stream];
      return components.map(component => ({
        ...component,
        team: component.team || stream.team || "",
        player_name: component.player_name || stream.player_name || "",
        player_icon_url: component.player_icon_url || stream.player_icon_url || ""
      }));
    }

    function cleanStreamComponents(stream) {
      return streamComponents(stream).map(component => {
        const cleaned = { ...component };
        delete cleaned.simulcast_streams;
        return cleaned;
      });
    }

    function linkKey(streamKeyValue, deckKey) {
      return JSON.stringify([streamKeyValue, deckKey]);
    }

    function cloneJson(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function normalizeInt(value) {
      const parsed = Number.parseInt(value, 10);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    function normalizeText(value) {
      return String(value || "").trim();
    }

    function describeStream(stream) {
      return [stream.team, stream.player_name, stream.title].filter(Boolean).join(" / ");
    }

    function initials(value) {
      const name = String(value || "?").trim();
      return Array.from(name || "?").slice(0, 2).join("").toUpperCase();
    }

    function avatarHtml(name, imageUrl) {
      const fallback = escapeHtml(initials(name));
      const image = imageUrl
        ? `<img src="${escapeHtml(imageUrl)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
        : "";
      return `<span class="avatar" aria-hidden="true">${image}<span>${fallback}</span></span>`;
    }

    function playerLabelHtml(row, className = "") {
      const classes = className ? `player-label ${className}` : "player-label";
      return `
        <span class="${classes}">
          ${avatarHtml(row.player_name, row.player_icon_url)}
          <span>${escapeHtml(row.player_name || "不明な選手")}</span>
        </span>
      `;
    }

    function streamThumbnailHtml(stream) {
      if (!stream.thumbnail_url) {
        return `<div class="timeline-thumbnail missing" aria-hidden="true">サムネイルなし</div>`;
      }
      return `
        <a class="timeline-thumbnail" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer" aria-label="${escapeHtml(stream.title || "アーカイブを開く")}">
          <img src="${escapeHtml(stream.thumbnail_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.closest('.timeline-thumbnail').classList.add('missing'); this.closest('.timeline-thumbnail').textContent='サムネイルなし';">
        </a>
      `;
    }

    function formatDuration(totalSeconds) {
      const seconds = Math.max(Number(totalSeconds || 0), 0);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      if (hours > 0) {
        return `${hours}時間${String(minutes).padStart(2, "0")}分`;
      }
      return `${minutes}分`;
    }

    function platformLabel(value) {
      if (value === "youtube") return "YouTube";
      if (value === "twitch") return "Twitch";
      return statusLabel(value);
    }

    function platformLinksHtml(stream) {
      return streamComponents(stream).map(component => `
        <a class="pill ${escapeHtml(component.platform || "")}" href="${escapeHtml(component.url || stream.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(platformLabel(component.platform))}</a>
      `).join("");
    }

    function archiveActionsHtml(stream) {
      const components = streamComponents(stream);
      return components.map(component => {
        const label = components.length > 1 ? `${platformLabel(component.platform)}を開く` : "アーカイブを開く";
        return `<a class="timeline-link" href="${escapeHtml(component.url || stream.url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
      }).join("");
    }

    function editActionsHtml(stream) {
      const components = streamComponents(stream);
      return components.map(component => {
        const label = components.length > 1 ? `${platformLabel(component.platform)}デッキ情報追加` : "デッキ情報追加";
        return `<button class="secondary-button edit-stream-button" type="button" data-stream-key="${escapeHtml(streamKey(component))}">${escapeHtml(label)}</button>`;
      }).join("");
    }

    function youtubeVideoId(stream) {
      const externalId = normalizeText(stream.external_stream_id || "");
      if (externalId) return externalId;
      try {
        const url = new URL(stream.url || "", window.location.href);
        if (url.hostname.includes("youtu.be")) {
          return url.pathname.split("/").filter(Boolean)[0] || "";
        }
        if (url.hostname.includes("youtube.com")) {
          const fromQuery = url.searchParams.get("v");
          if (fromQuery) return fromQuery;
          const parts = url.pathname.split("/").filter(Boolean);
          if (["live", "embed", "shorts"].includes(parts[0])) {
            return parts[1] || "";
          }
        }
      } catch {
        return "";
      }
      return "";
    }

    function twitchVideoId(stream) {
      const externalId = normalizeText(stream.external_stream_id || "");
      if (externalId) return externalId;
      try {
        const url = new URL(stream.url || "", window.location.href);
        const parts = url.pathname.split("/").filter(Boolean);
        if (parts[0] === "videos") {
          return parts[1] || "";
        }
      } catch {
        return "";
      }
      return "";
    }

    function streamEmbedUrl(stream) {
      if (stream.platform === "youtube") {
        const videoId = youtubeVideoId(stream);
        return videoId ? `https://www.youtube.com/embed/${encodeURIComponent(videoId)}` : "";
      }
      if (stream.platform === "twitch") {
        const videoId = twitchVideoId(stream);
        const parent = window.location.hostname;
        return videoId && parent
          ? `https://player.twitch.tv/?video=${encodeURIComponent(videoId)}&parent=${encodeURIComponent(parent)}`
          : "";
      }
      return "";
    }

    function embedUnavailableMessage(stream) {
      if (stream.platform === "twitch" && !window.location.hostname) {
        return "Twitchの埋め込みには公開ホスト名が必要です。";
      }
      return "このアーカイブは埋め込み表示できません。";
    }

    function streamTimestampMs(stream) {
      const value = stream.occurred_at || stream.started_at || stream.published_at || "";
      const parsed = Date.parse(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    function compareStreamsByLatestTimestampDesc(left, right) {
      const leftTime = streamTimestampMs(left) ?? Number.NEGATIVE_INFINITY;
      const rightTime = streamTimestampMs(right) ?? Number.NEGATIVE_INFINITY;
      if (leftTime !== rightTime) {
        return rightTime - leftTime;
      }
      return [
        "team",
        "player_name",
        "title",
        "platform",
        "external_stream_id"
      ].reduce((result, key) => result || String(left[key] || "").localeCompare(String(right[key] || ""), "ja"), 0);
    }

    function streamsAreSimulcast(left, right) {
      if (new Set([left.platform, right.platform]).size !== 2 || !["youtube", "twitch"].includes(left.platform) || !["youtube", "twitch"].includes(right.platform)) {
        return false;
      }
      if ((left.player_name || "") !== (right.player_name || "") || (left.team || "") !== (right.team || "")) {
        return false;
      }
      const leftTime = streamTimestampMs(left);
      const rightTime = streamTimestampMs(right);
      if (leftTime === null || rightTime === null || Math.abs(leftTime - rightTime) > 10 * 60 * 1000) {
        return false;
      }
      const leftDuration = Number(left.duration_sec || 0);
      const rightDuration = Number(right.duration_sec || 0);
      if (leftDuration > 0 && rightDuration > 0 && Math.abs(leftDuration - rightDuration) > 20 * 60) {
        return false;
      }
      return true;
    }

    function mergeDecks(decks) {
      const seen = new Set();
      const merged = [];
      decks.forEach(deck => {
        const key = deck.deck_key || deck.deck_name || JSON.stringify(deck);
        if (seen.has(key)) return;
        seen.add(key);
        merged.push(deck);
      });
      return merged;
    }

    function mergeSimulcastStreams(streams) {
      const groups = [];
      streams.forEach(stream => {
        let matched = false;
        for (const group of groups) {
          if (group.length >= 2) continue;
          if (group.some(existing => streamsAreSimulcast(stream, existing))) {
            group.push(stream);
            matched = true;
            break;
          }
        }
        if (!matched) {
          groups.push([stream]);
        }
      });

      return groups.map(group => {
        const primary = group.find(stream => stream.platform === "youtube") || group[0];
        const merged = {
          ...primary,
          duration_sec: Math.max(...group.map(stream => Number(stream.duration_sec || 0))),
          is_shadowverse_related: group.some(stream => Number(stream.is_shadowverse_related || 0) === 1) ? 1 : 0,
          decks: mergeDecks(group.flatMap(stream => stream.decks || []))
        };
        if (group.length > 1) {
          merged.simulcast_streams = group.map(stream => ({ ...stream }));
        }
        return merged;
      });
    }

    function hasDeckInfo(stream) {
      const decks = Array.isArray(stream.decks) ? stream.decks : [];
      return decks.some(deck => normalizeText(deck && (deck.deck_key || deck.deck_name)));
    }

    function isMissingDeckInfo(stream) {
      return Number(stream.is_shadowverse_related || 0) === 1 && !hasDeckInfo(stream);
    }

    function missingDeckBadgeHtml() {
      return `<span class="pill missing-deck">! デッキ情報未付与</span>`;
    }

    function missingDeckCountCellHtml(value) {
      const count = Number(value || 0);
      if (count <= 0) {
        return `<td class="num"><span class="missing-deck-zero">0件</span></td>`;
      }
      return `<td class="num"><span class="missing-deck-count">${escapeHtml(formatNumber(count))}件</span></td>`;
    }

    function streamCountLabel(countValue) {
      return `${formatNumber(countValue)}配信`;
    }

    function rowCountLabel(countValue) {
      return `${formatNumber(countValue)}行`;
    }

    function deckLabel(deck) {
      const parts = deckSummary(deck);
      return parts ? `${deck.deck_name} (${parts})` : deck.deck_name;
    }

    function deckPillHtml(deck) {
      const label = escapeHtml(deckLabel(deck));
      const className = `pill deck ${deckClassCssClass(deck)}`;
      if (deck.deck_url) {
        return `<a class="${className}" href="${escapeHtml(deck.deck_url)}" target="_blank" rel="noreferrer">${label}</a>`;
      }
      return `<span class="${className}">${label}</span>`;
    }

    const classAliases = deckClassDefinitions
      .flatMap(definition => [definition.value, ...(definition.aliases || [])]
        .map(alias => [definition.value, normalizeClassToken(alias)]))
      .filter(([, alias]) => alias)
      .sort((left, right) => right[1].length - left[1].length);

    function normalizeClassToken(value) {
      return normalizeText(value).normalize("NFKC").toUpperCase();
    }

    function normalizeClassName(value) {
      const token = normalizeClassToken(value);
      if (!token) return "";
      const direct = deckClassDefinitions.find(definition => normalizeClassToken(definition.value) === token);
      if (direct) return direct.value;
      const matched = classAliases.find(([, alias]) => alias === token);
      return matched ? matched[0] : "";
    }

    function effectiveDeckClassName(deck) {
      return normalizeClassName(deck.class_name) || inferClassName(deck.deck_name);
    }

    function deckClassLabel(className) {
      const normalized = normalizeClassName(className);
      const definition = deckClassByValue.get(normalized);
      return definition ? `${definition.display_name} (${definition.value})` : normalizeText(className);
    }

    function deckClassLabelForDeck(deck) {
      const className = effectiveDeckClassName(deck);
      return className ? deckClassLabel(className) : normalizeText(deck.class_name);
    }

    function deckClassDefinitionForDeck(deck) {
      const className = effectiveDeckClassName(deck);
      return deckClassByValue.get(className) || null;
    }

    function deckClassCssClass(deck) {
      const definition = deckClassDefinitionForDeck(deck);
      return definition ? definition.css_class : "deck-class-unknown";
    }

    function deckClassBadgeHtml(deck) {
      const definition = deckClassDefinitionForDeck(deck);
      const label = definition ? `${definition.display_name} (${definition.value})` : "クラス不明";
      const displayName = definition ? definition.display_name : "不明";
      const code = definition ? definition.value : "?";
      return `
        <span class="deck-class-badge ${escapeHtml(deckClassCssClass(deck))}" title="${escapeHtml(label)}">
          <span class="deck-class-dot" aria-hidden="true"></span>
          <span>${escapeHtml(displayName)}</span>
          <strong>${escapeHtml(code)}</strong>
        </span>
      `;
    }

    function deckClassLegendHtml() {
      return deckClassDefinitions.map(definition => `
        <span class="deck-legend-item ${escapeHtml(definition.css_class)}" title="${escapeHtml(`${definition.display_name} (${definition.value}) / ${definition.color_name}`)}">
          <span class="deck-class-dot" aria-hidden="true"></span>
          <span>${escapeHtml(definition.display_name)}</span>
          <strong>${escapeHtml(definition.value)}</strong>
        </span>
      `).join("");
    }

    function deckSecondarySummary(deck) {
      return [deck.archetype].filter(Boolean).join(" / ");
    }

    function deckSummary(deck) {
      return [deckClassLabelForDeck(deck), deck.archetype].filter(Boolean).join(" / ");
    }

    function deckNameCellHtml(deck) {
      if (deck.is_missing_deck_info_group) {
        return `
          <td>
            <div class="deck-cell">
              <div class="deck-cell-main">
                ${missingDeckBadgeHtml()}
                <span class="timeline-title">デッキ情報未付与</span>
              </div>
              <div class="deck-cell-meta">Shadowverse関連配信の入力作業候補</div>
            </div>
          </td>
        `;
      }
      const name = escapeHtml(deck.deck_name || deck.deck_key || "不明なデッキ");
      const title = deck.deck_url
        ? `<a class="timeline-title" href="${escapeHtml(deck.deck_url)}" target="_blank" rel="noreferrer">${name}</a>`
        : `<span class="timeline-title">${name}</span>`;
      const summary = deckSecondarySummary(deck);
      const meta = summary ? `<div class="deck-cell-meta">${escapeHtml(summary)}</div>` : "";
      return `
        <td>
          <div class="deck-cell">
            <div class="deck-cell-main">
              ${deckClassBadgeHtml(deck)}
              ${title}
            </div>
            ${meta}
          </div>
        </td>
      `;
    }

    function deckHeadingHtml(deck, fallbackKey = "") {
      const name = deck.deck_name || fallbackKey || "不明なデッキ";
      const summary = deckSecondarySummary(deck) || fallbackKey;
      return `
        <div class="deck-heading">
          <div class="deck-heading-title">
            ${deckClassBadgeHtml(deck)}
            <strong>${escapeHtml(name)}</strong>
          </div>
          ${summary ? `<span>${escapeHtml(summary)}</span>` : ""}
        </div>
      `;
    }

    function rowAttributes(row) {
      if (row.is_missing_deck_info_group) {
        return ` class="missing-deck-row"`;
      }
      if (state.view !== "deck") return "";
      return ` class="deck-class-row ${escapeHtml(deckClassCssClass(row))}"`;
    }

    function isClassSuffixMatch(name, alias) {
      if (!name.endsWith(alias)) return false;
      if (name === alias || alias.length > 1) return true;
      const previous = name.slice(0, -alias.length).slice(-1);
      return !/^[A-Z0-9]$/.test(previous);
    }

    function inferClassName(deckName) {
      const name = normalizeClassToken(deckName);
      if (!name) return "";
      for (const [className, aliases] of classAliases) {
        if (isClassSuffixMatch(name, aliases)) {
          return className;
        }
      }
      return "";
    }

    function generatedDeckKey(deckName) {
      const inferredClass = inferClassName(deckName).toLowerCase();
      return `deck-${inferredClass ? `${inferredClass}-` : ""}${Date.now()}`;
    }

    function deckMeta(deck) {
      return {
        deck_key: normalizeText(deck.deck_key),
        deck_name: normalizeText(deck.deck_name) || normalizeText(deck.deck_key),
        class_name: normalizeText(deck.class_name),
        archetype: normalizeText(deck.archetype),
        deck_url: normalizeText(deck.deck_url),
        deck_code: normalizeText(deck.deck_code),
        notes: normalizeText(deck.notes)
      };
    }

    function linkMeta(streamKeyValue, deck) {
      return {
        stream_key: streamKeyValue,
        deck_key: normalizeText(deck.deck_key),
        confidence: normalizeText(deck.confidence),
        source_note: normalizeText(deck.source_note),
        display_order: normalizeInt(deck.display_order)
      };
    }

    function initializeEditorState(timelines, deckUsage) {
      state.decksByKey = new Map();
      state.linksByKey = new Map();
      state.streamsByKey = new Map();

      deckUsage.forEach(deck => {
        const normalized = deckMeta(deck);
        if (normalized.deck_key) {
          state.decksByKey.set(normalized.deck_key, normalized);
        }
      });

      timelines.forEach(timeline => {
        (timeline.streams || []).forEach(stream => {
          stream.team = timeline.team;
          stream.player_name = timeline.player_name;
          stream.player_icon_url = timeline.player_icon_url;
          const components = cleanStreamComponents(stream);
          components.forEach(component => {
            const keyValue = streamKey(component);
            const componentForEditor = components.length > 1
              ? { ...component, simulcast_streams: components.map(item => ({ ...item })) }
              : component;
            state.streamsByKey.set(keyValue, componentForEditor);
            (component.decks || []).forEach(deck => {
              const normalizedDeck = deckMeta(deck);
              if (normalizedDeck.deck_key && !state.decksByKey.has(normalizedDeck.deck_key)) {
                state.decksByKey.set(normalizedDeck.deck_key, normalizedDeck);
              }
              const link = linkMeta(keyValue, deck);
              if (link.deck_key) {
                state.linksByKey.set(linkKey(keyValue, link.deck_key), link);
              }
            });
          });
        });
      });

      state.originalDecksByKey = new Map(Array.from(state.decksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.originalLinksByKey = new Map(Array.from(state.linksByKey, ([key, value]) => [key, cloneJson(value)]));
      materializeDerivedData();
    }

    function linksForStream(streamKeyValue) {
      return Array.from(state.linksByKey.values())
        .filter(link => link.stream_key === streamKeyValue)
        .sort((a, b) => a.display_order - b.display_order || deckLabel(state.decksByKey.get(a.deck_key) || a).localeCompare(deckLabel(state.decksByKey.get(b.deck_key) || b), "ja"));
    }

    function materializeMissingDeckCounts() {
      const teamCounts = new Map();
      const playerCounts = new Map();
      const missingStreams = [];

      state.timelines.forEach(timeline => {
        // 同時配信はここで代表1件にmerge済み。YouTube/Twitchの両方にデッキリンクがない場合だけ1件として警告する。
        const timelineMissingStreams = (timeline.streams || [])
          .filter(isMissingDeckInfo)
          .map(stream => ({
            ...stream,
            team: timeline.team,
            player_name: timeline.player_name,
            player_icon_url: timeline.player_icon_url
          }));
        if (timelineMissingStreams.length === 0) {
          return;
        }
        teamCounts.set(timeline.team, (teamCounts.get(timeline.team) || 0) + timelineMissingStreams.length);
        playerCounts.set(playerKey(timeline), timelineMissingStreams.length);
        missingStreams.push(...timelineMissingStreams);
      });

      state.missingDeckStreams = missingStreams.sort(compareStreamsByLatestTimestampDesc);
      state.team.forEach(row => {
        const count = teamCounts.get(row.team) || 0;
        row.missing_deck_stream_count = count;
        row.missing_deck_status = count > 0 ? "デッキ情報未付与 デッキ未付与" : "";
      });
      state.player.forEach(row => {
        const count = playerCounts.get(playerKey(row)) || 0;
        row.missing_deck_stream_count = count;
        row.missing_deck_status = count > 0 ? "デッキ情報未付与 デッキ未付与" : "";
      });
    }

    function missingDeckRow() {
      const streams = state.missingDeckStreams || [];
      if (streams.length === 0) {
        return null;
      }
      const players = Array.from(new Set(streams.map(stream => stream.player_name).filter(Boolean))).sort();
      return {
        deck_key: missingDeckKey,
        deck_name: "デッキ情報未付与",
        class_name: "",
        archetype: "入力作業候補",
        deck_url: "",
        deck_code: "",
        notes: "",
        stream_count: streams.length,
        player_count: players.length,
        players,
        streams,
        is_missing_deck_info_group: true
      };
    }

    function materializeDerivedData() {
      state.timelines.forEach(timeline => {
        (timeline.streams || []).forEach(stream => {
          const components = streamComponents(stream);
          components.forEach(component => {
            component.decks = linksForStream(streamKey(component)).map(link => ({
              ...state.decksByKey.get(link.deck_key),
              confidence: link.confidence,
              source_note: link.source_note,
              display_order: link.display_order
            }));
          });
          stream.decks = mergeDecks(components.flatMap(component => component.decks || []));
          if (Array.isArray(stream.simulcast_streams) && stream.simulcast_streams.length > 0) {
            stream.simulcast_streams = components;
          }
        });
      });

      materializeMissingDeckCounts();

      const rows = Array.from(state.decksByKey.values()).map(deck => {
        const streams = mergeSimulcastStreams(Array.from(state.linksByKey.values())
          .filter(link => link.deck_key === deck.deck_key)
          .map(link => {
            const stream = state.streamsByKey.get(link.stream_key);
            if (!stream) return null;
            return {
              team: stream.team || "",
              player_name: stream.player_name || "",
              player_icon_url: stream.player_icon_url || "",
              platform: stream.platform,
              external_stream_id: stream.external_stream_id,
              title: stream.title,
              url: stream.url,
              thumbnail_url: stream.thumbnail_url,
              started_at: stream.started_at,
              published_at: stream.published_at,
              occurred_at: stream.occurred_at,
              duration_sec: stream.duration_sec,
              is_shadowverse_related: stream.is_shadowverse_related,
              confidence: link.confidence,
              source_note: link.source_note,
              display_order: link.display_order
            };
          })
          .filter(Boolean))
          .sort(compareStreamsByLatestTimestampDesc);
        const players = Array.from(new Set(streams.map(stream => stream.player_name).filter(Boolean))).sort();
        return {
          ...deck,
          stream_count: streams.length,
          player_count: players.length,
          players,
          streams
        };
      }).sort((a, b) => b.stream_count - a.stream_count || deckLabel(a).localeCompare(deckLabel(b), "ja"));

      const missingRow = missingDeckRow();
      if (missingRow) {
        rows.unshift(missingRow);
      }

      state.deck = rows;
      state.deckByKey = new Map(rows.map(deck => [deck.deck_key, deck]));
      state.timelineByPlayer = new Map(state.timelines.map(timeline => [playerKey(timeline), timeline]));
    }

    function pendingChanges() {
      const addedDecks = Array.from(state.decksByKey.values())
        .filter(deck => !state.originalDecksByKey.has(deck.deck_key));
      const addedLinks = Array.from(state.linksByKey.values())
        .filter(link => !state.originalLinksByKey.has(linkKey(link.stream_key, link.deck_key)));
      const removedLinks = Array.from(state.originalLinksByKey.values())
        .filter(link => !state.linksByKey.has(linkKey(link.stream_key, link.deck_key)));
      const updatedLinks = Array.from(state.linksByKey.values()).filter(link => {
        const original = state.originalLinksByKey.get(linkKey(link.stream_key, link.deck_key));
        if (!original) return false;
        return original.confidence !== link.confidence
          || original.source_note !== link.source_note
          || Number(original.display_order || 0) !== Number(link.display_order || 0);
      });
      return { addedDecks, addedLinks, removedLinks, updatedLinks };
    }

    function changeCount(changes = pendingChanges()) {
      return changes.addedDecks.length + changes.addedLinks.length + changes.removedLinks.length + changes.updatedLinks.length;
    }

    function changeDescription(prefix, link) {
      const deck = state.decksByKey.get(link.deck_key) || state.originalDecksByKey.get(link.deck_key) || { deck_name: link.deck_key };
      const stream = state.streamsByKey.get(link.stream_key) || {};
      return `${prefix}: ${deckLabel(deck)} -> ${describeStream(stream) || "不明なアーカイブ"}`;
    }

    function renderDraftState() {
      const changes = pendingChanges();
      const count = changeCount(changes);
      const bar = document.getElementById("change-bar");
      const panel = document.getElementById("draft-panel");
      const list = document.getElementById("draft-list");
      document.getElementById("change-summary").textContent = count === 0
        ? "未保存の変更はありません。"
        : `${count}件の未保存の変更があります。まだ保存されていません。`;
      bar.hidden = count === 0;
      panel.hidden = count === 0 || !state.showDraftPanel;
      if (count > 0 && state.saveStatusKind === "ok") {
        setSaveStatus("");
      }
      if (count === 0) {
        list.innerHTML = "";
        return;
      }

      const items = [
        ...changes.addedDecks.map(deck => `新規デッキ: ${deckLabel(deck)}`),
        ...changes.addedLinks.map(link => changeDescription("使用デッキ追加", link)),
        ...changes.removedLinks.map(link => changeDescription("使用デッキから削除", link)),
        ...changes.updatedLinks.map(link => changeDescription("使用デッキ情報更新", link))
      ];
      list.innerHTML = items.map(item => `<div class="draft-item">${escapeHtml(item)}</div>`).join("");
    }

    function csvEscape(value) {
      const text = String(value ?? "");
      if (/[",\\n\\r]/.test(text)) {
        return `"${text.replaceAll('"', '""')}"`;
      }
      return text;
    }

    function csvLine(values) {
      return values.map(csvEscape).join(",");
    }

    function serializeDecksCsv() {
      const fields = ["deck_key", "deck_name", "class_name", "archetype", "deck_url", "deck_code", "notes"];
      const rows = Array.from(state.decksByKey.values())
        .sort((a, b) => a.deck_key.localeCompare(b.deck_key, "ja"))
        .map(deck => fields.map(field => deck[field] || ""));
      return [csvLine(fields), ...rows.map(csvLine)].join("\\n") + "\\n";
    }

    function serializeStreamSessionDecksCsv() {
      const fields = ["platform", "external_stream_id", "deck_key", "confidence", "source_note", "display_order"];
      const rows = Array.from(state.linksByKey.values()).map(link => {
        const stream = state.streamsByKey.get(link.stream_key);
        if (!stream) return null;
        return {
          platform: stream.platform || "",
          external_stream_id: stream.external_stream_id || "",
          deck_key: link.deck_key,
          confidence: link.confidence || "",
          source_note: link.source_note || "",
          display_order: String(normalizeInt(link.display_order))
        };
      }).filter(Boolean)
        .sort((a, b) => a.platform.localeCompare(b.platform)
          || a.external_stream_id.localeCompare(b.external_stream_id)
          || normalizeInt(a.display_order) - normalizeInt(b.display_order)
          || a.deck_key.localeCompare(b.deck_key, "ja"))
        .map(row => fields.map(field => row[field] || ""));
      return [csvLine(fields), ...rows.map(csvLine)].join("\\n") + "\\n";
    }

    function validateSavePayload() {
      const errors = [];
      const deckKeys = new Set();
      state.decksByKey.forEach(deck => {
        if (!deck.deck_key) errors.push("デッキキーが必要です。");
        if (!deck.deck_name) errors.push(`${deck.deck_key || "デッキ"} のデッキ名が必要です。`);
        if (deckKeys.has(deck.deck_key)) errors.push(`デッキキーが重複しています: ${deck.deck_key}`);
        deckKeys.add(deck.deck_key);
      });

      const linkKeys = new Set();
      state.linksByKey.forEach(link => {
        const stream = state.streamsByKey.get(link.stream_key);
        if (!deckKeys.has(link.deck_key)) errors.push(`使用デッキが見つかりません: ${link.deck_key}`);
        if (!stream) {
          errors.push(`${link.deck_key} の使用先アーカイブが見つかりません。`);
          return;
        }
        if (!["youtube", "twitch"].includes(stream.platform)) errors.push(`不正なプラットフォームです: ${stream.platform || "空"}`);
        if (!stream.external_stream_id) errors.push(`${stream.title || "配信"} の外部配信IDが必要です。`);
        const keyValue = `${stream.platform}/${stream.external_stream_id}/${link.deck_key}`;
        if (linkKeys.has(keyValue)) errors.push(`アーカイブと使用デッキの組み合わせが重複しています: ${keyValue}`);
        linkKeys.add(keyValue);
      });
      return Array.from(new Set(errors));
    }

    function updateSaveControls() {
      document.querySelectorAll(".save-button").forEach(button => {
        button.disabled = state.saving;
      });
    }

    function setSaveStatus(message, kind = "", detail = "") {
      state.saveStatus = message;
      state.saveStatusKind = kind;
      state.saveStatusDetail = detail;
      document.querySelectorAll("[data-save-status]").forEach(status => {
        status.replaceChildren();
        if (message) {
          const messageText = document.createElement("span");
          messageText.textContent = message;
          status.appendChild(messageText);
        }
        if (detail) {
          const details = document.createElement("details");
          details.className = "status-details";
          const summary = document.createElement("summary");
          summary.textContent = "調査用の詳細";
          const pre = document.createElement("pre");
          pre.textContent = detail;
          details.append(summary, pre);
          status.appendChild(details);
        }
        status.hidden = !message && !detail;
        status.classList.toggle("ok", kind === "ok");
        status.classList.toggle("error", kind === "error");
      });
    }

    function publicSaveApiMessage(status, payloadMessage) {
      if (/branch is not allowed/i.test(payloadMessage)) {
        return "保存先ブランチが保存APIで許可されていません。";
      }
      if (/repository is not allowed/i.test(payloadMessage)) {
        return "保存先リポジトリが保存APIで許可されていません。";
      }
      if (status === 401 || status === 403) {
        return "保存APIへの権限がありません。";
      }
      if (status === 404) {
        return "保存APIの保存先が見つかりません。";
      }
      if (status >= 500) {
        return "保存API側でエラーが発生しました。";
      }
      return `保存APIリクエストに失敗しました。ステータス: ${status}`;
    }

    function saveApiErrorDetail(status, statusText, payloadMessage) {
      const lines = [
        `HTTP status: ${status}${statusText ? ` ${statusText}` : ""}`
      ];
      if (payloadMessage) {
        lines.push(`API message: ${payloadMessage}`);
      }
      return lines.join("\\n");
    }

    async function saveApiJson(url, options = {}) {
      const response = await fetch(url, {
        ...options,
        credentials: "include",
        headers: {
          "Accept": "application/json",
          ...(options.headers || {})
        }
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const payloadMessage = payload && typeof payload === "object"
          ? normalizeText(payload.message || payload.error || "")
          : "";
        const error = new Error(publicSaveApiMessage(response.status, payloadMessage));
        error.debugDetail = saveApiErrorDetail(response.status, response.statusText, payloadMessage);
        throw error;
      }
      return payload;
    }

    function publicSaveErrorMessage(error) {
      if (error && !error.debugDetail && error.name === "TypeError") {
        return "保存APIへの接続に失敗しました。";
      }
      const message = normalizeText(error && error.message ? error.message : error);
      if (!message) return "保存APIへの接続に失敗しました。";
      const firstLine = message.split(/\\r?\\n/)[0];
      return firstLine.length > 140 ? `${firstLine.slice(0, 137)}...` : firstLine;
    }

    function saveErrorDetail(error) {
      const detail = normalizeText(error && error.debugDetail ? error.debugDetail : error && error.message ? error.message : "");
      if (!detail) return "";
      return detail.length > 600 ? `${detail.slice(0, 597)}...` : detail;
    }

    function saveValidationMessage(errors) {
      const messages = errors.slice(0, 2);
      if (errors.length > 2) {
        messages.push(`ほか${errors.length - 2}件の確認が必要です。`);
      }
      return messages.join(" ");
    }

    function buildSavePayload() {
      const changes = pendingChanges();
      return {
        repository: state.metadata.repository || "",
        branch: state.metadata.branch_name || "",
        decks_csv: serializeDecksCsv(),
        stream_session_decks_csv: serializeStreamSessionDecksCsv(),
        changes: {
          added_decks: changes.addedDecks.length,
          added_links: changes.addedLinks.length,
          updated_links: changes.updatedLinks.length,
          removed_links: changes.removedLinks.length,
          total: changeCount(changes)
        }
      };
    }

    function markDraftSaved() {
      state.originalDecksByKey = new Map(Array.from(state.decksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.originalLinksByKey = new Map(Array.from(state.linksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.showDraftPanel = false;
      render();
    }

    async function saveChangesToApi() {
      if (state.saving) return;
      const endpoint = normalizeText(state.metadata.save_api_endpoint || "");
      const repo = normalizeText(state.metadata.repository || "");
      const branch = normalizeText(state.metadata.branch_name || "");
      const errors = validateSavePayload();
      if (!repo || !repo.includes("/")) errors.push("リポジトリは owner/repo 形式である必要があります。");
      if (!branch) errors.push("ブランチが必要です。");
      if (!endpoint) errors.push("このダッシュボードには保存APIエンドポイントが設定されていません。");
      if (changeCount() === 0) errors.push("保存する下書き変更がありません。");
      if (errors.length > 0) {
        setSaveStatus(`保存できません: ${saveValidationMessage(errors)}`, "error");
        return;
      }

      state.saving = true;
      updateSaveControls();
      setSaveStatus("保存中...", "");
      try {
        await saveApiJson(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildSavePayload())
        });
        markDraftSaved();
        setSaveStatus("保存しました。", "ok");
      } catch (error) {
        setSaveStatus(`保存に失敗しました: ${publicSaveErrorMessage(error)}`, "error", saveErrorDetail(error));
      } finally {
        state.saving = false;
        updateSaveControls();
      }
    }

    function rowMatches(row) {
      if (!state.query) return true;
      const haystack = JSON.stringify(row).toLowerCase();
      return haystack.includes(state.query);
    }

    function compareRows(left, right) {
      const key = state.sortKey;
      const a = left[key];
      const b = right[key];
      let result;
      if (numberFields.has(key)) {
        result = Number(a || 0) - Number(b || 0);
      } else {
        result = String(a || "").localeCompare(String(b || ""), "ja");
      }
      return state.sortDirection === "asc" ? result : -result;
    }

    function cellHtml(row, key) {
      const value = row[key] ?? "";
      if (key === "timeline") {
        const keyValue = playerKey(row);
        const active = keyValue === state.selectedPlayerKey ? " active" : "";
        return `<td class="action"><button class="detail-button${active}" type="button" data-player-key="${escapeHtml(keyValue)}">表示</button></td>`;
      }
      if (key === "deck_usage") {
        const active = row.deck_key === state.selectedDeckKey ? " active" : "";
        return `<td class="action"><button class="detail-button deck-detail-button${active}" type="button" data-deck-key="${escapeHtml(row.deck_key)}">表示</button></td>`;
      }
      if (key === "deck_name") {
        return deckNameCellHtml(row);
      }
      if (key === "player_name") {
        return `<td>${playerLabelHtml(row)}</td>`;
      }
      if (key === "class_name") {
        return `<td>${escapeHtml(deckClassLabelForDeck(row))}</td>`;
      }
      if (key === "missing_deck_stream_count") {
        return missingDeckCountCellHtml(value);
      }
      if (numberFields.has(key)) {
        return `<td class="num">${formatNumber(value)}</td>`;
      }
      if (statusFields.has(key)) {
        const className = String(value || "unknown").replaceAll("_", "-");
        return `<td><span class="status ${String(value || "unknown")}">${statusLabel(value)}</span></td>`;
      }
      return `<td>${escapeHtml(value)}</td>`;
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function render() {
      materializeDerivedData();
      let activeTableColumns = activeColumns();
      if (!activeTableColumns.some(([key]) => key === state.sortKey)) {
        state.sortKey = state.view === "deck" ? "stream_count" : "total_hours";
        state.sortDirection = "desc";
        activeTableColumns = activeColumns();
      }
      const rows = state[state.view].filter(rowMatches).sort(compareRows);
      const workspace = document.getElementById("workspace");
      const tableWrap = document.getElementById("table-wrap");
      const playerDetailsControl = document.getElementById("player-details-control");
      const deckClassLegend = document.getElementById("deck-class-legend");
      workspace.classList.toggle("player-mode", state.view === "player");
      workspace.classList.toggle("deck-mode", state.view === "deck");
      workspace.classList.toggle("team-mode", state.view === "team");
      tableWrap.classList.toggle("player-table-wrap", state.view === "player");
      tableWrap.classList.toggle("player-detail-table-wrap", state.view === "player" && state.showPlayerDetails);
      tableWrap.classList.toggle("deck-table-wrap", state.view === "deck");
      playerDetailsControl.hidden = state.view !== "player";
      deckClassLegend.hidden = state.view !== "deck";
      deckClassLegend.innerHTML = state.view === "deck" ? deckClassLegendHtml() : "";
      if (state.view === "player") {
        const visibleKeys = new Set(rows.map(playerKey));
        if (!visibleKeys.has(state.selectedPlayerKey)) {
          state.selectedPlayerKey = rows[0] ? playerKey(rows[0]) : "";
        }
      }
      if (state.view === "deck") {
        const visibleKeys = new Set(rows.map(row => row.deck_key));
        if (!visibleKeys.has(state.selectedDeckKey)) {
          state.selectedDeckKey = rows[0] ? rows[0].deck_key : "";
        }
      }
      document.getElementById("table-title").textContent = viewLabels[state.view] || "";
      document.getElementById("row-count").textContent = rowCountLabel(rows.length);
      document.getElementById("empty").hidden = rows.length > 0;

      document.getElementById("table-head").innerHTML = `<tr>${activeTableColumns.map(([key, label]) => {
        const sortClass = key === state.sortKey ? ` sorted-${state.sortDirection}` : "";
        return `<th class="sortable${sortClass}" data-key="${key}" scope="col">${label}</th>`;
      }).join("")}</tr>`;

      document.getElementById("table-body").innerHTML = rows.map(row => (
        `<tr${rowAttributes(row)}>${activeTableColumns.map(([key]) => cellHtml(row, key)).join("")}</tr>`
      )).join("");

      document.querySelectorAll("th.sortable").forEach(th => {
        th.addEventListener("click", () => {
          const key = th.dataset.key;
          if (state.sortKey === key) {
            state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
          } else {
            state.sortKey = key;
            state.sortDirection = numberFields.has(key) ? "desc" : "asc";
          }
          render();
        });
      });

      document.querySelectorAll(".detail-button[data-player-key]").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedPlayerKey = button.dataset.playerKey || "";
          render();
        });
      });

      document.querySelectorAll(".deck-detail-button").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedDeckKey = button.dataset.deckKey || "";
          render();
        });
      });

      renderSidePanel();
      document.querySelectorAll(".edit-stream-button").forEach(button => {
        button.addEventListener("click", () => {
          openDeckEditor(button.dataset.streamKey || "");
        });
      });
      renderDraftState();
    }

    function renderSidePanel() {
      if (state.view === "deck") {
        renderDeckUsage();
        return;
      }
      renderTimeline();
    }

    function renderTimeline() {
      if (state.view !== "player") {
        return;
      }

      const timeline = state.timelineByPlayer.get(state.selectedPlayerKey);
      const title = document.getElementById("timeline-title");
      const summary = document.getElementById("timeline-summary");
      const count = document.getElementById("timeline-count");
      const list = document.getElementById("timeline-list");
      const empty = document.getElementById("timeline-empty");

      if (!timeline) {
        title.textContent = "選手タイムライン";
        summary.textContent = "";
        count.textContent = streamCountLabel(0);
        list.innerHTML = "";
        empty.hidden = false;
        return;
      }

      const streams = timeline.streams || [];
      title.innerHTML = `${playerLabelHtml(timeline, "heading")} <span>タイムライン</span>`;
      summary.textContent = timeline.team;
      count.textContent = streamCountLabel(streams.length);
      empty.hidden = streams.length > 0;
      list.innerHTML = streams.map(stream => {
        const timestamp = stream.occurred_at || stream.started_at || stream.published_at || "";
        const timestampKind = stream.started_at ? "開始" : stream.published_at ? "公開" : "日付不明";
        const related = Number(stream.is_shadowverse_related || 0) === 1
          ? `<span class="pill related">Shadowverse</span>`
          : "";
        const missingDeck = isMissingDeckInfo(stream);
        const deckTags = (stream.decks || []).map(deckPillHtml).join("");
        return `
          <article class="timeline-item${missingDeck ? " missing-deck-info" : ""}">
            <div class="timeline-date">
              <strong>${escapeHtml(formatDate(timestamp))}</strong>
              <span>${escapeHtml(timestampKind)}</span>
            </div>
            ${streamThumbnailHtml(stream)}
            <div class="timeline-main">
              <a class="timeline-title" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer">${escapeHtml(stream.title || "無題の配信")}</a>
              <div class="timeline-tags">
                ${platformLinksHtml(stream)}
                <span class="pill">${escapeHtml(formatDuration(stream.duration_sec))}</span>
                ${related}
                ${missingDeck ? missingDeckBadgeHtml() : ""}
                ${deckTags}
              </div>
            </div>
            <div class="stream-actions">
              ${archiveActionsHtml(stream)}
              ${editActionsHtml(stream)}
            </div>
          </article>
        `;
      }).join("");
    }

    function renderDeckUsage() {
      const deck = state.deckByKey.get(state.selectedDeckKey);
      const title = document.getElementById("timeline-title");
      const summary = document.getElementById("timeline-summary");
      const count = document.getElementById("timeline-count");
      const list = document.getElementById("timeline-list");
      const empty = document.getElementById("timeline-empty");

      if (!deck) {
        title.textContent = "デッキ利用状況";
        summary.textContent = "";
        count.textContent = streamCountLabel(0);
        list.innerHTML = "";
        empty.textContent = "デッキが選択されていません。";
        empty.hidden = false;
        return;
      }

      const streams = deck.streams || [];
      const missingDeckGroup = deck.is_missing_deck_info_group;
      title.textContent = missingDeckGroup ? "デッキ情報未付与のアーカイブ" : `${deck.deck_name}のアーカイブ`;
      summary.textContent = missingDeckGroup
        ? "Shadowverse関連配信 / 同時配信は代表1件で表示"
        : [deckClassLabelForDeck(deck), deck.archetype, deck.notes].filter(Boolean).join(" · ");
      count.textContent = streamCountLabel(streams.length);
      empty.textContent = missingDeckGroup ? "デッキ情報未付与の配信はありません。" : "紐づいた配信アーカイブはありません。";
      empty.hidden = streams.length > 0;
      list.innerHTML = streams.map(stream => {
        const timestamp = stream.occurred_at || stream.started_at || stream.published_at || "";
        const timestampKind = stream.started_at ? "開始" : stream.published_at ? "公開" : "日付不明";
        const related = Number(stream.is_shadowverse_related || 0) === 1
          ? `<span class="pill related">Shadowverse</span>`
          : "";
        const note = !missingDeckGroup && stream.source_note
          ? `<div class="timeline-note">${escapeHtml(stream.source_note)}</div>`
          : "";
        const confidence = !missingDeckGroup && stream.confidence
          ? `<span class="pill">${escapeHtml(stream.confidence)}</span>`
          : "";
        return `
          <article class="timeline-item${missingDeckGroup ? " missing-deck-info" : ""}">
            <div class="timeline-date">
              <strong>${escapeHtml(formatDate(timestamp))}</strong>
              <span>${escapeHtml(timestampKind)}</span>
            </div>
            ${streamThumbnailHtml(stream)}
            <div class="timeline-main">
              <a class="timeline-title" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer">${escapeHtml(stream.title || "無題の配信")}</a>
              <div class="timeline-meta">${escapeHtml(stream.team || "")} / ${escapeHtml(stream.player_name || "不明な選手")}</div>
              <div class="timeline-tags">
                ${platformLinksHtml(stream)}
                <span class="pill">${escapeHtml(formatDuration(stream.duration_sec))}</span>
                ${related}
                ${confidence}
                ${missingDeckGroup ? missingDeckBadgeHtml() : ""}
              </div>
              ${note}
            </div>
            <div class="stream-actions">
              ${archiveActionsHtml(stream)}
              ${editActionsHtml(stream)}
            </div>
          </article>
        `;
      }).join("");
    }

    function openDeckEditor(streamKeyValue) {
      if (!state.streamsByKey.has(streamKeyValue)) {
        return;
      }
      state.editingStreamKey = streamKeyValue;
      state.previewStreamKey = streamKeyValue;
      state.deckSearchQuery = "";
      renderDeckEditor();
      document.getElementById("deck-editor-modal").hidden = false;
    }

    function closeDeckEditor() {
      state.editingStreamKey = "";
      state.previewStreamKey = "";
      document.getElementById("deck-editor-modal").hidden = true;
    }

    function previewStreamForEditor() {
      return state.streamsByKey.get(state.previewStreamKey)
        || state.streamsByKey.get(state.editingStreamKey);
    }

    function renderVideoPreview() {
      const editingStream = state.streamsByKey.get(state.editingStreamKey);
      if (!editingStream) {
        return;
      }
      const components = cleanStreamComponents(editingStream);
      if (!components.some(component => streamKey(component) === state.previewStreamKey)) {
        state.previewStreamKey = state.editingStreamKey;
      }
      const previewStream = previewStreamForEditor() || editingStream;
      const embedUrl = streamEmbedUrl(previewStream);
      const platforms = document.getElementById("video-platforms");
      const frame = document.getElementById("video-frame");
      const meta = document.getElementById("video-meta");
      const actions = document.getElementById("video-actions");

      platforms.innerHTML = components.length > 1
        ? components.map(component => {
            const keyValue = streamKey(component);
            const active = keyValue === state.previewStreamKey ? " active" : "";
            return `<button class="secondary-button platform-choice${active}" type="button" data-preview-stream-key="${escapeHtml(keyValue)}">${escapeHtml(platformLabel(component.platform))}</button>`;
          }).join("")
        : `<span class="pill ${escapeHtml(previewStream.platform || "")}">${escapeHtml(platformLabel(previewStream.platform))}</span>`;

      frame.innerHTML = embedUrl
        ? `<iframe src="${escapeHtml(embedUrl)}" title="${escapeHtml(previewStream.title || "アーカイブ動画")}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share" allowfullscreen></iframe>`
        : `<div class="video-placeholder"><strong>${escapeHtml(embedUnavailableMessage(previewStream))}</strong><span>外部リンクからアーカイブを開けます。</span></div>`;

      meta.textContent = [
        platformLabel(previewStream.platform),
        formatDate(previewStream.occurred_at || previewStream.started_at || previewStream.published_at || ""),
        previewStream.title || "無題の配信"
      ].filter(Boolean).join(" / ");
      actions.innerHTML = `<a class="timeline-link" href="${escapeHtml(previewStream.url || "#")}" target="_blank" rel="noreferrer">外部で開く</a>`;

      document.querySelectorAll(".platform-choice").forEach(button => {
        button.addEventListener("click", () => {
          state.previewStreamKey = button.dataset.previewStreamKey || state.editingStreamKey;
          renderVideoPreview();
        });
      });
    }

    function renderDeckEditor() {
      const stream = state.streamsByKey.get(state.editingStreamKey);
      if (!stream) {
        closeDeckEditor();
        return;
      }

      document.getElementById("deck-editor-title").textContent = "アーカイブのデッキ情報追加";
      document.getElementById("deck-editor-summary").textContent = describeStream(stream);
      renderVideoPreview();
      renderLinkedDecks();

      const searchInput = document.getElementById("deck-search-input");
      searchInput.value = state.deckSearchQuery;
      renderDeckSearchResults();

      document.getElementById("new-deck-key").value = state.newDeckDraft.deck_key;
      document.getElementById("new-deck-name").value = state.newDeckDraft.deck_name;
      document.getElementById("new-deck-class").value = state.newDeckDraft.class_name;
      document.getElementById("new-deck-archetype").value = state.newDeckDraft.archetype;
      document.getElementById("new-deck-url").value = state.newDeckDraft.deck_url;
      document.getElementById("new-deck-code").value = state.newDeckDraft.deck_code;
      document.getElementById("new-deck-notes").value = state.newDeckDraft.notes;
      renderNewDeckAdvanced();
    }

    function renderNewDeckAdvanced() {
      const inferredClass = inferClassName(state.newDeckDraft.deck_name);
      const className = normalizeClassName(state.newDeckDraft.class_name) || inferredClass;
      document.getElementById("new-deck-class-hint").textContent = state.newDeckDraft.deck_name
        ? `推定クラス: ${className ? deckClassLabel(className) : "不明"}`
        : "デッキ名を入力すると推定クラスが表示されます。";
      document.querySelectorAll(".advanced-deck-field").forEach(field => {
        field.hidden = !state.showNewDeckAdvanced;
      });
      document.getElementById("toggle-new-deck-advanced").setAttribute("aria-expanded", String(state.showNewDeckAdvanced));
      document.getElementById("toggle-new-deck-advanced").textContent = state.showNewDeckAdvanced
        ? "詳細入力を閉じる"
        : "詳細入力";
    }

    function renderLinkedDecks() {
      const container = document.getElementById("linked-decks");
      const links = linksForStream(state.editingStreamKey);
      if (links.length === 0) {
        const stream = state.streamsByKey.get(state.editingStreamKey);
        const message = stream && isMissingDeckInfo(stream)
          ? "デッキ情報未付与です。使用デッキはまだありません。"
          : "使用デッキはまだありません。";
        container.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
        return;
      }

      container.innerHTML = links.map(link => {
        const deck = state.decksByKey.get(link.deck_key) || { deck_name: link.deck_key };
        const keyValue = linkKey(link.stream_key, link.deck_key);
        const expanded = state.expandedLinkedDeckKeys.has(keyValue);
        const detailForm = expanded ? `
          <div class="form-grid">
            <label class="field">信頼度
              <select class="link-field" data-link-key="${escapeHtml(keyValue)}" data-field="confidence">
                ${["", "low", "medium", "high"].map(value => `<option value="${escapeHtml(value)}"${value === link.confidence ? " selected" : ""}>${escapeHtml(confidenceLabel(value))}</option>`).join("")}
              </select>
            </label>
            <label class="field">表示順
              <input class="link-field" data-link-key="${escapeHtml(keyValue)}" data-field="display_order" type="number" min="0" step="1" value="${escapeHtml(link.display_order)}">
            </label>
            <label class="field full">メモ
              <textarea class="link-field" data-link-key="${escapeHtml(keyValue)}" data-field="source_note">${escapeHtml(link.source_note)}</textarea>
            </label>
          </div>
        ` : "";
        return `
          <article class="linked-deck deck-card ${escapeHtml(deckClassCssClass(deck))}">
            <div class="linked-deck-head">
              ${deckHeadingHtml(deck, link.deck_key)}
              <div class="linked-deck-actions">
                <button class="secondary-button toggle-link-details" type="button" data-link-key="${escapeHtml(keyValue)}">${expanded ? "詳細を閉じる" : "詳細"}</button>
                <button class="danger-button unlink-deck" type="button" data-link-key="${escapeHtml(keyValue)}">使用デッキから削除</button>
              </div>
            </div>
            ${detailForm}
          </article>
        `;
      }).join("");

      document.querySelectorAll(".toggle-link-details").forEach(button => {
        button.addEventListener("click", () => {
          const keyValue = button.dataset.linkKey || "";
          if (state.expandedLinkedDeckKeys.has(keyValue)) {
            state.expandedLinkedDeckKeys.delete(keyValue);
          } else {
            state.expandedLinkedDeckKeys.add(keyValue);
          }
          renderDeckEditor();
        });
      });

      document.querySelectorAll(".unlink-deck").forEach(button => {
        button.addEventListener("click", () => {
          const keyValue = button.dataset.linkKey || "";
          state.linksByKey.delete(keyValue);
          state.expandedLinkedDeckKeys.delete(keyValue);
          render();
          renderDeckEditor();
        });
      });

      document.querySelectorAll(".link-field").forEach(field => {
        field.addEventListener("input", () => {
          updateLinkField(field.dataset.linkKey || "", field.dataset.field || "", field.value, false);
        });
        field.addEventListener("change", () => {
          updateLinkField(field.dataset.linkKey || "", field.dataset.field || "", field.value);
        });
      });
    }

    function renderDeckSearchResults() {
      const container = document.getElementById("deck-search-results");
      const query = state.deckSearchQuery.toLowerCase();
      const linked = new Set(linksForStream(state.editingStreamKey).map(link => link.deck_key));
      const decks = Array.from(state.decksByKey.values())
        .filter(deck => !query || JSON.stringify(deck).toLowerCase().includes(query))
        .sort((a, b) => deckLabel(a).localeCompare(deckLabel(b), "ja"))
        .slice(0, 8);

      if (decks.length === 0) {
        container.innerHTML = `<div class="empty">既存デッキが見つかりません。</div>`;
        return;
      }

      container.innerHTML = decks.map(deck => {
        const alreadyLinked = linked.has(deck.deck_key);
        return `
          <div class="search-result deck-card ${escapeHtml(deckClassCssClass(deck))}">
            ${deckHeadingHtml(deck, deck.deck_key)}
            <button class="secondary-button add-existing-deck" type="button" data-deck-key="${escapeHtml(deck.deck_key)}"${alreadyLinked ? " disabled" : ""}>${alreadyLinked ? "使用デッキに追加済み" : "動画内使用デッキとして追加"}</button>
          </div>
        `;
      }).join("");

      document.querySelectorAll(".add-existing-deck").forEach(button => {
        button.addEventListener("click", () => {
          addDeckLink(button.dataset.deckKey || "");
        });
      });
    }

    function addDeckLink(deckKey) {
      if (!deckKey || !state.decksByKey.has(deckKey) || !state.editingStreamKey) {
        return;
      }
      const keyValue = linkKey(state.editingStreamKey, deckKey);
      if (state.linksByKey.has(keyValue)) {
        return;
      }
      state.linksByKey.set(keyValue, {
        stream_key: state.editingStreamKey,
        deck_key: deckKey,
        confidence: "",
        source_note: "",
        display_order: linksForStream(state.editingStreamKey).length + 1
      });
      render();
      renderDeckEditor();
    }

    function updateLinkField(keyValue, field, value, rerender = true) {
      const link = state.linksByKey.get(keyValue);
      if (!link) return;
      if (field === "display_order") {
        link.display_order = normalizeInt(value);
      } else if (field === "confidence" || field === "source_note") {
        link[field] = normalizeText(value);
      }
      state.linksByKey.set(keyValue, link);
      if (rerender) {
        render();
        renderDeckEditor();
      } else {
        materializeDerivedData();
        renderDraftState();
      }
    }

    function createAndLinkDeck() {
      const draft = deckMeta(state.newDeckDraft);
      draft.class_name = normalizeClassName(draft.class_name);
      if (!draft.class_name) {
        draft.class_name = inferClassName(draft.deck_name);
      }
      if (!draft.deck_key && draft.deck_name) {
        draft.deck_key = generatedDeckKey(draft.deck_name);
      }
      if (!draft.deck_key || !draft.deck_name) {
        window.alert("デッキ名が必要です。");
        return;
      }
      if (state.decksByKey.has(draft.deck_key)) {
        window.alert("同じデッキキーが既に存在します。");
        return;
      }
      state.decksByKey.set(draft.deck_key, draft);
      state.newDeckDraft = {
        deck_key: "",
        deck_name: "",
        class_name: "",
        archetype: "",
        deck_url: "",
        deck_code: "",
        notes: ""
      };
      state.newDeckClassManual = false;
      state.showNewDeckAdvanced = false;
      addDeckLink(draft.deck_key);
    }

    function clearDraft() {
      state.decksByKey = new Map(Array.from(state.originalDecksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.linksByKey = new Map(Array.from(state.originalLinksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.showDraftPanel = false;
      materializeDerivedData();
      render();
      if (state.editingStreamKey) {
        renderDeckEditor();
      }
    }

    function renderMetadata() {
      const meta = state.metadata;
      document.getElementById("metadata").textContent = `更新: ${formatDate(meta.generated_at)}`;
      const debugRows = [
        ["生成日時", formatDate(meta.generated_at)],
        ["チーム数", formatNumber(meta.team_count)],
        ["選手数", formatNumber(meta.player_count)],
        ["配信数", formatNumber(meta.total_streams)],
        ["総配信時間", formatNumber(meta.total_hours)],
        ["SV時間", formatNumber(meta.shadowverse_hours)],
        ["リポジトリ", meta.repository || "未設定"],
        ["ブランチ", meta.branch_name || "未設定"],
        ["ワークフロー実行", meta.run_number ? `#${meta.run_number}` : "未設定"],
        ["保存API", meta.save_api_endpoint ? "設定済み" : "未設定"]
      ];
      document.getElementById("debug-list").innerHTML = debugRows
        .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`)
        .join("");
      document.getElementById("debug-info").hidden = false;
      if (meta.run_url) {
        const link = document.getElementById("run-link");
        link.href = meta.run_url;
        link.hidden = false;
      }
    }

    async function loadData() {
      const [team, player, timelines, deckUsage, metadata] = await Promise.all([
        fetch("data/streaming_by_team.json").then(response => response.json()),
        fetch("data/streaming_by_player.json").then(response => response.json()),
        fetch("data/streaming_timeline_by_player.json").then(response => response.json()),
        fetch("data/streaming_deck_usage.json").then(response => response.json()),
        fetch("data/metadata.json").then(response => response.json())
      ]);
      state.team = team;
      state.player = player;
      state.timelines = timelines;
      initializeEditorState(timelines, deckUsage);
      state.metadata = metadata;
      renderMetadata();
      render();
    }

    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(item => item.classList.remove("active"));
        tab.classList.add("active");
        state.view = tab.dataset.view;
        state.sortKey = state.view === "deck" ? "stream_count" : "total_hours";
        state.sortDirection = "desc";
        render();
      });
    });

    document.getElementById("search").addEventListener("input", event => {
      state.query = event.target.value.trim().toLowerCase();
      render();
    });

    document.getElementById("show-player-details").addEventListener("change", event => {
      state.showPlayerDetails = event.target.checked;
      render();
    });

    document.getElementById("toggle-draft-panel").addEventListener("click", () => {
      state.showDraftPanel = !state.showDraftPanel;
      renderDraftState();
    });

    document.getElementById("clear-draft").addEventListener("click", clearDraft);
    document.querySelectorAll(".save-button").forEach(button => {
      button.addEventListener("click", saveChangesToApi);
    });
    document.getElementById("close-deck-editor").addEventListener("click", closeDeckEditor);

    document.getElementById("deck-editor-modal").addEventListener("click", event => {
      if (event.target.id === "deck-editor-modal") {
        closeDeckEditor();
      }
    });

    document.getElementById("deck-search-input").addEventListener("input", event => {
      state.deckSearchQuery = event.target.value.trim();
      renderDeckSearchResults();
    });

    document.getElementById("toggle-new-deck-advanced").addEventListener("click", () => {
      state.showNewDeckAdvanced = !state.showNewDeckAdvanced;
      renderNewDeckAdvanced();
    });

    [
      ["new-deck-key", "deck_key"],
      ["new-deck-name", "deck_name"],
      ["new-deck-class", "class_name"],
      ["new-deck-archetype", "archetype"],
      ["new-deck-url", "deck_url"],
      ["new-deck-code", "deck_code"],
      ["new-deck-notes", "notes"]
    ].forEach(([id, field]) => {
      document.getElementById(id).addEventListener("input", event => {
        state.newDeckDraft[field] = event.target.value;
        if (field === "class_name") {
          state.newDeckClassManual = true;
        }
        if (field === "deck_name" && !state.newDeckClassManual) {
          state.newDeckDraft.class_name = inferClassName(event.target.value);
          document.getElementById("new-deck-class").value = state.newDeckDraft.class_name;
        }
        if (field === "deck_name" || field === "class_name") {
          renderNewDeckAdvanced();
        }
      });
    });

    document.getElementById("create-deck").addEventListener("click", createAndLinkDeck);

    loadData().catch(error => {
      document.getElementById("metadata").textContent = "レポートデータの読み込みに失敗しました。";
      document.getElementById("empty").hidden = false;
      document.getElementById("empty").textContent = error.message;
    });
  </script>
</body>
</html>
"""


def render_index_html() -> str:
    return INDEX_HTML


def render_html() -> str:
    return HTML.replace("__DECK_CLASS_DEFINITIONS__", DECK_CLASS_DEFINITIONS_JSON)


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def copy_pages_functions(out_dir: Path) -> list[Path]:
    if not FUNCTIONS_DIR.exists():
        return []

    destination = out_dir / "functions"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(FUNCTIONS_DIR, destination)
    return sorted(path for path in destination.rglob("*") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static dashboard for streaming reports.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--out-dir", type=Path, default=PUBLIC_DIR)
    args = parser.parse_args()

    player_rows = read_csv(args.reports_dir / "streaming_by_player.csv")
    team_rows = read_csv(args.reports_dir / "streaming_by_team.csv")
    timelines = build_player_timelines(args.db)
    deck_usage = build_deck_usage(args.db)
    metadata = build_metadata(player_rows, team_rows)

    write_html(args.out_dir / "index.html", render_index_html())
    write_html(args.out_dir / "streaming-report.html", render_html())
    write_json(args.out_dir / "data" / "streaming_by_player.json", player_rows)
    write_json(args.out_dir / "data" / "streaming_by_team.json", team_rows)
    write_json(args.out_dir / "data" / "streaming_timeline_by_player.json", timelines)
    write_json(args.out_dir / "data" / "streaming_deck_usage.json", deck_usage)
    write_json(args.out_dir / "data" / "metadata.json", metadata)
    write_ps_simulator_assets(args.out_dir)
    copied_functions = copy_pages_functions(args.out_dir)

    print(f"wrote {args.out_dir / 'index.html'}")
    print(f"wrote {args.out_dir / 'streaming-report.html'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_by_player.json'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_by_team.json'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_timeline_by_player.json'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_deck_usage.json'}")
    print(f"wrote {args.out_dir / 'data' / 'metadata.json'}")
    print(f"wrote {args.out_dir / 'ps-simulator.html'}")
    print(f"wrote {args.out_dir / 'data' / 'ps_simulator' / 'sample_dataset.json'}")
    print(f"wrote {args.out_dir / PLAYER_PROFILES_PUBLIC_PATH}")
    for path in copied_functions:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
