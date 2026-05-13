from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import DEFAULT_DB_PATH, ROOT_DIR, connect, init_schema


REPORTS_DIR = ROOT_DIR / "reports"
PUBLIC_DIR = ROOT_DIR / "public"

INT_FIELDS = {"stream_count", "has_youtube_channel", "has_twitch_channel"}
FLOAT_FIELDS = {"total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"}


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
    return timelines


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
            if current_deck is not None:
                current_deck["player_count"] = len(current_players)
                current_deck["players"] = sorted(current_players)
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
        current_deck["stream_count"] = len(current_deck["streams"])

    if current_deck is not None:
        current_deck["player_count"] = len(current_players)
        current_deck["players"] = sorted(current_players)

    conn.close()
    return deck_usage


HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Streaming Report</title>
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

    main {
      padding: 24px 0 40px;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .stat {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      box-shadow: var(--shadow);
    }

    .stat span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }

    .stat strong {
      display: block;
      margin-top: 4px;
      font-size: 22px;
      line-height: 1.2;
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
      min-width: 760px;
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

    .pill.deck {
      background: #e0f2fe;
      color: #075985;
      text-decoration: none;
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

    .save-status.ok {
      color: var(--accent);
      font-weight: 700;
    }

    .save-status.error {
      color: var(--bad);
      font-weight: 700;
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

    #save-modal {
      z-index: 30;
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

    .editor-section {
      display: grid;
      gap: 10px;
    }

    .editor-section h3 {
      margin: 0;
      font-size: 15px;
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

    .deck-heading strong,
    .deck-heading span {
      overflow-wrap: anywhere;
    }

    .deck-heading span {
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

      .summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
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
        <h1>Streaming Report</h1>
        <div class="meta" id="metadata">Loading...</div>
      </div>
      <div class="actions">
        <a class="button" href="data/streaming_by_team.json">Team JSON</a>
        <a class="button" href="data/streaming_by_player.json">Player JSON</a>
        <a class="button" href="data/streaming_timeline_by_player.json">Timeline JSON</a>
        <a class="button" href="data/streaming_deck_usage.json">Deck JSON</a>
        <a class="button" id="run-link" href="#" hidden>Workflow run</a>
      </div>
    </div>
  </header>

  <main>
    <div class="shell">
      <section class="summary" aria-label="Summary">
        <div class="stat"><span>Teams</span><strong id="team-count">-</strong></div>
        <div class="stat"><span>Players</span><strong id="player-count">-</strong></div>
        <div class="stat"><span>Streams</span><strong id="stream-count">-</strong></div>
        <div class="stat"><span>Total hours</span><strong id="total-hours">-</strong></div>
        <div class="stat"><span>SV hours</span><strong id="sv-hours">-</strong></div>
      </section>

      <div class="toolbar">
        <div class="tabs" role="tablist" aria-label="Report views">
          <button class="tab active" type="button" data-view="team">By team</button>
          <button class="tab" type="button" data-view="player">By player</button>
          <button class="tab" type="button" data-view="deck">By deck</button>
        </div>
        <input class="search" id="search" type="search" placeholder="Filter by team, player, deck, or status" autocomplete="off">
      </div>

      <section class="change-bar" id="change-bar" hidden>
        <div id="change-summary">No unsaved changes.</div>
        <div class="change-actions">
          <button class="primary-button open-save-modal-button" id="open-save-modal" type="button">Save changes</button>
          <button class="secondary-button" id="toggle-draft-panel" type="button">Review changes</button>
          <button class="danger-button" id="clear-draft" type="button">Clear draft</button>
        </div>
      </section>

      <section class="draft-panel" id="draft-panel" hidden>
        <h3>Pending changes</h3>
        <div class="draft-list" id="draft-list"></div>
      </section>

      <div class="workspace team-mode" id="workspace">
        <section class="panel">
          <div class="panel-head">
            <h2 id="table-title">By team</h2>
            <div class="panel-actions">
              <label class="toggle" id="player-details-control" hidden>
                <input id="show-player-details" type="checkbox">
                Show details
              </label>
              <div class="count" id="row-count">0 rows</div>
            </div>
          </div>
          <div class="table-wrap" id="table-wrap">
            <table>
              <thead id="table-head"></thead>
              <tbody id="table-body"></tbody>
            </table>
            <div class="empty" id="empty" hidden>No matching rows.</div>
          </div>
        </section>

        <section class="panel timeline-panel" id="timeline-panel">
          <div class="panel-head">
            <div>
              <h2 id="timeline-title">Player timeline</h2>
              <div class="timeline-summary" id="timeline-summary"></div>
            </div>
            <div class="count" id="timeline-count">0 streams</div>
          </div>
          <div class="timeline-list" id="timeline-list"></div>
          <div class="empty" id="timeline-empty" hidden>No stream archives collected.</div>
        </section>
      </div>
    </div>
  </main>

  <div class="modal-backdrop" id="save-modal" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="save-modal-title">
      <div class="modal-head">
        <div>
          <h2 id="save-modal-title">Save deck edits</h2>
          <div class="timeline-summary" id="save-modal-summary"></div>
        </div>
        <div class="modal-actions">
          <button class="secondary-button" id="close-save-modal" type="button">Close</button>
        </div>
      </div>
      <div class="modal-body">
        <section class="editor-section">
          <h3>GitHub target</h3>
          <div class="form-grid">
            <label class="field">Repository
              <input id="save-repository" type="text" placeholder="owner/repo" autocomplete="off">
            </label>
            <label class="field">Branch
              <input id="save-branch" type="text" placeholder="branch-name" autocomplete="off">
            </label>
            <label class="field full">GitHub token
              <input id="save-token" type="password" autocomplete="off" placeholder="Fine-grained token with Contents: Read and write">
            </label>
          </div>
          <div class="save-status" id="save-status"></div>
          <div class="modal-actions">
            <button class="primary-button" id="save-to-github" type="button">Save to GitHub</button>
          </div>
        </section>
      </div>
    </section>
  </div>

  <div class="modal-backdrop" id="deck-editor-modal" hidden>
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="deck-editor-title">
      <div class="modal-head">
        <div>
          <h2 id="deck-editor-title">Edit archive decks</h2>
          <div class="timeline-summary" id="deck-editor-summary"></div>
        </div>
        <div class="modal-actions">
          <button class="primary-button open-save-modal-button" type="button">Save changes</button>
          <button class="secondary-button" id="close-deck-editor" type="button">Close</button>
        </div>
      </div>
      <div class="modal-body">
        <section class="editor-section">
          <h3>Linked decks</h3>
          <div class="linked-decks" id="linked-decks"></div>
        </section>

        <section class="editor-section">
          <h3>Add existing deck</h3>
          <input class="editor-input" id="deck-search-input" type="search" placeholder="Search decks" autocomplete="off">
          <div class="search-results" id="deck-search-results"></div>
        </section>

        <section class="editor-section">
          <h3>Create new deck</h3>
          <label class="field">Deck name
            <input id="new-deck-name" type="text" placeholder="連携R" autocomplete="off">
          </label>
          <div class="timeline-summary" id="new-deck-class-hint"></div>
          <div class="modal-actions">
            <button class="secondary-button" id="toggle-new-deck-advanced" type="button" aria-expanded="false">Advanced input</button>
          </div>
          <div class="form-grid">
            <label class="field advanced-deck-field" hidden>Deck key
              <input id="new-deck-key" type="text" autocomplete="off">
            </label>
            <label class="field advanced-deck-field" hidden>Class
              <input id="new-deck-class" type="text" autocomplete="off">
            </label>
            <label class="field advanced-deck-field" hidden>Archetype
              <input id="new-deck-archetype" type="text" autocomplete="off">
            </label>
            <label class="field advanced-deck-field" hidden>Deck URL
              <input id="new-deck-url" type="url" autocomplete="off">
            </label>
            <label class="field advanced-deck-field" hidden>Deck code
              <input id="new-deck-code" type="text" autocomplete="off">
            </label>
            <label class="field full advanced-deck-field" hidden>Notes
              <textarea id="new-deck-notes"></textarea>
            </label>
          </div>
          <div class="modal-actions">
            <button class="primary-button" id="create-deck" type="button">Create and link</button>
          </div>
        </section>
      </div>
    </section>
  </div>

  <script>
    const numberFields = new Set(["stream_count", "player_count", "total_hours", "shadowverse_hours", "youtube_hours", "twitch_hours"]);
    const statusFields = new Set(["youtube_channel_status", "twitch_channel_status"]);
    const state = {
      view: "team",
      query: "",
      sortKey: "total_hours",
      sortDirection: "desc",
      team: [],
      player: [],
      deck: [],
      timelines: [],
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
      deckSearchQuery: "",
      expandedLinkedDeckKeys: new Set(),
      showDraftPanel: false,
      showNewDeckAdvanced: false,
      newDeckClassManual: false,
      saving: false,
      saveStatus: "",
      saveStatusKind: "",
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
        ["team", "Team"],
        ["stream_count", "Streams"],
        ["total_hours", "Total hours"],
        ["shadowverse_hours", "SV hours"],
        ["youtube_hours", "YouTube hours"],
        ["twitch_hours", "Twitch hours"]
      ],
      playerCompact: [
        ["team", "Team"],
        ["player_name", "Player"],
        ["timeline", "Timeline"],
        ["stream_count", "Streams"],
        ["total_hours", "Total hours"],
        ["shadowverse_hours", "SV hours"]
      ],
      playerDetail: [
        ["team", "Team"],
        ["player_name", "Player"],
        ["timeline", "Timeline"],
        ["stream_count", "Streams"],
        ["total_hours", "Total hours"],
        ["shadowverse_hours", "SV hours"],
        ["youtube_hours", "YouTube hours"],
        ["twitch_hours", "Twitch hours"],
        ["youtube_channel_status", "YouTube"],
        ["twitch_channel_status", "Twitch"],
        ["youtube_skipped_reason", "YouTube reason"],
        ["twitch_skipped_reason", "Twitch reason"]
      ],
      deck: [
        ["deck_name", "Deck"],
        ["class_name", "Class"],
        ["archetype", "Archetype"],
        ["deck_usage", "Usage"],
        ["stream_count", "Streams"],
        ["player_count", "Players"]
      ]
    };

    function activeColumns() {
      if (state.view === "player") {
        return state.showPlayerDetails ? columns.playerDetail : columns.playerCompact;
      }
      return columns[state.view];
    }

    function formatNumber(value) {
      return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value ?? 0);
    }

    function formatDate(value) {
      if (!value) return "Unknown";
      return new Intl.DateTimeFormat("ja-JP", {
        dateStyle: "medium",
        timeStyle: "short"
      }).format(new Date(value));
    }

    function statusLabel(value) {
      return String(value || "unknown").replaceAll("_", " ");
    }

    function playerKey(row) {
      return JSON.stringify([row.team, row.player_name]);
    }

    function streamKey(stream) {
      return JSON.stringify([stream.platform || "", stream.external_stream_id || ""]);
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
          <span>${escapeHtml(row.player_name || "Unknown player")}</span>
        </span>
      `;
    }

    function streamThumbnailHtml(stream) {
      if (!stream.thumbnail_url) {
        return `<div class="timeline-thumbnail missing" aria-hidden="true">No thumbnail</div>`;
      }
      return `
        <a class="timeline-thumbnail" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer" aria-label="${escapeHtml(stream.title || "Open archive")}">
          <img src="${escapeHtml(stream.thumbnail_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.closest('.timeline-thumbnail').classList.add('missing'); this.closest('.timeline-thumbnail').textContent='No thumbnail';">
        </a>
      `;
    }

    function formatDuration(totalSeconds) {
      const seconds = Math.max(Number(totalSeconds || 0), 0);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      if (hours > 0) {
        return `${hours}h ${String(minutes).padStart(2, "0")}m`;
      }
      return `${minutes}m`;
    }

    function platformLabel(value) {
      if (value === "youtube") return "YouTube";
      if (value === "twitch") return "Twitch";
      return statusLabel(value);
    }

    function deckLabel(deck) {
      const parts = [deck.class_name, deck.archetype].filter(Boolean).join(" / ");
      return parts ? `${deck.deck_name} (${parts})` : deck.deck_name;
    }

    function deckPillHtml(deck) {
      const label = escapeHtml(deckLabel(deck));
      if (deck.deck_url) {
        return `<a class="pill deck" href="${escapeHtml(deck.deck_url)}" target="_blank" rel="noreferrer">${label}</a>`;
      }
      return `<span class="pill deck">${label}</span>`;
    }

    const classAliases = [
      ["Nm", ["Nm", "NM", "ナイトメア", "NIGHTMARE"]],
      ["Nc", ["Nc", "NC", "ネクロ", "ネクロマンサー", "NECRO", "NECROMANCER"]],
      ["R", ["R", "ロイヤル", "ROYAL"]],
      ["E", ["E", "エルフ", "ELF"]],
      ["W", ["W", "ウィッチ", "WITCH"]],
      ["D", ["D", "ドラゴン", "DRAGON"]],
      ["B", ["B", "ビショップ", "BISHOP"]],
      ["V", ["V", "ヴァンプ", "ヴァンパイア", "VAMPIRE"]]
    ];

    function inferClassName(deckName) {
      const name = normalizeText(deckName);
      if (!name) return "";
      const upperName = name.toUpperCase();
      for (const [className, aliases] of classAliases) {
        for (const alias of aliases) {
          const normalizedAlias = alias.toUpperCase();
          if (upperName.endsWith(normalizedAlias)) {
            return className;
          }
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
          const keyValue = streamKey(stream);
          state.streamsByKey.set(keyValue, stream);
          (stream.decks || []).forEach(deck => {
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

      state.originalDecksByKey = new Map(Array.from(state.decksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.originalLinksByKey = new Map(Array.from(state.linksByKey, ([key, value]) => [key, cloneJson(value)]));
      materializeDerivedData();
    }

    function linksForStream(streamKeyValue) {
      return Array.from(state.linksByKey.values())
        .filter(link => link.stream_key === streamKeyValue)
        .sort((a, b) => a.display_order - b.display_order || deckLabel(state.decksByKey.get(a.deck_key) || a).localeCompare(deckLabel(state.decksByKey.get(b.deck_key) || b), "ja"));
    }

    function materializeDerivedData() {
      state.timelines.forEach(timeline => {
        (timeline.streams || []).forEach(stream => {
          const keyValue = streamKey(stream);
          stream.decks = linksForStream(keyValue).map(link => ({
            ...state.decksByKey.get(link.deck_key),
            confidence: link.confidence,
            source_note: link.source_note,
            display_order: link.display_order
          }));
        });
      });

      const rows = Array.from(state.decksByKey.values()).map(deck => {
        const streams = Array.from(state.linksByKey.values())
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
          .filter(Boolean)
          .sort((a, b) => String(b.occurred_at || "").localeCompare(String(a.occurred_at || "")));
        const players = Array.from(new Set(streams.map(stream => stream.player_name).filter(Boolean))).sort();
        return {
          ...deck,
          stream_count: streams.length,
          player_count: players.length,
          players,
          streams
        };
      }).sort((a, b) => b.stream_count - a.stream_count || deckLabel(a).localeCompare(deckLabel(b), "ja"));

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
      return `${prefix}: ${deckLabel(deck)} -> ${describeStream(stream) || "Unknown archive"}`;
    }

    function renderDraftState() {
      const changes = pendingChanges();
      const count = changeCount(changes);
      const bar = document.getElementById("change-bar");
      const panel = document.getElementById("draft-panel");
      const list = document.getElementById("draft-list");
      document.getElementById("change-summary").textContent = count === 0
        ? "No unsaved changes."
        : `${count} unsaved draft change${count === 1 ? "" : "s"}. Changes are not persisted yet.`;
      bar.hidden = count === 0;
      panel.hidden = count === 0 || !state.showDraftPanel;
      if (count === 0) {
        list.innerHTML = "";
        return;
      }

      const items = [
        ...changes.addedDecks.map(deck => `New deck: ${deckLabel(deck)}`),
        ...changes.addedLinks.map(link => changeDescription("Linked", link)),
        ...changes.removedLinks.map(link => changeDescription("Unlinked", link)),
        ...changes.updatedLinks.map(link => changeDescription("Updated link", link))
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
        if (!deck.deck_key) errors.push("Deck key is required.");
        if (!deck.deck_name) errors.push(`Deck name is required for ${deck.deck_key || "a deck"}.`);
        if (deckKeys.has(deck.deck_key)) errors.push(`Duplicate deck key: ${deck.deck_key}`);
        deckKeys.add(deck.deck_key);
      });

      const linkKeys = new Set();
      state.linksByKey.forEach(link => {
        const stream = state.streamsByKey.get(link.stream_key);
        if (!deckKeys.has(link.deck_key)) errors.push(`Linked deck is missing: ${link.deck_key}`);
        if (!stream) {
          errors.push(`Linked stream is missing for ${link.deck_key}.`);
          return;
        }
        if (!["youtube", "twitch"].includes(stream.platform)) errors.push(`Invalid platform: ${stream.platform || "empty"}`);
        if (!stream.external_stream_id) errors.push(`External stream id is required for ${stream.title || "a stream"}.`);
        const keyValue = `${stream.platform}/${stream.external_stream_id}/${link.deck_key}`;
        if (linkKeys.has(keyValue)) errors.push(`Duplicate stream deck link: ${keyValue}`);
        linkKeys.add(keyValue);
      });
      return Array.from(new Set(errors));
    }

    function utf8ToBase64(value) {
      const bytes = new TextEncoder().encode(value);
      let binary = "";
      bytes.forEach(byte => {
        binary += String.fromCharCode(byte);
      });
      return btoa(binary);
    }

    function setSaveStatus(message, kind = "") {
      state.saveStatus = message;
      state.saveStatusKind = kind;
      const status = document.getElementById("save-status");
      status.textContent = message;
      status.className = kind ? `save-status ${kind}` : "save-status";
    }

    function openSaveModal() {
      const changes = pendingChanges();
      document.getElementById("save-modal-summary").textContent = `${changeCount(changes)} pending changes will update data/decks.csv and data/stream_session_decks.csv.`;
      document.getElementById("save-repository").value = state.metadata.repository || "";
      document.getElementById("save-branch").value = state.metadata.branch_name || "";
      document.getElementById("save-token").value = "";
      setSaveStatus(state.metadata.repository && state.metadata.branch_name
        ? "Token is used only for this save and is not stored."
        : "Repository or branch metadata is missing. Fill both fields before saving.");
      document.getElementById("save-modal").hidden = false;
    }

    function closeSaveModal() {
      if (state.saving) return;
      document.getElementById("save-modal").hidden = true;
    }

    async function githubJson(url, options = {}) {
      const response = await fetch(url, {
        ...options,
        headers: {
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          ...(options.headers || {})
        }
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = payload.message || `GitHub API request failed with status ${response.status}.`;
        throw new Error(message);
      }
      return payload;
    }

    async function updateGitHubFile({ repo, branch, token, path, content, message }) {
      const encodedPath = path.split("/").map(encodeURIComponent).join("/");
      const url = `https://api.github.com/repos/${repo}/contents/${encodedPath}`;
      const current = await githubJson(`${url}?ref=${encodeURIComponent(branch)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      await githubJson(url, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message,
          content: utf8ToBase64(content),
          sha: current.sha,
          branch
        })
      });
    }

    function markDraftSaved() {
      state.originalDecksByKey = new Map(Array.from(state.decksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.originalLinksByKey = new Map(Array.from(state.linksByKey, ([key, value]) => [key, cloneJson(value)]));
      state.showDraftPanel = false;
      render();
    }

    async function saveChangesToGitHub() {
      if (state.saving) return;
      const repo = normalizeText(document.getElementById("save-repository").value);
      const branch = normalizeText(document.getElementById("save-branch").value);
      const token = normalizeText(document.getElementById("save-token").value);
      const errors = validateSavePayload();
      if (!repo || !repo.includes("/")) errors.push("Repository must be owner/repo.");
      if (!branch) errors.push("Branch is required.");
      if (!token) errors.push("GitHub token is required.");
      if (changeCount() === 0) errors.push("There are no draft changes to save.");
      if (errors.length > 0) {
        setSaveStatus(errors.join(" "), "error");
        return;
      }

      state.saving = true;
      document.getElementById("save-to-github").disabled = true;
      setSaveStatus("Saving data/decks.csv...", "");
      try {
        await updateGitHubFile({
          repo,
          branch,
          token,
          path: "data/decks.csv",
          content: serializeDecksCsv(),
          message: "Update deck definitions from dashboard"
        });
        setSaveStatus("Saving data/stream_session_decks.csv...", "");
        await updateGitHubFile({
          repo,
          branch,
          token,
          path: "data/stream_session_decks.csv",
          content: serializeStreamSessionDecksCsv(),
          message: "Update stream deck links from dashboard"
        });
        markDraftSaved();
        setSaveStatus("Saved. Run Collect streaming data for this branch to rebuild the dashboard.", "ok");
      } catch (error) {
        setSaveStatus(`Save failed: ${error.message}`, "error");
      } finally {
        state.saving = false;
        document.getElementById("save-to-github").disabled = false;
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
        return `<td class="action"><button class="detail-button${active}" type="button" data-player-key="${escapeHtml(keyValue)}">View</button></td>`;
      }
      if (key === "deck_usage") {
        const active = row.deck_key === state.selectedDeckKey ? " active" : "";
        return `<td class="action"><button class="detail-button deck-detail-button${active}" type="button" data-deck-key="${escapeHtml(row.deck_key)}">View</button></td>`;
      }
      if (key === "deck_name" && row.deck_url) {
        return `<td><a class="timeline-title" href="${escapeHtml(row.deck_url)}" target="_blank" rel="noreferrer">${escapeHtml(value)}</a></td>`;
      }
      if (key === "player_name") {
        return `<td>${playerLabelHtml(row)}</td>`;
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
      workspace.classList.toggle("player-mode", state.view === "player");
      workspace.classList.toggle("deck-mode", state.view === "deck");
      workspace.classList.toggle("team-mode", state.view === "team");
      tableWrap.classList.toggle("player-table-wrap", state.view === "player");
      tableWrap.classList.toggle("player-detail-table-wrap", state.view === "player" && state.showPlayerDetails);
      tableWrap.classList.toggle("deck-table-wrap", state.view === "deck");
      playerDetailsControl.hidden = state.view !== "player";
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
      document.getElementById("table-title").textContent = state.view === "team" ? "By team" : state.view === "player" ? "By player" : "By deck";
      document.getElementById("row-count").textContent = `${rows.length} rows`;
      document.getElementById("empty").hidden = rows.length > 0;

      document.getElementById("table-head").innerHTML = `<tr>${activeTableColumns.map(([key, label]) => {
        const sortClass = key === state.sortKey ? ` sorted-${state.sortDirection}` : "";
        return `<th class="sortable${sortClass}" data-key="${key}" scope="col">${label}</th>`;
      }).join("")}</tr>`;

      document.getElementById("table-body").innerHTML = rows.map(row => (
        `<tr>${activeTableColumns.map(([key]) => cellHtml(row, key)).join("")}</tr>`
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
        title.textContent = "Player timeline";
        summary.textContent = "";
        count.textContent = "0 streams";
        list.innerHTML = "";
        empty.hidden = false;
        return;
      }

      const streams = timeline.streams || [];
      title.innerHTML = `${playerLabelHtml(timeline, "heading")} <span>timeline</span>`;
      summary.textContent = timeline.team;
      count.textContent = `${streams.length} streams`;
      empty.hidden = streams.length > 0;
      list.innerHTML = streams.map(stream => {
        const timestamp = stream.occurred_at || stream.started_at || stream.published_at || "";
        const timestampKind = stream.started_at ? "Started" : stream.published_at ? "Published" : "Date unknown";
        const related = Number(stream.is_shadowverse_related || 0) === 1
          ? `<span class="pill related">Shadowverse</span>`
          : "";
        const deckTags = (stream.decks || []).map(deckPillHtml).join("");
        return `
          <article class="timeline-item">
            <div class="timeline-date">
              <strong>${escapeHtml(formatDate(timestamp))}</strong>
              <span>${escapeHtml(timestampKind)}</span>
            </div>
            ${streamThumbnailHtml(stream)}
            <div class="timeline-main">
              <a class="timeline-title" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer">${escapeHtml(stream.title || "Untitled stream")}</a>
              <div class="timeline-tags">
                <span class="pill ${escapeHtml(stream.platform || "")}">${escapeHtml(platformLabel(stream.platform))}</span>
                <span class="pill">${escapeHtml(formatDuration(stream.duration_sec))}</span>
                ${related}
                ${deckTags}
              </div>
            </div>
            <div class="stream-actions">
              <a class="timeline-link" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer">Open archive</a>
              <button class="secondary-button edit-stream-button" type="button" data-stream-key="${escapeHtml(streamKey(stream))}">Edit decks</button>
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
        title.textContent = "Deck usage";
        summary.textContent = "";
        count.textContent = "0 streams";
        list.innerHTML = "";
        empty.textContent = "No deck selected.";
        empty.hidden = false;
        return;
      }

      const streams = deck.streams || [];
      title.textContent = `${deck.deck_name} archives`;
      summary.textContent = [deck.class_name, deck.archetype, deck.notes].filter(Boolean).join(" · ");
      count.textContent = `${streams.length} streams`;
      empty.textContent = "No stream archives linked.";
      empty.hidden = streams.length > 0;
      list.innerHTML = streams.map(stream => {
        const timestamp = stream.occurred_at || stream.started_at || stream.published_at || "";
        const timestampKind = stream.started_at ? "Started" : stream.published_at ? "Published" : "Date unknown";
        const related = Number(stream.is_shadowverse_related || 0) === 1
          ? `<span class="pill related">Shadowverse</span>`
          : "";
        const note = stream.source_note
          ? `<div class="timeline-note">${escapeHtml(stream.source_note)}</div>`
          : "";
        const confidence = stream.confidence
          ? `<span class="pill">${escapeHtml(stream.confidence)}</span>`
          : "";
        return `
          <article class="timeline-item">
            <div class="timeline-date">
              <strong>${escapeHtml(formatDate(timestamp))}</strong>
              <span>${escapeHtml(timestampKind)}</span>
            </div>
            ${streamThumbnailHtml(stream)}
            <div class="timeline-main">
              <a class="timeline-title" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer">${escapeHtml(stream.title || "Untitled stream")}</a>
              <div class="timeline-meta">${escapeHtml(stream.team || "")} / ${escapeHtml(stream.player_name || "Unknown player")}</div>
              <div class="timeline-tags">
                <span class="pill ${escapeHtml(stream.platform || "")}">${escapeHtml(platformLabel(stream.platform))}</span>
                <span class="pill">${escapeHtml(formatDuration(stream.duration_sec))}</span>
                ${related}
                ${confidence}
              </div>
              ${note}
            </div>
            <div class="stream-actions">
              <a class="timeline-link" href="${escapeHtml(stream.url)}" target="_blank" rel="noreferrer">Open archive</a>
              <button class="secondary-button edit-stream-button" type="button" data-stream-key="${escapeHtml(streamKey(stream))}">Edit decks</button>
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
      state.deckSearchQuery = "";
      renderDeckEditor();
      document.getElementById("deck-editor-modal").hidden = false;
    }

    function closeDeckEditor() {
      state.editingStreamKey = "";
      document.getElementById("deck-editor-modal").hidden = true;
    }

    function renderDeckEditor() {
      const stream = state.streamsByKey.get(state.editingStreamKey);
      if (!stream) {
        closeDeckEditor();
        return;
      }

      document.getElementById("deck-editor-title").textContent = "Edit archive decks";
      document.getElementById("deck-editor-summary").textContent = describeStream(stream);
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
      const className = state.newDeckDraft.class_name || inferredClass;
      document.getElementById("new-deck-class-hint").textContent = state.newDeckDraft.deck_name
        ? `Class guess: ${className || "unknown"}`
        : "Class guess appears after entering a deck name.";
      document.querySelectorAll(".advanced-deck-field").forEach(field => {
        field.hidden = !state.showNewDeckAdvanced;
      });
      document.getElementById("toggle-new-deck-advanced").setAttribute("aria-expanded", String(state.showNewDeckAdvanced));
      document.getElementById("toggle-new-deck-advanced").textContent = state.showNewDeckAdvanced
        ? "Hide advanced input"
        : "Advanced input";
    }

    function renderLinkedDecks() {
      const container = document.getElementById("linked-decks");
      const links = linksForStream(state.editingStreamKey);
      if (links.length === 0) {
        container.innerHTML = `<div class="empty">No linked decks.</div>`;
        return;
      }

      container.innerHTML = links.map(link => {
        const deck = state.decksByKey.get(link.deck_key) || { deck_name: link.deck_key };
        const keyValue = linkKey(link.stream_key, link.deck_key);
        const expanded = state.expandedLinkedDeckKeys.has(keyValue);
        const detailForm = expanded ? `
          <div class="form-grid">
            <label class="field">Confidence
              <select class="link-field" data-link-key="${escapeHtml(keyValue)}" data-field="confidence">
                ${["", "low", "medium", "high"].map(value => `<option value="${escapeHtml(value)}"${value === link.confidence ? " selected" : ""}>${escapeHtml(value || "unset")}</option>`).join("")}
              </select>
            </label>
            <label class="field">Display order
              <input class="link-field" data-link-key="${escapeHtml(keyValue)}" data-field="display_order" type="number" min="0" step="1" value="${escapeHtml(link.display_order)}">
            </label>
            <label class="field full">Note
              <textarea class="link-field" data-link-key="${escapeHtml(keyValue)}" data-field="source_note">${escapeHtml(link.source_note)}</textarea>
            </label>
          </div>
        ` : "";
        return `
          <article class="linked-deck">
            <div class="linked-deck-head">
              <div class="deck-heading">
                <strong>${escapeHtml(deck.deck_name || link.deck_key)}</strong>
                <span>${escapeHtml([deck.class_name, deck.archetype].filter(Boolean).join(" / ") || link.deck_key)}</span>
              </div>
              <div class="linked-deck-actions">
                <button class="secondary-button toggle-link-details" type="button" data-link-key="${escapeHtml(keyValue)}">${expanded ? "Hide details" : "Details"}</button>
                <button class="danger-button unlink-deck" type="button" data-link-key="${escapeHtml(keyValue)}">Unlink</button>
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
        container.innerHTML = `<div class="empty">No existing decks found.</div>`;
        return;
      }

      container.innerHTML = decks.map(deck => {
        const alreadyLinked = linked.has(deck.deck_key);
        return `
          <div class="search-result">
            <div class="deck-heading">
              <strong>${escapeHtml(deck.deck_name)}</strong>
              <span>${escapeHtml([deck.class_name, deck.archetype].filter(Boolean).join(" / ") || deck.deck_key)}</span>
            </div>
            <button class="secondary-button add-existing-deck" type="button" data-deck-key="${escapeHtml(deck.deck_key)}"${alreadyLinked ? " disabled" : ""}>${alreadyLinked ? "Linked" : "Add"}</button>
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
      if (!draft.class_name) {
        draft.class_name = inferClassName(draft.deck_name);
      }
      if (!draft.deck_key && draft.deck_name) {
        draft.deck_key = generatedDeckKey(draft.deck_name);
      }
      if (!draft.deck_key || !draft.deck_name) {
        window.alert("Deck name is required.");
        return;
      }
      if (state.decksByKey.has(draft.deck_key)) {
        window.alert("Deck key already exists.");
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
      document.getElementById("metadata").textContent = `Updated ${formatDate(meta.generated_at)}${meta.run_number ? ` · Run #${meta.run_number}` : ""}`;
      document.getElementById("team-count").textContent = formatNumber(meta.team_count);
      document.getElementById("player-count").textContent = formatNumber(meta.player_count);
      document.getElementById("stream-count").textContent = formatNumber(meta.total_streams);
      document.getElementById("total-hours").textContent = formatNumber(meta.total_hours);
      document.getElementById("sv-hours").textContent = formatNumber(meta.shadowverse_hours);
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
    document.querySelectorAll(".open-save-modal-button").forEach(button => {
      button.addEventListener("click", openSaveModal);
    });
    document.getElementById("close-save-modal").addEventListener("click", closeSaveModal);
    document.getElementById("save-to-github").addEventListener("click", saveChangesToGitHub);
    document.getElementById("close-deck-editor").addEventListener("click", closeDeckEditor);

    document.getElementById("save-modal").addEventListener("click", event => {
      if (event.target.id === "save-modal") {
        closeSaveModal();
      }
    });

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
      document.getElementById("metadata").textContent = "Failed to load report data.";
      document.getElementById("empty").hidden = false;
      document.getElementById("empty").textContent = error.message;
    });
  </script>
</body>
</html>
"""


def write_html(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HTML, encoding="utf-8")


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

    write_html(args.out_dir / "index.html")
    write_json(args.out_dir / "data" / "streaming_by_player.json", player_rows)
    write_json(args.out_dir / "data" / "streaming_by_team.json", team_rows)
    write_json(args.out_dir / "data" / "streaming_timeline_by_player.json", timelines)
    write_json(args.out_dir / "data" / "streaming_deck_usage.json", deck_usage)
    write_json(args.out_dir / "data" / "metadata.json", metadata)

    print(f"wrote {args.out_dir / 'index.html'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_by_player.json'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_by_team.json'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_timeline_by_player.json'}")
    print(f"wrote {args.out_dir / 'data' / 'streaming_deck_usage.json'}")
    print(f"wrote {args.out_dir / 'data' / 'metadata.json'}")


if __name__ == "__main__":
    main()
