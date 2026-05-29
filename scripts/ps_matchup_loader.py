from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FALLBACK_WIN_RATE = 0.5
FALLBACK_NOTE = "相性表未定義のため0.5"


@dataclass(frozen=True)
class MatchupEntry:
    source_deck_id: str
    target_deck_id: str
    win_rate: float
    source: str
    source_cell: str = ""
    perspective: str = "rowDeck"
    note: str = ""


@dataclass
class MatchupIndex:
    source: str
    entries: dict[tuple[str, str], MatchupEntry] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def deck_id_lookup(decks: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for deck in decks:
        deck_id = str(deck.get("deckId") or "").strip()
        if not deck_id:
            continue
        for value in [deck_id, deck.get("deckName"), deck.get("sourceDeckKey")]:
            key = str(value or "").strip()
            if key:
                lookup[key] = deck_id
    return lookup


def resolve_deck_id(value: Any, lookup: dict[str, str]) -> str | None:
    key = str(value or "").strip()
    if not key:
        return None
    return lookup.get(key)


def normalize_win_rate(raw_value: Any) -> tuple[float | None, str | None, bool]:
    if raw_value is None:
        return None, None, True
    if isinstance(raw_value, str) and raw_value.strip() == "":
        return None, None, True

    try:
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if text.endswith("%"):
                value = float(text[:-1].strip()) / 100
            else:
                value = float(text)
                if 1 < value <= 100:
                    value = value / 100
        else:
            value = float(raw_value)
            if 1 < value <= 100:
                value = value / 100
    except (TypeError, ValueError):
        return None, f"winRateを数値として読めません: {raw_value}", False

    if value < 0 or value > 1:
        return None, f"winRateが範囲外です: {raw_value}", False
    return value, None, False


def _add_entry(
    index: MatchupIndex,
    *,
    source_deck_id: str | None,
    target_deck_id: str | None,
    raw_win_rate: Any,
    source: str,
    source_cell: str = "",
    perspective: str = "rowDeck",
    note: str = "",
) -> None:
    if not source_deck_id:
        index.warnings.append("行デッキをdeckIdへ解決できないためmatchupを採用しません。")
        return
    if not target_deck_id:
        index.warnings.append(f"列デッキをdeckIdへ解決できないためmatchupを採用しません: {source_deck_id}")
        return

    win_rate, warning, missing = normalize_win_rate(raw_win_rate)
    if missing:
        return
    if warning:
        index.warnings.append(f"{source_deck_id} vs {target_deck_id}: {warning}")
        return
    assert win_rate is not None

    key = (source_deck_id, target_deck_id)
    if key in index.entries:
        index.warnings.append(f"重複matchupを検出しました: {source_deck_id} vs {target_deck_id}")
        return

    if source_deck_id == target_deck_id and win_rate != FALLBACK_WIN_RATE:
        index.warnings.append(
            f"自己対面は0.5が原則です: {source_deck_id} = {win_rate}"
        )

    index.entries[key] = MatchupEntry(
        source_deck_id=source_deck_id,
        target_deck_id=target_deck_id,
        win_rate=win_rate,
        source=source,
        source_cell=source_cell,
        perspective=perspective,
        note=note,
    )


def build_matchup_index(dataset: dict[str, Any]) -> MatchupIndex:
    decks = dataset.get("decks", [])
    lookup = deck_id_lookup(decks)
    fixture = dataset.get("matchupFixture") or {}
    source = str(fixture.get("source") or "repo-local fixture")
    index = MatchupIndex(source=source)

    matrix = fixture.get("matrix") or {}
    source_cells_by_row = matrix.get("sourceCells") or {}
    for row in matrix.get("rows", []):
        source_deck_id = resolve_deck_id(
            row.get("sourceDeckId") or row.get("deckId") or row.get("sourceDeckName") or row.get("deckName"),
            lookup,
        )
        if not source_deck_id:
            index.warnings.append(
                f"行デッキをdeckIdへ解決できません: {row.get('deckName') or row.get('sourceDeckName') or row.get('deckId')}"
            )
            continue
        row_source_cells = row.get("sourceCells") or source_cells_by_row.get(source_deck_id) or {}
        for target_ref, raw_win_rate in (row.get("values") or {}).items():
            target_deck_id = resolve_deck_id(target_ref, lookup)
            if not target_deck_id:
                index.warnings.append(f"列デッキをdeckIdへ解決できません: {target_ref}")
                continue
            _add_entry(
                index,
                source_deck_id=source_deck_id,
                target_deck_id=target_deck_id,
                raw_win_rate=raw_win_rate,
                source=source,
                source_cell=str(row_source_cells.get(target_ref) or row_source_cells.get(target_deck_id) or ""),
                perspective=str(fixture.get("perspective") or "rowDeck"),
                note=str(row.get("note") or ""),
            )

    for matchup in fixture.get("matchups", []):
        source_deck_id = resolve_deck_id(
            matchup.get("sourceDeckId") or matchup.get("deckIdA") or matchup.get("sourceDeckName"),
            lookup,
        )
        target_deck_id = resolve_deck_id(
            matchup.get("targetDeckId") or matchup.get("deckIdB") or matchup.get("targetDeckName"),
            lookup,
        )
        _add_entry(
            index,
            source_deck_id=source_deck_id,
            target_deck_id=target_deck_id,
            raw_win_rate=matchup.get("winRate", matchup.get("winRateForA")),
            source=source,
            source_cell=str(matchup.get("sourceCell") or ""),
            perspective=str(matchup.get("perspective") or fixture.get("perspective") or "rowDeck"),
            note=str(matchup.get("note") or ""),
        )

    return index


def get_win_rate(index: MatchupIndex, self_deck_id: str, opponent_deck_id: str) -> dict[str, Any]:
    entry = index.entries.get((self_deck_id, opponent_deck_id))
    if entry:
        return {
            "winRate": entry.win_rate,
            "selfWinRate": entry.win_rate,
            "winRateSource": {
                "type": "matchup",
                "selfDeckId": self_deck_id,
                "opponentDeckId": opponent_deck_id,
                "source": entry.source,
                "sourceCell": entry.source_cell,
                "perspective": entry.perspective,
            },
            "winRateNote": "相性表fixtureの行デッキ視点を使用しています。",
            "warnings": [],
            "isFallback": False,
        }

    warning = f"matchup not found: {self_deck_id} vs {opponent_deck_id}"
    return {
        "winRate": FALLBACK_WIN_RATE,
        "selfWinRate": FALLBACK_WIN_RATE,
        "winRateSource": {
            "type": "fallback",
            "selfDeckId": self_deck_id,
            "opponentDeckId": opponent_deck_id,
            "source": index.source,
            "fallbackValue": FALLBACK_WIN_RATE,
        },
        "winRateNote": FALLBACK_NOTE,
        "warnings": [warning],
        "isFallback": True,
    }
