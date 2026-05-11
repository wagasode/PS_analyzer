from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "streams.sqlite"
DEFAULT_PLAYERS_CSV = ROOT_DIR / "data" / "players_channels.csv"
SCHEMA_PATH = ROOT_DIR / "sql" / "schema.sql"

NO_CHANNEL = "チャンネル非所持"
SHADOWVERSE_TERMS = (
    "shadowverse",
    "シャドウバース",
    "シャドバ",
    "worlds beyond",
    "ワールズビヨンド",
    "svwb",
    "シャドバwb",
)


class ApiError(RuntimeError):
    def __init__(self, status_code: int, url: str, body: str):
        self.status_code = status_code
        self.url = url
        self.body = body
        try:
            self.payload = json.loads(body)
        except json.JSONDecodeError:
            self.payload = None
        super().__init__(f"HTTP {status_code} for {url}: {body}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def read_players_csv(path: Path = DEFAULT_PLAYERS_CSV) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def is_real_channel(value: str | None) -> bool:
    value = (value or "").strip()
    return bool(value and value != NO_CHANNEL)


def http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    req_headers = headers or {}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req_headers = {"Content-Type": "application/x-www-form-urlencoded", **req_headers}
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, url, detail) from exc


def youtube_api(path: str, params: dict[str, Any], api_key: str) -> dict[str, Any]:
    params = {**params, "key": api_key}
    query = urllib.parse.urlencode(params)
    return http_json(f"https://www.googleapis.com/youtube/v3/{path}?{query}")


def parse_iso8601_duration(value: str | None) -> int:
    if not value:
        return 0
    match = re.fullmatch(r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?", value)
    if not match:
        return 0
    parts = {key: int(val or 0) for key, val in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def parse_twitch_duration(value: str | None) -> int:
    if not value:
        return 0
    total = 0
    for amount, unit in re.findall(r"(\d+)([hms])", value):
        n = int(amount)
        total += {"h": 3600, "m": 60, "s": 1}[unit] * n
    return total


def classify_shadowverse(title: str, description: str = "", game_or_category: str = "") -> tuple[int, str]:
    haystack = " ".join([title, description, game_or_category]).lower()
    matches = [term for term in SHADOWVERSE_TERMS if term.lower() in haystack]
    return (1, ",".join(matches)) if matches else (0, "")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"環境変数 {name} が未設定です。")
    return value


def create_run(conn: sqlite3.Connection, platform: str, script_name: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO collection_runs(platform, script_name, status)
        VALUES (?, ?, 'running')
        """,
        (platform, script_name),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    channels_checked: int = 0,
    items_seen: int = 0,
    items_upserted: int = 0,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE collection_runs
        SET ended_at = ?, status = ?, channels_checked = ?, items_seen = ?, items_upserted = ?, error_message = ?
        WHERE collection_run_id = ?
        """,
        (utc_now(), status, channels_checked, items_seen, items_upserted, error_message, run_id),
    )
    conn.commit()
