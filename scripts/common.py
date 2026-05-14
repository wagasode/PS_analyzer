from __future__ import annotations

import csv
from difflib import SequenceMatcher
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
SIMULCAST_START_TOLERANCE_SECONDS = 10 * 60
SIMULCAST_DURATION_TOLERANCE_SECONDS = 20 * 60


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
    ensure_column(conn, "channels", "image_url", "TEXT NOT NULL DEFAULT ''")


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_def: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


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


def _youtube_video_id(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value

    host = parsed.netloc.lower()
    path_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if host.endswith("youtu.be") and path_parts:
        return path_parts[0]
    if "youtube.com" not in host:
        return value

    query = urllib.parse.parse_qs(parsed.query)
    if query.get("v"):
        return query["v"][0]
    if len(path_parts) >= 2 and path_parts[0] in {"live", "embed", "shorts"}:
        return path_parts[1]
    return value


def youtube_archive_url(video_id_or_url: str) -> str:
    video_id = _youtube_video_id(video_id_or_url)
    if not video_id:
        return ""
    return f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id, safe='-_')}"


def twitch_archive_url(video_id: str, url: str = "") -> str:
    parsed = urllib.parse.urlparse(url.strip())
    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme and parsed.netloc and len(path_parts) >= 2 and path_parts[0] == "videos":
        return f"https://www.twitch.tv/videos/{urllib.parse.quote(path_parts[1], safe='')}"
    video_id = video_id.strip()
    if not video_id:
        return url.strip()
    return f"https://www.twitch.tv/videos/{urllib.parse.quote(video_id, safe='')}"


def parse_stream_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def stream_timestamp(stream: dict[str, Any]) -> datetime | None:
    for field in ("occurred_at", "started_at", "published_at"):
        parsed = parse_stream_timestamp(stream.get(field))
        if parsed is not None:
            return parsed
    return None


def normalized_stream_title(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _same_stream_owner(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in ("player_id", "player_name"):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value and right_value and left_value != right_value:
            return False
    return True


def _titles_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = normalized_stream_title(left.get("title"))
    right_title = normalized_stream_title(right.get("title"))
    if not left_title or not right_title:
        return True
    if left_title == right_title:
        return True
    return SequenceMatcher(None, left_title, right_title).ratio() >= 0.62


def streams_are_simulcast(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if {left.get("platform"), right.get("platform")} != {"youtube", "twitch"}:
        return False
    if not _same_stream_owner(left, right):
        return False

    left_time = stream_timestamp(left)
    right_time = stream_timestamp(right)
    if left_time is None or right_time is None:
        return False
    started_delta = abs((left_time - right_time).total_seconds())
    if started_delta > SIMULCAST_START_TOLERANCE_SECONDS:
        return False

    left_duration = int(left.get("duration_sec") or 0)
    right_duration = int(right.get("duration_sec") or 0)
    if left_duration > 0 and right_duration > 0:
        duration_delta = abs(left_duration - right_duration)
        if duration_delta > SIMULCAST_DURATION_TOLERANCE_SECONDS:
            return False

    return _titles_compatible(left, right)


def dedupe_simulcast_groups(streams: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for stream in streams:
        matched = False
        for group in groups:
            if len(group) >= 2:
                continue
            if any(streams_are_simulcast(stream, existing) for existing in group):
                group.append(stream)
                matched = True
                break
        if not matched:
            groups.append([stream])
    return groups


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
