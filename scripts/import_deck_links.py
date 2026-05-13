from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from common import DEFAULT_DB_PATH, ROOT_DIR, connect, init_schema


DEFAULT_DECKS_CSV = ROOT_DIR / "data" / "decks.csv"
DEFAULT_STREAM_SESSION_DECKS_CSV = ROOT_DIR / "data" / "stream_session_decks.csv"


def read_csv(path: Path, required_fields: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = required_fields - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"{path} is missing required fields: {', '.join(sorted(missing))}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def parse_int(value: str, *, default: int = 0) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def import_deck_links(conn: sqlite3.Connection, decks_csv: Path, links_csv: Path) -> tuple[int, int, int, int]:
    deck_rows = read_csv(decks_csv, {"deck_key", "deck_name"})
    link_rows = read_csv(links_csv, {"platform", "external_stream_id", "deck_key"})

    conn.execute("DELETE FROM stream_session_decks")
    conn.execute("DELETE FROM decks")

    deck_count = 0
    for row in deck_rows:
        deck_key = row.get("deck_key", "")
        if not deck_key:
            continue
        deck_name = row.get("deck_name", "") or deck_key
        conn.execute(
            """
            INSERT INTO decks(deck_key, deck_name, class_name, archetype, deck_url, deck_code, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(deck_key) DO UPDATE SET
                deck_name = excluded.deck_name,
                class_name = excluded.class_name,
                archetype = excluded.archetype,
                deck_url = excluded.deck_url,
                deck_code = excluded.deck_code,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (
                deck_key,
                deck_name,
                row.get("class_name", ""),
                row.get("archetype", ""),
                row.get("deck_url", ""),
                row.get("deck_code", ""),
                row.get("notes", ""),
            ),
        )
        deck_count += 1

    linked_count = 0
    skipped_missing_deck = 0
    skipped_missing_stream = 0
    for row in link_rows:
        platform = row.get("platform", "")
        external_stream_id = row.get("external_stream_id", "")
        deck_key = row.get("deck_key", "")
        if not platform or not external_stream_id or not deck_key:
            continue

        deck = conn.execute("SELECT deck_id FROM decks WHERE deck_key = ?", (deck_key,)).fetchone()
        if deck is None:
            skipped_missing_deck += 1
            continue

        stream = conn.execute(
            """
            SELECT stream_session_id
            FROM stream_sessions
            WHERE platform = ? AND external_stream_id = ?
            """,
            (platform, external_stream_id),
        ).fetchone()
        if stream is None:
            skipped_missing_stream += 1
            continue

        conn.execute(
            """
            INSERT INTO stream_session_decks(
                stream_session_id, deck_id, confidence, source_note, display_order, updated_at
            )
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(stream_session_id, deck_id) DO UPDATE SET
                confidence = excluded.confidence,
                source_note = excluded.source_note,
                display_order = excluded.display_order,
                updated_at = datetime('now')
            """,
            (
                stream["stream_session_id"],
                deck["deck_id"],
                row.get("confidence", ""),
                row.get("source_note", ""),
                parse_int(row.get("display_order", "")),
            ),
        )
        linked_count += 1

    conn.commit()
    return deck_count, linked_count, skipped_missing_deck, skipped_missing_stream


def main() -> None:
    parser = argparse.ArgumentParser(description="Import deck definitions and stream archive deck links into SQLite.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--decks-csv", type=Path, default=DEFAULT_DECKS_CSV)
    parser.add_argument("--links-csv", type=Path, default=DEFAULT_STREAM_SESSION_DECKS_CSV)
    args = parser.parse_args()

    conn = connect(args.db)
    init_schema(conn)
    deck_count, linked_count, skipped_missing_deck, skipped_missing_stream = import_deck_links(
        conn,
        args.decks_csv,
        args.links_csv,
    )
    conn.close()

    print(f"imported decks={deck_count} stream_deck_links={linked_count}")
    if skipped_missing_deck:
        print(f"skipped links with missing deck={skipped_missing_deck}")
    if skipped_missing_stream:
        print(f"skipped links with missing stream archive={skipped_missing_stream}")


if __name__ == "__main__":
    main()
