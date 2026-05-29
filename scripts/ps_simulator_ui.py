from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
PS_SIMULATOR_SAMPLE_DATASET_PATH = ROOT_DIR / "data" / "ps_simulator" / "sample_dataset.json"
PS_SIMULATOR_PUBLIC_DATASET_PATH = Path("data") / "ps_simulator" / "sample_dataset.json"
HTML2CANVAS_VENDOR_PATH = ROOT_DIR / "scripts" / "vendor" / "html2canvas.min.js"
HTML2CANVAS_VENDOR_LICENSE_PATH = ROOT_DIR / "scripts" / "vendor" / "html2canvas.LICENSE.txt"
HTML2CANVAS_PUBLIC_PATH = Path("vendor") / "html2canvas.min.js"
HTML2CANVAS_PUBLIC_LICENSE_PATH = Path("vendor") / "html2canvas.LICENSE.txt"
ROUND_ROLE_BY_NUMBER = {1: "A", 2: "B", 3: "C"}
EXPECTED_ROUND_CANDIDATE_COUNTS = {1: 3, 2: 2, 3: 2, 4: 4, 5: 3}


def unique_deck_ids(deck_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for deck_id in deck_ids:
        if not deck_id or deck_id in seen:
            continue
        seen.add(deck_id)
        unique.append(deck_id)
    return unique


def submission_deck_ids(submission: dict[str, Any]) -> list[str]:
    deck_ids: list[str] = []
    for assignment in submission.get("assignments", []):
        deck_ids.extend(assignment.get("deckIds", []))
    return unique_deck_ids(deck_ids)


def battle_candidate_deck_ids_for_round(
    submission: dict[str, Any],
    round_number: int,
    used_deck_ids: set[str],
) -> list[str]:
    if round_number in ROUND_ROLE_BY_NUMBER:
        role = ROUND_ROLE_BY_NUMBER[round_number]
        for assignment in submission.get("assignments", []):
            if assignment.get("role") == role:
                return [
                    deck_id
                    for deck_id in unique_deck_ids(assignment.get("deckIds", []))
                    if deck_id not in used_deck_ids
                ]
        return []
    if round_number in {4, 5}:
        return [deck_id for deck_id in submission_deck_ids(submission) if deck_id not in used_deck_ids]
    raise ValueError(f"unsupported round_number: {round_number}")


def selected_deck_id_for_side(round_state: dict[str, Any], side: str) -> str:
    if side == "self":
        return str(round_state.get("selfSelectedDeckId") or "")
    if side == "opponent":
        return str(round_state.get("opponentSelectedDeckId") or "")
    raise ValueError(f"unsupported side: {side}")


def battle_used_deck_ids_for_side(
    rounds: list[dict[str, Any]],
    side: str,
    *,
    through_round_number: int | None = None,
) -> list[str]:
    deck_ids: list[str] = []
    for round_state in rounds:
        round_number = int(round_state.get("roundNumber") or 0)
        if through_round_number is not None and round_number > through_round_number:
            continue
        deck_id = selected_deck_id_for_side(round_state, side)
        if deck_id:
            deck_ids.append(deck_id)
    return unique_deck_ids(deck_ids)


def battle_remaining_deck_ids_for_side(
    submission: dict[str, Any],
    used_deck_ids: list[str] | set[str],
) -> list[str]:
    used = set(used_deck_ids)
    return [deck_id for deck_id in submission_deck_ids(submission) if deck_id not in used]


def reset_battle_rounds_from(
    rounds: list[dict[str, Any]],
    round_number: int,
) -> list[dict[str, Any]]:
    return [round_state for round_state in rounds if int(round_state.get("roundNumber") or 0) < round_number]


def validate_round_candidate_count(round_number: int, candidate_deck_ids: list[str]) -> list[str]:
    expected = EXPECTED_ROUND_CANDIDATE_COUNTS.get(round_number)
    if expected is None or len(candidate_deck_ids) == expected:
        return []
    return [f"R{round_number}候補は{expected}デッキ想定です。現在は{len(candidate_deck_ids)}デッキです。"]


PS_SIMULATOR_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PSルール戦略シミュレータ</title>
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
      width: min(1220px, calc(100% - 32px));
      margin: 0 auto;
    }

    .topbar,
    .toolbar,
    .panel-head,
    .control-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      flex-wrap: wrap;
    }

    .topbar {
      padding: 24px 0 18px;
      align-items: flex-start;
    }

    h1,
    h2,
    h3,
    h4 {
      margin: 0;
      line-height: 1.25;
      letter-spacing: 0;
    }

    h1 {
      font-size: 28px;
    }

    h2 {
      font-size: 18px;
    }

    h3 {
      font-size: 15px;
    }

    h4 {
      font-size: 14px;
    }

    .meta,
    .hint,
    .count {
      color: var(--muted);
      font-size: 14px;
    }

    .meta {
      margin-top: 8px;
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
      padding: 22px 0 42px;
    }

    a.button,
    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 12px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
      text-decoration: none;
      cursor: pointer;
      box-shadow: var(--shadow);
      white-space: nowrap;
    }

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.62;
      box-shadow: none;
    }

    .toolbar {
      margin-bottom: 18px;
    }

    .field {
      display: inline-grid;
      gap: 5px;
      min-width: 180px;
      color: var(--muted);
      font-size: 13px;
    }

    select {
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }

    input[type="text"] {
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr);
      gap: 16px;
      align-items: start;
    }

    .panel {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .panel-head {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
    }

    .panel-body {
      padding: 16px;
    }

    .stack {
      display: grid;
      gap: 16px;
    }

    .role-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    .role-panel {
      display: grid;
      gap: 12px;
      align-content: start;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      background: #f8fafc;
    }

    .role-panel.invalid {
      border-color: #fdba74;
      background: #fff7ed;
    }

    .role-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }

    .player-select-row {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }

    .player-select-row select {
      width: 100%;
      min-width: 0;
    }

    .player-avatar {
      position: relative;
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      width: 32px;
      height: 32px;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--none-soft);
      color: var(--none);
      font-size: 12px;
      font-weight: 700;
      line-height: 1;
    }

    .player-avatar img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      background: var(--panel);
    }

    .player-avatar.small {
      width: 22px;
      height: 22px;
      font-size: 10px;
    }

    .deck-options {
      display: grid;
      gap: 8px;
    }

    .deck-class-group {
      display: grid;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      background: #fff;
    }

    .deck-class-group.selected-class {
      border-color: var(--deck-class-border, var(--accent));
      background: var(--deck-class-row, #f8fafc);
    }

    .deck-class-group-head,
    .validation-section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }

    .deck-option {
      display: grid;
      gap: 6px;
      align-items: start;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 7px 8px;
      background: var(--panel);
    }

    .deck-option.selected {
      border-color: var(--deck-class-border, var(--accent));
      background: linear-gradient(90deg, var(--deck-class-border, var(--accent)) 0 5px, var(--deck-class-row, var(--accent-soft)) 5px);
    }

    .deck-option-pick {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      cursor: pointer;
    }

    .deck-option input {
      width: 16px;
      height: 16px;
      margin: 0;
      accent-color: var(--accent);
    }

    .deck-main {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 7px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .deck-name {
      display: flex;
      align-items: center;
      gap: 7px;
      flex-wrap: wrap;
      overflow-wrap: anywhere;
    }

    .class-code-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 24px;
      min-height: 22px;
      border: 1px solid var(--deck-class-border, var(--border));
      border-radius: 999px;
      padding: 0 7px;
      background: var(--deck-class-soft, var(--none-soft));
      color: var(--deck-class-color, var(--none));
      font-size: 12px;
      font-weight: 800;
      line-height: 1;
      white-space: nowrap;
    }

    .deck-note,
    .role-class-summary,
    .status-note,
    .source-note {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .badge-row,
    .class-coverage,
    .data-summary {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      align-items: center;
    }

    .role-selection-summary {
      display: grid;
      gap: 7px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px;
      background: #fff;
    }

    .role-selection-summary.invalid {
      border-color: #fdba74;
      background: #fff7ed;
    }

    .role-summary-head {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex-wrap: wrap;
    }

    .role-summary-head strong {
      overflow-wrap: anywhere;
    }

    .summary-deck-chips {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: center;
    }

    .summary-deck-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 26px;
      max-width: 100%;
      border: 1px solid var(--deck-class-border, var(--border));
      border-radius: 999px;
      padding: 0 8px 0 4px;
      background: var(--deck-class-soft, var(--none-soft));
      color: var(--deck-class-color, var(--none));
      font-size: 12px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .summary-deck-chip.empty {
      border-style: dashed;
      background: #f8fafc;
      color: var(--muted);
      font-weight: 600;
    }

    .summary-deck-chip-code {
      display: inline-grid;
      place-items: center;
      min-width: 22px;
      height: 22px;
      border-radius: 999px;
      background: var(--deck-class-color, var(--none));
      color: #fff;
      font-size: 11px;
      line-height: 1;
    }

    .class-coverage-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 26px;
      min-height: 26px;
      border: 2px solid var(--border);
      border-radius: 999px;
      padding: 0 7px;
      background: var(--deck-class-soft, var(--none-soft));
      color: var(--deck-class-color, var(--none));
      font-size: 12px;
      font-weight: 800;
      line-height: 1;
      white-space: nowrap;
    }

    .class-coverage-badge.selected {
      border-color: var(--deck-class-color, var(--none));
    }

    .class-coverage-badge.missing {
      border-color: var(--border);
      border-style: dashed;
    }

    .class-coverage-badge.duplicate {
      border-color: var(--bad);
      box-shadow: 0 0 0 2px var(--bad-soft);
    }

    .badge,
    .class-badge,
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 24px;
      border-radius: 999px;
      padding: 0 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .badge {
      background: var(--none-soft);
      color: var(--none);
    }

    .badge.ok {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .badge.warn,
    .status-badge.trainable,
    .status-badge.missing {
      background: var(--warn-soft);
      color: var(--warn);
    }

    .badge.bad,
    .status-badge.hard {
      background: var(--bad-soft);
      color: var(--bad);
    }

    .status-badge.confident {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .status-badge.available {
      background: #dbeafe;
      color: #1d4ed8;
    }

    .class-badge {
      border: 1px solid var(--deck-class-border, var(--border));
      background: var(--deck-class-soft, var(--none-soft));
      color: var(--deck-class-color, var(--none));
    }

    .class-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--deck-class-color, var(--none));
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

    .validation-list {
      display: grid;
      gap: 8px;
    }

    .battle-panel .panel-body {
      gap: 12px;
    }

    .battle-panel {
      margin-top: 16px;
    }

    .battle-submissions,
    .battle-status-grid,
    .battle-round-grid,
    .battle-side-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .battle-main-grid {
      display: grid;
      grid-template-columns: minmax(260px, 0.8fr) minmax(420px, 1.2fr) minmax(260px, 0.8fr);
      gap: 12px;
      align-items: start;
    }

    .battle-main-column {
      display: grid;
      gap: 12px;
      min-width: 0;
    }

    .battle-card,
    .battle-round,
    .battle-submission,
    .battle-list {
      display: grid;
      gap: 9px;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      background: #f8fafc;
    }

    .battle-submission {
      align-content: start;
    }

    .battle-assignment-list {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }

    .battle-assignment {
      display: grid;
      gap: 6px;
      align-items: start;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px;
      background: #fff;
      min-width: 0;
    }

    .battle-assignment-main {
      display: grid;
      gap: 5px;
      min-width: 0;
    }

    .battle-assignment-head {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .battle-card.ended {
      border-color: #99f6e4;
      background: var(--accent-soft);
    }

    .battle-card.blocked {
      border-color: #fdba74;
      background: var(--warn-soft);
    }

    .battle-controls {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .choice-list,
    .battle-progress {
      display: grid;
      gap: 8px;
    }

    .deck-token-list {
      display: grid;
      gap: 6px;
      min-width: 0;
    }

    .deck-token-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      min-width: 0;
    }

    .deck-token {
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 5px;
      max-width: 100%;
      min-width: 0;
      min-height: 24px;
      border: 1px solid var(--deck-class-border, var(--border));
      border-radius: 7px;
      padding: 2px 7px 2px 3px;
      background: var(--deck-class-soft, #fff);
      color: var(--deck-class-color, var(--text));
      font-size: 12px;
      line-height: 1.25;
      white-space: normal;
      overflow-wrap: anywhere;
    }

    .deck-token-name {
      color: var(--text);
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .deck-token-code {
      display: inline-grid;
      place-items: center;
      min-width: 20px;
      min-height: 18px;
      border-radius: 999px;
      background: var(--deck-class-color, var(--none));
      color: #fff;
      font-size: 11px;
      font-weight: 800;
      line-height: 1;
    }

    .deck-list-group {
      display: grid;
      gap: 6px;
    }

    .deck-list-group + .deck-list-group {
      padding-top: 8px;
      border-top: 1px solid var(--border);
    }

    .choice-button {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 8px;
      min-height: 0;
      width: 100%;
      padding: 8px 9px;
      border-color: var(--deck-class-border, var(--border));
      background: linear-gradient(90deg, var(--deck-class-border, var(--border)) 0 5px, #fff 5px);
      text-align: left;
      white-space: normal;
    }

    .choice-button.selected {
      border-color: var(--deck-class-color, var(--accent));
      background: linear-gradient(90deg, var(--deck-class-color, var(--accent)) 0 5px, var(--deck-class-row, var(--accent-soft)) 5px);
      color: var(--text);
      font-weight: 800;
      outline: 2px solid var(--deck-class-color, var(--accent));
      outline-offset: 1px;
      box-shadow: 0 0 0 3px var(--deck-class-soft, var(--accent-soft));
    }

    .choice-button:disabled {
      cursor: not-allowed;
      opacity: 0.62;
      box-shadow: none;
    }

    .progress-item {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px;
      background: #fff;
    }

    .progress-item.current {
      border-color: #99f6e4;
      background: var(--accent-soft);
    }

    .progress-item.done {
      border-color: #cbd5e1;
    }

    .progress-match {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 5px;
    }

    .progress-side {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .battle-result-badge {
      display: inline-flex;
      align-items: center;
      min-height: 20px;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 800;
      line-height: 1;
      white-space: nowrap;
    }

    .battle-result-badge.win {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .battle-result-badge.loss {
      background: var(--bad-soft);
      color: var(--bad);
    }

    .progress-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }

    .battle-summary-section {
      display: grid;
      gap: 10px;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
    }

    .battle-summary-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .battle-summary-export-status {
      min-height: 20px;
      text-align: right;
    }

    .battle-summary-export-status.ok {
      color: var(--accent);
      font-weight: 700;
    }

    .battle-summary-export-status.warn {
      color: var(--warn);
      font-weight: 700;
    }

    .battle-summary-export-status.error {
      color: var(--bad);
      font-weight: 700;
    }

    .battle-summary-card {
      display: grid;
      gap: 12px;
      min-width: 0;
    }

    .battle-summary-result,
    .summary-round-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f8fafc;
    }

    .battle-summary-result {
      display: grid;
      gap: 6px;
      padding: 12px;
      border-color: #99f6e4;
      background: var(--accent-soft);
    }

    .battle-summary-result.incomplete {
      border-color: #fdba74;
      background: var(--warn-soft);
    }

    .battle-summary-titleline {
      font-size: 24px;
      font-weight: 800;
      line-height: 1.15;
      overflow-wrap: anywhere;
    }

    .battle-summary-rounds {
      display: grid;
      grid-template-columns: repeat(3, minmax(130px, 0.8fr)) repeat(2, minmax(240px, 1.3fr));
      gap: 8px;
      min-width: 0;
    }

    .summary-round-card {
      display: grid;
      gap: 7px;
      align-content: start;
      padding: 9px;
      min-width: 0;
    }

    .summary-round-card.pending {
      border-style: dashed;
      color: var(--muted);
    }

    .summary-round-card.win {
      border-color: #99f6e4;
    }

    .summary-round-card.loss {
      border-color: #fecaca;
    }

    .summary-result-badge {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 800;
      line-height: 1.1;
      white-space: nowrap;
    }

    .summary-result-badge.self-win {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .summary-result-badge.opponent-win {
      background: var(--bad-soft);
      color: var(--bad);
    }

    .summary-result-badge.pending {
      background: var(--warn-soft);
      color: var(--warn);
    }

    .summary-round-head,
    .summary-side-line {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .summary-round-head {
      justify-content: space-between;
    }

    .summary-round-match {
      display: grid;
      gap: 5px;
      min-width: 0;
    }

    .summary-side-line {
      align-items: flex-start;
    }

    .summary-round-candidates {
      display: grid;
      gap: 6px;
      padding-top: 7px;
      border-top: 1px solid var(--border);
    }

    .summary-round-candidates h4 {
      margin: 0;
      font-size: 13px;
      line-height: 1.2;
    }

    .summary-candidate-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      min-width: 0;
    }

    .side-label {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .submission-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }

    .submission-actions-label {
      display: inline-flex;
      align-items: center;
      min-height: 36px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }

    .submission-actions button {
      min-width: 72px;
      padding: 0 11px;
    }

    .json-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 10px;
    }

    .scoreline {
      font-size: 20px;
      font-weight: 700;
    }

    .validation-section {
      display: grid;
      gap: 8px;
    }

    .validation-item {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      background: #f8fafc;
      color: var(--muted);
      font-size: 14px;
    }

    .validation-item.ok {
      border-color: #99f6e4;
      background: var(--accent-soft);
      color: var(--accent);
    }

    .validation-item.error {
      border-color: #fdba74;
      background: var(--warn-soft);
      color: var(--warn);
      font-weight: 700;
    }

    .validation-item.hard {
      border-color: #fecaca;
      background: var(--bad-soft);
      color: var(--bad);
      font-weight: 700;
    }

    .validation-item.warn {
      border-color: #fdba74;
      background: var(--warn-soft);
      color: var(--warn);
    }

    .empty {
      color: var(--muted);
      padding: 18px 0;
      text-align: center;
    }

    details {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f8fafc;
    }

    summary {
      cursor: pointer;
      padding: 12px;
      font-weight: 700;
    }

    details[open] summary {
      border-bottom: 1px solid var(--border);
    }

    .details-body {
      padding: 12px;
    }

    .deck-status-details {
      border: 0;
      border-radius: 0;
      background: transparent;
    }

    .deck-status-details summary {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      padding: 2px 0 0 24px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }

    .deck-status-details[open] summary {
      border-bottom: 0;
      padding-bottom: 6px;
    }

    .status-summary {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }

    .status-summary-label {
      color: var(--muted);
      font-weight: 600;
    }

    .status-mini {
      display: inline-flex;
      align-items: center;
      min-height: 20px;
      border-radius: 999px;
      padding: 0 7px;
      background: var(--none-soft);
      color: var(--none);
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }

    .status-mini.ok {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .status-mini.confident {
      background: var(--accent-soft);
      color: var(--accent);
    }

    .status-mini.available {
      background: #dbeafe;
      color: #1d4ed8;
    }

    .status-mini.warn {
      background: var(--warn-soft);
      color: var(--warn);
    }

    .status-mini.bad {
      background: var(--bad-soft);
      color: var(--bad);
    }

    .status-details-body {
      display: grid;
      gap: 6px;
      padding: 0 0 2px 24px;
    }

    .player-status-row {
      display: grid;
      grid-template-columns: minmax(80px, 0.9fr) auto minmax(120px, 1fr);
      gap: 8px;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px;
      background: #fff;
    }

    .player-status-row.current {
      border-color: var(--deck-class-border, var(--border));
      background: var(--deck-class-row, #f8fafc);
    }

    .debug-field {
      width: min(100%, 260px);
    }

    pre {
      margin: 0;
      max-height: 520px;
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      background: #0f172a;
      color: #e2e8f0;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 14px;
    }

    th,
    td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }

    th {
      background: #eef2f7;
      color: #334155;
      font-weight: 700;
    }

    td {
      overflow-wrap: anywhere;
    }

    tr:last-child td {
      border-bottom: 0;
    }

    @media (max-width: 1120px) {
      .battle-main-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 980px) {
      .layout,
      .role-grid,
      .battle-submissions,
      .battle-assignment-list,
      .battle-status-grid,
      .battle-round-grid,
      .battle-side-grid,
      .battle-summary-rounds,
      .summary-candidate-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 700px) {
      .shell {
        width: min(100% - 20px, 1220px);
      }

      .topbar,
      .toolbar,
      .panel-head,
      .control-row {
        align-items: stretch;
        flex-direction: column;
      }

      h1 {
        font-size: 24px;
      }

      .field {
        width: 100%;
      }

      .player-status-row {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="shell topbar">
        <div>
          <h1>PSルール戦略シミュレータ</h1>
          <div class="meta" id="dataset-meta">読み込み中...</div>
        </div>
      <nav class="site-nav" aria-label="主要ページ">
        <a class="nav-link" href="index.html">トップ</a>
        <a class="nav-link" href="streaming-report.html">配信レポート</a>
        <a class="nav-link active" aria-current="page" href="ps-simulator.html">PSルール戦略シミュレータ</a>
      </nav>
    </div>
  </header>

  <main>
    <div class="shell">
      <div class="toolbar">
        <div class="control-row">
          <label class="field">提出側
            <select id="submission-side">
              <option value="self">自分側</option>
              <option value="opponent">相手側</option>
            </select>
          </label>
          <button class="primary" id="reset-sample" type="button">サンプル提出案に戻す</button>
          <button id="clear-decks" type="button">デッキ選択をクリア</button>
        </div>
      </div>

      <div class="layout">
        <div class="stack">
          <section class="panel" aria-labelledby="builder-title">
            <div class="panel-head">
                <div>
                  <h2 id="builder-title">A/B/C 割当</h2>
                </div>
              <div class="class-coverage" id="class-coverage"></div>
            </div>
            <div class="panel-body">
              <div class="role-grid" id="role-grid"></div>
              <div class="submission-actions">
                <span class="submission-actions-label">現在の提出案をセット</span>
                <button class="primary" id="set-self-submission" type="button">自分側</button>
                <button id="set-opponent-submission" type="button">相手側</button>
                <button id="set-both-submission" type="button">両側</button>
              </div>
            </div>
          </section>
        </div>

        <aside class="stack">
          <section class="panel" aria-labelledby="validation-title">
            <div class="panel-head">
                <div>
                  <h2 id="validation-title">バリデーション</h2>
                </div>
              <span class="badge" id="validity-badge">確認中</span>
            </div>
            <div class="panel-body">
              <div class="validation-list" id="validation-list"></div>
            </div>
          </section>

          <section class="panel" aria-labelledby="debug-title">
            <div class="panel-head">
                <div>
                  <h2 id="debug-title">Debug</h2>
                </div>
            </div>
            <div class="panel-body stack">
              <details>
                <summary>開発者向け設定</summary>
                <div class="details-body stack">
                  <div class="data-summary" id="data-summary"></div>
                  <label class="field debug-field">抽選seed
                    <input id="battle-seed" type="text" value="sample-seed-001">
                  </label>
                </div>
              </details>
              <details>
                <summary>JSONプレビュー</summary>
                <div class="details-body">
                  <div class="json-actions">
                    <button id="download-battle-log" type="button">BattleLog JSONを保存</button>
                  </div>
                  <pre id="json-preview">{}</pre>
                </div>
              </details>
                <details>
                  <summary>読み込みデータ詳細</summary>
                  <div class="details-body stack">
                    <div class="source-note" id="debug-dataset-meta"></div>
                    <div>
                    <h3>デッキ一覧</h3>
                    <div id="deck-reference"></div>
                  </div>
                  <div>
                    <h3>選手一覧 / PlayerDeckStatus</h3>
                    <div id="player-reference"></div>
                  </div>
                </div>
              </details>
            </div>
          </section>
        </aside>
      </div>

      <section class="panel battle-panel" aria-labelledby="battle-title">
        <div class="panel-head">
          <div>
            <h2 id="battle-title">ラウンド進行シミュレータ</h2>
          </div>
        </div>
        <div class="panel-body stack">
          <div class="battle-submissions" id="battle-submissions"></div>
          <div class="battle-main-grid">
            <div class="battle-main-column">
              <div id="battle-self-deck-list"></div>
            </div>
            <div class="battle-main-column">
              <div class="battle-status-grid" id="battle-status-grid"></div>
              <div class="battle-round" id="battle-current-round"></div>
              <div class="battle-progress" id="battle-progress"></div>
              <div class="battle-controls">
                <button id="reset-battle-progress" type="button">ラウンドをやり直す</button>
              </div>
            </div>
            <div class="battle-main-column">
              <div id="battle-opponent-deck-list"></div>
            </div>
          </div>
          <section class="battle-summary-section" aria-labelledby="battle-summary-title">
            <div class="deck-class-group-head">
              <h3 id="battle-summary-title">スクショ共有用サマリー</h3>
              <div class="battle-summary-actions">
                <button id="download-battle-summary-png" type="button" disabled>共有用画像を保存</button>
                <button id="copy-battle-summary-png" type="button" disabled>画像をコピー</button>
                <span class="source-note battle-summary-export-status" id="battle-summary-export-status" aria-live="polite"></span>
              </div>
            </div>
            <div id="battle-summary-card"></div>
          </section>
        </div>
      </section>
    </div>
  </main>

  <script src="vendor/html2canvas.min.js"></script>
  <script>
    const roles = [
      { role: "A", expectedDeckCount: 3 },
      { role: "B", expectedDeckCount: 2 },
      { role: "C", expectedDeckCount: 2 }
    ];
    const roundRoleByNumber = { 1: "A", 2: "B", 3: "C" };
    const expectedRoundCandidateCounts = { 1: 3, 2: 2, 3: 2, 4: 4, 5: 3 };
    const datasetUrl = "data/ps_simulator/sample_dataset.json";
    const statusLabels = {
      confident: "自信あり",
      available: "使用可能",
      trainable: "頑張れば可",
      hard: "きつそう"
    };
    const state = {
      dataset: null,
      side: "self",
      assignments: {},
      battle: null
    };
    let isBattleSummaryPngExporting = false;

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function byDeckOrder(left, right) {
      return deckIndex(left) - deckIndex(right);
    }

    function deckIndex(deckId) {
      const decks = state.dataset?.decks || [];
      const index = decks.findIndex(deck => deck.deckId === deckId);
      return index === -1 ? Number.MAX_SAFE_INTEGER : index;
    }

    function classOrderIndex(className) {
      const fallbackOrder = ["E", "R", "W", "D", "Ni", "B", "Nm"];
      const fallbackIndex = fallbackOrder.indexOf(className);
      if (fallbackIndex !== -1) return fallbackIndex;
      const definitions = state.dataset?.classDefinitions || [];
      const definitionIndex = definitions.findIndex(definition => definition.className === className);
      if (definitionIndex !== -1) return definitionIndex;
      return Number.MAX_SAFE_INTEGER;
    }

    function byDeckClassOrder(left, right) {
      const leftDeck = deckById(left);
      const rightDeck = deckById(right);
      const classDiff = classOrderIndex(leftDeck?.className) - classOrderIndex(rightDeck?.className);
      return classDiff || byDeckOrder(left, right);
    }

    function sortDeckIdsByClassOrder(deckIds) {
      return [...(deckIds || [])].sort(byDeckClassOrder);
    }

    function classCssClass(className) {
      return `deck-class-${String(className || "").toLowerCase()}`;
    }

    function deckById(deckId) {
      return (state.dataset?.decks || []).find(deck => deck.deckId === deckId) || null;
    }

    function playerById(playerId) {
      return (state.dataset?.players || []).find(player => player.playerId === playerId) || null;
    }

    function initials(value) {
      const name = String(value || "?").trim();
      return Array.from(name || "?").slice(0, 2).join("").toUpperCase();
    }

    function playerIconUrl(player) {
      return player?.playerIconUrl || player?.player_icon_url || player?.iconUrl || "";
    }

    function avatarHtml(name, imageUrl, extraClass = "") {
      const fallback = escapeHtml(initials(name));
      const image = imageUrl
        ? `<img src="${escapeHtml(imageUrl)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
        : "";
      const className = ["player-avatar", extraClass].filter(Boolean).join(" ");
      return `<span class="${escapeHtml(className)}" aria-hidden="true">${image}<span>${fallback}</span></span>`;
    }

    function playerAvatarHtml(player, extraClass = "") {
      return avatarHtml(player?.playerName || "?", playerIconUrl(player), extraClass);
    }

    function classDefinition(className) {
      return (state.dataset?.classDefinitions || []).find(definition => definition.className === className) || null;
    }

    function classLabel(className) {
      const definition = classDefinition(className);
      return definition ? `${definition.displayName} (${definition.className})` : className || "不明";
    }

    function classBadgeHtml(className) {
      const definition = classDefinition(className);
      const label = definition ? definition.displayName : "不明";
      const code = definition ? definition.className : "?";
      return `
        <span class="class-badge ${escapeHtml(classCssClass(className))}" title="${escapeHtml(classLabel(className))}">
          <span class="class-dot" aria-hidden="true"></span>
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(code)}</strong>
        </span>
      `;
    }

    function compactClassBadgeHtml(className) {
      const definition = classDefinition(className);
      const code = definition ? definition.className : className || "?";
      return `<span class="class-code-pill ${escapeHtml(classCssClass(className))}" title="${escapeHtml(classLabel(className))}">${escapeHtml(code)}</span>`;
    }

    function decksByClass(className) {
      return (state.dataset?.decks || []).filter(deck => deck.className === className);
    }

    function assignmentForRole(role) {
      return state.assignments[role] || { playerId: "", deckIds: [] };
    }

    function selectedClassesForRole(role) {
      return (assignmentForRole(role).deckIds || [])
        .map(deckById)
        .filter(Boolean)
        .map(deck => deck.className);
    }

    function selectedRolesForClass(className) {
      return roles
        .filter(roleDef => selectedClassesForRole(roleDef.role).includes(className))
        .map(roleDef => roleDef.role);
    }

    function shouldShowClassForRole(role, className) {
      const selectedRoles = selectedRolesForClass(className);
      return selectedRoles.length === 0 || selectedRoles.includes(role);
    }

    function deckSummaryChipHtml(deck) {
      if (!deck) {
        return `<span class="summary-deck-chip empty">未選択</span>`;
      }
      const definition = classDefinition(deck.className);
      const classCode = definition?.className || deck.className || "?";
      return `
        <span class="summary-deck-chip ${escapeHtml(classCssClass(deck.className))}" title="${escapeHtml(classLabel(deck.className))} / deckId: ${escapeHtml(deck.deckId)}">
          <span class="summary-deck-chip-code" aria-hidden="true">${escapeHtml(classCode)}</span>
          <span>${escapeHtml(deck.deckName)}</span>
        </span>
      `;
    }

    function roleClassSummaryHtml(roleDef) {
      const assignment = assignmentForRole(roleDef.role);
      const selectedDecks = (assignment.deckIds || []).map(deckById).filter(Boolean);
      const selectedPlayer = playerById(assignment.playerId);
      const missingSlotCount = Math.max(roleDef.expectedDeckCount - selectedDecks.length, 0);
      const chips = [
        ...selectedDecks.map(deckSummaryChipHtml),
        ...Array.from({ length: missingSlotCount }, () => deckSummaryChipHtml(null))
      ].join("");
      const invalid = selectedDecks.length !== roleDef.expectedDeckCount;
      return `
        <div class="role-selection-summary ${invalid ? "invalid" : ""}">
          <div class="role-summary-head">
            <span class="badge">${escapeHtml(roleDef.role)}</span>
            <strong>${escapeHtml(selectedPlayer?.playerName || "担当未選択")}</strong>
            <span class="count">${selectedDecks.length}/${roleDef.expectedDeckCount}デッキ</span>
          </div>
          <div class="summary-deck-chips">${chips}</div>
        </div>
      `;
    }

    function classGroupState(role, className) {
      const selectedRoles = selectedRolesForClass(className);
      const selectedHere = selectedRoles.includes(role);
      if (selectedHere && selectedRoles.length > 1) {
        return ["bad", `重複: ${selectedRoles.join("/")}`];
      }
      return ["", ""];
    }

    function statusKey(playerId, deckId) {
      return `${playerId}\\u0000${deckId}`;
    }

    function statusMap() {
      const map = new Map();
      (state.dataset?.playerDeckStatuses || []).forEach(status => {
        map.set(statusKey(status.playerId, status.deckId), status);
      });
      return map;
    }

    function statusFor(playerId, deckId) {
      if (!playerId || !deckId) return null;
      return statusMap().get(statusKey(playerId, deckId)) || null;
    }

    function statusBadgeHtml(status) {
      if (!status) {
        return `<span class="status-badge missing">データなし</span><span class="badge warn">要確認</span>`;
      }
      const label = statusLabels[status.status] || status.status;
      return `<span class="status-badge ${escapeHtml(status.status)}">${escapeHtml(label)}</span>`;
    }

    function statusSummaryHtml(playerId, deckId) {
      const player = playerById(playerId);
      if (!player) {
        return `
          <span class="status-summary">
            <span class="status-summary-label">使用可能度:</span>
            <span class="status-mini warn">担当未選択</span>
          </span>
        `;
      }
      const status = statusFor(playerId, deckId);
      if (!status) {
        return `
          <span class="status-summary">
            <span class="status-summary-label">使用可能度:</span>
            <span class="status-mini warn">データなし</span>
            <span class="status-mini warn">要確認</span>
          </span>
        `;
      }
      const badgeKind = status.status === "hard"
        ? "bad"
        : status.status === "trainable"
          ? "warn"
          : status.status;
      const label = statusLabels[status.status] || status.status;
      return `
        <span class="status-summary">
          <span class="status-summary-label">使用可能度:</span>
          <span class="status-mini ${badgeKind}">${escapeHtml(label)}</span>
        </span>
      `;
    }

    function statusNoteHtml(status) {
      if (!status) {
        return "PlayerDeckStatus 行なし。データなし / 要確認として扱います。";
      }
      const parts = [`練習負荷 ${Number(status.practiceCost || 0)}`];
      if (status.note) parts.push(status.note);
      return parts.join(" / ");
    }

    function playerStatusRowForDeckHtml(deckId, currentPlayerId) {
      const player = playerById(currentPlayerId);
      if (!player) {
        return `<div class="status-note">担当選手を選ぶと使用可能度を確認できます。</div>`;
      }
      const status = statusFor(player.playerId, deckId);
      return `
        <div class="player-status-row current">
          <div class="badge-row">
            <strong>${escapeHtml(player.playerName)}</strong>
            <span class="badge ok">担当</span>
          </div>
          <div class="badge-row">${statusBadgeHtml(status)}</div>
          <div class="status-note">${escapeHtml(statusNoteHtml(status))}</div>
        </div>
      `;
    }

    function deckStatusDetailsHtml(deckId, currentPlayerId) {
      return `
        <details class="deck-status-details">
          <summary>
            ${statusSummaryHtml(currentPlayerId, deckId)}
          </summary>
          <div class="status-details-body">
            ${playerStatusRowForDeckHtml(deckId, currentPlayerId)}
          </div>
        </details>
      `;
    }

    function defaultAssignmentForRole(role, roleIndex, sampleSubmission) {
      const players = state.dataset?.players || [];
      const sample = (sampleSubmission?.assignments || []).find(assignment => assignment.role === role);
      return {
        playerId: sample?.playerId || players[roleIndex]?.playerId || players[0]?.playerId || "",
        deckIds: [...(sample?.deckIds || [])]
      };
    }

    function loadSampleSubmission() {
      const sample = state.dataset?.sampleSubmission || {};
      state.side = sample.side || "self";
      state.assignments = {};
      roles.forEach((roleDef, index) => {
        state.assignments[roleDef.role] = defaultAssignmentForRole(roleDef.role, index, sample);
      });
    }

    function clearDeckSelections() {
      roles.forEach(roleDef => {
        state.assignments[roleDef.role].deckIds = [];
      });
      render();
    }

    function currentSubmission() {
      return {
        submissionId: `draft-${state.side}-submission`,
        side: state.side,
        assignments: roles.map(roleDef => ({
          role: roleDef.role,
          playerId: state.assignments[roleDef.role]?.playerId || "",
          deckIds: [...(state.assignments[roleDef.role]?.deckIds || [])].sort(byDeckOrder)
        }))
      };
    }

    function cloneJson(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function normalizeSubmissionForSide(submission, side) {
      return {
        submissionId: submission?.submissionId || `draft-${side}-submission`,
        side,
        assignments: roles.map(roleDef => {
          const source = (submission?.assignments || []).find(assignment => assignment.role === roleDef.role) || {};
          return {
            role: roleDef.role,
            playerId: source.playerId || "",
            deckIds: [...(source.deckIds || [])].sort(byDeckOrder)
          };
        })
      };
    }

    function sampleSubmissionForSide(side) {
      const sample = cloneJson(state.dataset?.sampleSubmission || { assignments: [] });
      sample.side = side;
      sample.submissionId = side === "self" ? "sample-self-submission" : "sample-opponent-submission";
      return normalizeSubmissionForSide(sample, side);
    }

    function snapshotDeck(deckId) {
      const deck = deckById(deckId);
      if (!deck) {
        return {
          deckId,
          className: "",
          deckName: deckId || "未選択",
          source: "missing"
        };
      }
      return {
        deckId: deck.deckId,
        className: deck.className,
        deckName: deck.deckName,
        source: deck.source || "",
        sourceDeckKey: deck.sourceDeckKey || ""
      };
    }

    function snapshotPlayer(playerId) {
      const player = playerById(playerId);
      if (!player) {
        return {
          playerId,
          playerName: playerId || "未選択",
          team: "",
          note: ""
        };
      }
      return {
        playerId: player.playerId,
        playerName: player.playerName,
        team: player.team || "",
        note: player.note || ""
      };
    }

    function snapshotSubmission(submission, side) {
      return {
        submissionId: submission?.submissionId || `draft-${side}-submission`,
        side,
        assignments: roles.map(roleDef => {
          const source = (submission?.assignments || []).find(assignment => assignment.role === roleDef.role) || {};
          const deckIds = [...(source.deckIds || [])].sort(byDeckOrder);
          return {
            role: roleDef.role,
            playerId: source.playerId || "",
            playerSnapshot: snapshotPlayer(source.playerId || ""),
            deckIds,
            deckSnapshots: deckIds.map(snapshotDeck)
          };
        })
      };
    }

    function initializeBattleState() {
      state.battle = {
        createdAt: new Date().toISOString(),
        seed: "sample-seed-001",
        selfSubmission: sampleSubmissionForSide("self"),
        opponentSubmission: sampleSubmissionForSide("opponent"),
        rounds: [],
        score: { self: 0, opponent: 0 },
        isComplete: false,
        winner: "",
        finishedAtRound: null
      };
      resetBattleProgress(false);
    }

    function assignmentByRole(submission, role) {
      return (submission?.assignments || []).find(assignment => assignment.role === role) || null;
    }

    function assignmentForDeck(submission, deckId) {
      return (submission?.assignments || []).find(assignment => (assignment.deckIds || []).includes(deckId)) || null;
    }

    function playerForDeckInSubmission(submission, deckId) {
      return playerById(assignmentForDeck(submission, deckId)?.playerId);
    }

    function uniqueDeckIds(deckIds) {
      const seen = new Set();
      return (deckIds || []).filter(deckId => {
        if (!deckId || seen.has(deckId)) return false;
        seen.add(deckId);
        return true;
      });
    }

    function submissionDeckIds(submission) {
      return uniqueDeckIds((submission?.assignments || []).flatMap(assignment => assignment.deckIds || []));
    }

    function candidateDeckIdsForRound(submission, roundNumber, usedDeckIds) {
      const used = new Set(usedDeckIds || []);
      const role = roundRoleByNumber[roundNumber];
      if (role) {
        return uniqueDeckIds(assignmentByRole(submission, role)?.deckIds || [])
          .filter(deckId => !used.has(deckId));
      }
      if (roundNumber === 4 || roundNumber === 5) {
        return submissionDeckIds(submission).filter(deckId => !used.has(deckId));
      }
      return [];
    }

    function validateRoundCandidates(roundNumber, candidateDeckIds) {
      const expected = expectedRoundCandidateCounts[roundNumber];
      if (!expected || candidateDeckIds.length === expected) return [];
      return [`R${roundNumber}候補は${expected}デッキ想定です。現在は${candidateDeckIds.length}デッキです。`];
    }

    function scoreFromRounds(rounds) {
      return rounds.reduce((score, round) => {
        if (round.result === "self_win") score.self += 1;
        if (round.result === "opponent_win") score.opponent += 1;
        return score;
      }, { self: 0, opponent: 0 });
    }

    function selectedDeckIdForSide(round, side) {
      return side === "self" ? round.selfSelectedDeckId : round.opponentSelectedDeckId;
    }

    function usedDeckIdsForSideFromRounds(rounds, side, options = {}) {
      const throughRoundNumber = Object.prototype.hasOwnProperty.call(options, "throughRoundNumber")
        ? options.throughRoundNumber
        : null;
      const hasRoundLimit = Number.isInteger(throughRoundNumber);
      return uniqueDeckIds((rounds || []).filter(round => (
        !hasRoundLimit || round.roundNumber <= throughRoundNumber
      )).map(round => selectedDeckIdForSide(round, side)).filter(Boolean));
    }

    function usedDeckIdsBeforeRound(side, roundNumber) {
      return usedDeckIdsForSideFromRounds(
        state.battle?.rounds || [],
        side,
        { throughRoundNumber: roundNumber - 1 }
      );
    }

    function usedDeckIdsForSide(side) {
      return usedDeckIdsForSideFromRounds(state.battle?.rounds || [], side);
    }

    function remainingDeckIdsForSide(side, usedDeckIds) {
      const submission = side === "self" ? state.battle.selfSubmission : state.battle.opponentSubmission;
      const used = new Set(usedDeckIds || []);
      return submissionDeckIds(submission).filter(deckId => !used.has(deckId));
    }

    function refreshRoundUsageSnapshot(round) {
      round.selfUsedDeckIds = usedDeckIdsForSideFromRounds(
        state.battle.rounds,
        "self",
        { throughRoundNumber: round.roundNumber }
      );
      round.opponentUsedDeckIds = usedDeckIdsForSideFromRounds(
        state.battle.rounds,
        "opponent",
        { throughRoundNumber: round.roundNumber }
      );
      round.selfRemainingDeckIds = remainingDeckIdsForSide("self", round.selfUsedDeckIds);
      round.opponentRemainingDeckIds = remainingDeckIdsForSide("opponent", round.opponentUsedDeckIds);
    }

    function refreshBattleUsageSnapshots() {
      (state.battle?.rounds || []).forEach(refreshRoundUsageSnapshot);
    }

    function createBattleRound(roundNumber) {
      const selfUsed = usedDeckIdsBeforeRound("self", roundNumber);
      const opponentUsed = usedDeckIdsBeforeRound("opponent", roundNumber);
      const selfCandidateDeckIds = candidateDeckIdsForRound(state.battle.selfSubmission, roundNumber, selfUsed);
      const opponentCandidateDeckIds = candidateDeckIdsForRound(state.battle.opponentSubmission, roundNumber, opponentUsed);
      const round = {
        roundNumber,
        selfCandidateDeckIds,
        opponentCandidateDeckIds,
        selfSelectedDeckId: "",
        opponentSelectedDeckId: "",
        selfWinRate: 0.5,
        winRateNote: "選択前です。",
        winRateSource: {
          type: "unknown",
          note: "選択前です。"
        },
        result: "",
        resultDecisionMethod: "",
        resultDecision: null,
        selfUsedDeckIds: [...selfUsed],
        opponentUsedDeckIds: [...opponentUsed],
        selfRemainingDeckIds: remainingDeckIdsForSide("self", selfUsed),
        opponentRemainingDeckIds: remainingDeckIdsForSide("opponent", opponentUsed),
        candidateWarnings: [
          ...validateRoundCandidates(roundNumber, selfCandidateDeckIds).map(message => `自分側: ${message}`),
          ...validateRoundCandidates(roundNumber, opponentCandidateDeckIds).map(message => `相手側: ${message}`)
        ],
        score: { ...state.battle.score }
      };
      return round;
    }

    function resetRoundsFrom(roundNumber, shouldRender = true) {
      if (!state.battle) return;
      // 現行UIでは過去ラウンドを直接編集しない。将来編集可能にする場合は、
      // 後続状態を保持せず、この関数で編集ラウンド以降を作り直す。
      state.battle.rounds = state.battle.rounds.filter(round => round.roundNumber < roundNumber);
      state.battle.score = scoreFromRounds(state.battle.rounds);
      state.battle.isComplete = false;
      state.battle.winner = "";
      state.battle.finishedAtRound = null;
      state.battle.rounds.push(createBattleRound(roundNumber));
      refreshBattleUsageSnapshots();
      if (shouldRender) render();
    }

    function resetBattleProgress(shouldRender = true) {
      if (!state.battle) return;
      state.battle.createdAt = new Date().toISOString();
      state.battle.rounds = [];
      state.battle.score = { self: 0, opponent: 0 };
      state.battle.isComplete = false;
      state.battle.winner = "";
      state.battle.finishedAtRound = null;
      state.battle.rounds.push(createBattleRound(1));
      if (shouldRender) render();
    }

    function activeBattleRound() {
      if (state.battle?.isComplete) return null;
      return (state.battle?.rounds || []).find(round => !round.result) || null;
    }

    function lookupSelfWinRate(selfDeckId, opponentDeckId) {
      const matchup = (state.dataset?.sampleMatchups || []).find(item => (
        item.deckIdA === selfDeckId && item.deckIdB === opponentDeckId
      ));
      if (matchup) {
        return {
          winRate: Number(matchup.winRateForA),
          note: "sampleMatchupsの暫定値を使用しています。",
          source: {
            type: "matchup",
            deckIdA: matchup.deckIdA,
            deckIdB: matchup.deckIdB,
            winRateForA: Number(matchup.winRateForA),
            note: matchup.note || ""
          }
        };
      }
      const reverseMatchup = (state.dataset?.sampleMatchups || []).find(item => (
        item.deckIdA === opponentDeckId && item.deckIdB === selfDeckId
      ));
      if (reverseMatchup) {
        return {
          winRate: 1 - Number(reverseMatchup.winRateForA),
          note: "sampleMatchupsの逆向き暫定値を使用しています。",
          source: {
            type: "reverseMatchup",
            deckIdA: reverseMatchup.deckIdA,
            deckIdB: reverseMatchup.deckIdB,
            winRateForA: Number(reverseMatchup.winRateForA),
            note: reverseMatchup.note || ""
          }
        };
      }
      return {
        winRate: 0.5,
        note: "相性表未接続のため暫定0.5を使用しています。",
        source: {
          type: "fallback",
          fallbackValue: 0.5,
          note: "相性表未接続のため暫定0.5を使用しています。"
        }
      };
    }

    function updateRoundWinRate(round) {
      if (!round.selfSelectedDeckId || !round.opponentSelectedDeckId) {
        round.selfWinRate = 0.5;
        round.winRateNote = "選択前です。";
        round.winRateSource = {
          type: "unknown",
          note: "選択前です。"
        };
        return;
      }
      const lookup = lookupSelfWinRate(round.selfSelectedDeckId, round.opponentSelectedDeckId);
      round.selfWinRate = lookup.winRate;
      round.winRateNote = lookup.note;
      round.winRateSource = lookup.source;
    }

    function setBattleSubmission(side, submission) {
      if (!state.battle) initializeBattleState();
      state.battle[side === "self" ? "selfSubmission" : "opponentSubmission"] =
        normalizeSubmissionForSide(submission, side);
      resetBattleProgress();
    }

    function setBattleSubmissionForBothSides(submission) {
      if (!state.battle) initializeBattleState();
      state.battle.selfSubmission = normalizeSubmissionForSide(submission, "self");
      state.battle.opponentSubmission = normalizeSubmissionForSide(submission, "opponent");
      resetBattleProgress();
    }

    function canUseBattleSubmission(submission) {
      return validateSubmission(submission).canStartBattle;
    }

    function selectBattleDeck(side, deckId) {
      const round = activeBattleRound();
      if (!round) return;
      const candidates = side === "self" ? round.selfCandidateDeckIds : round.opponentCandidateDeckIds;
      const used = new Set(usedDeckIdsBeforeRound(side, round.roundNumber));
      if (!candidates.includes(deckId) || used.has(deckId)) return;
      if (side === "self") {
        round.selfSelectedDeckId = deckId;
      } else {
        round.opponentSelectedDeckId = deckId;
      }
      updateRoundWinRate(round);
      refreshRoundUsageSnapshot(round);
      render();
    }

    function deterministicUnitInterval(seedText) {
      let hash = 2166136261;
      for (const char of String(seedText)) {
        hash ^= char.charCodeAt(0);
        hash = Math.imul(hash, 16777619);
      }
      hash += hash << 13;
      hash ^= hash >>> 7;
      hash += hash << 3;
      hash ^= hash >>> 17;
      hash += hash << 5;
      return (hash >>> 0) / 4294967296;
    }

    function rollBattleRound() {
      const round = activeBattleRound();
      if (!round || !round.selfSelectedDeckId || !round.opponentSelectedDeckId) return;
      updateRoundWinRate(round);
      const seedInput = [
        state.battle.seed,
        round.roundNumber,
        round.selfSelectedDeckId,
        round.opponentSelectedDeckId
      ].join("|");
      const roll = deterministicUnitInterval(seedInput);
      decideBattleRound(roll < round.selfWinRate ? "self_win" : "opponent_win", {
        method: "random",
        randomValue: roll,
        seedInput
      });
    }

    function decideBattleRound(result, decision = {}) {
      const round = activeBattleRound();
      if (!round || !round.selfSelectedDeckId || !round.opponentSelectedDeckId) return;
      updateRoundWinRate(round);
      round.result = result;
      round.resultDecisionMethod = decision.method || "manual";
      round.resultDecision = {
        method: round.resultDecisionMethod,
        randomValue: Number.isFinite(decision.randomValue) ? decision.randomValue : null,
        seedInput: decision.seedInput || "",
        note: decision.note || ""
      };
      state.battle.score = scoreFromRounds(state.battle.rounds);
      refreshRoundUsageSnapshot(round);
      round.score = { ...state.battle.score };

      if (state.battle.score.self >= 3 || state.battle.score.opponent >= 3 || round.roundNumber >= 5) {
        state.battle.isComplete = true;
        state.battle.winner = state.battle.score.self > state.battle.score.opponent ? "self" : "opponent";
        state.battle.finishedAtRound = round.roundNumber;
      } else {
        state.battle.rounds.push(createBattleRound(round.roundNumber + 1));
      }
      render();
    }

    function formatWinRate(value) {
      return `${Math.round(Number(value) * 100)}%`;
    }

    function battleLabel(roundNumber) {
      return `バトル${roundNumber}`;
    }

    function sideLabel(side) {
      if (side === "self") return "自分側";
      if (side === "opponent") return "相手側";
      return "未定";
    }

    function playerSideText(player, fallbackSide) {
      return player ? `${player.playerName}側` : sideLabel(fallbackSide);
    }

    function playerSideHtml(player, fallbackSide) {
      if (!player) {
        return `<span class="side-label">${escapeHtml(sideLabel(fallbackSide))}</span>`;
      }
      return `
        <span class="side-label">
          ${playerAvatarHtml(player, "small")}
          <span>${escapeHtml(player.playerName)}側</span>
        </span>
      `;
    }

    function battleSideResultHtml(result, side) {
      if (!result) return "";
      const won = (side === "self" && result === "self_win") || (side === "opponent" && result === "opponent_win");
      return `<span class="battle-result-badge ${won ? "win" : "loss"}">${won ? "勝ち" : "負け"}</span>`;
    }

    function groupedDeckIdsByPlayer(submission, deckIds) {
      const remaining = new Set(deckIds || []);
      const groups = (submission?.assignments || []).map(assignment => {
        const groupDeckIds = (assignment.deckIds || []).filter(deckId => remaining.has(deckId));
        groupDeckIds.forEach(deckId => remaining.delete(deckId));
        return {
          player: playerById(assignment.playerId),
          deckIds: groupDeckIds
        };
      }).filter(group => group.deckIds.length > 0);
      if (remaining.size > 0) {
        groups.push({ player: null, deckIds: Array.from(remaining).sort(byDeckOrder) });
      }
      return groups;
    }

    function deckTokenHtml(deckId, options = {}) {
      const deck = options.deck || deckById(deckId);
      if (!deck) {
        return `<span class="deck-token"><strong class="deck-token-name">${escapeHtml(deckId || "未選択")}</strong></span>`;
      }
      const definition = classDefinition(deck.className);
      const classCode = definition?.className || deck.className || "?";
      const tokenDeckId = deck.deckId || deckId;
      const player = options.player || null;
      return `
        <span class="deck-token ${escapeHtml(classCssClass(deck.className))}" title="${escapeHtml(classLabel(deck.className))} / deckId: ${escapeHtml(tokenDeckId)}">
          ${player ? playerAvatarHtml(player, "small") : ""}
          <span class="deck-token-code" aria-hidden="true">${escapeHtml(classCode)}</span>
          <strong class="deck-token-name">${escapeHtml(deck.deckName)}</strong>
        </span>
      `;
    }

    function deckTokenListHtml(deckIds) {
      if (!deckIds.length) {
        return `<span class="source-note">なし</span>`;
      }
      return `
        <div class="deck-token-row">
          ${deckIds.map(deckTokenHtml).join("")}
        </div>
      `;
    }

    function deckGroupListHtml(submission, deckIds) {
      if (!deckIds.length) {
        return `<span class="source-note">なし</span>`;
      }
      const sortedDeckIds = sortDeckIdsByClassOrder(deckIds);
      return `
        <div class="deck-token-list">
          ${sortedDeckIds.map(deckId => deckTokenHtml(deckId, {
            player: playerForDeckInSubmission(submission, deckId)
          })).join("")}
        </div>
      `;
    }

    function selectedProgressDeckHtml(submission, deckId) {
      if (!deckId) {
        return `<span class="source-note">未選択</span>`;
      }
      const player = playerForDeckInSubmission(submission, deckId);
      return deckTokenHtml(deckId, { player });
    }

    function representativePlayerForCandidates(submission, deckIds) {
      const groups = groupedDeckIdsByPlayer(submission, deckIds);
      return groups.length === 1 ? groups[0].player : null;
    }

    function selectedOrRepresentativePlayer(submission, deckId, deckIds) {
      return playerForDeckInSubmission(submission, deckId) || representativePlayerForCandidates(submission, deckIds);
    }

    function submissionSummaryHtml(label, submission) {
      const assignments = roles.map(roleDef => {
        const assignment = assignmentByRole(submission, roleDef.role) || {};
        const player = playerById(assignment.playerId);
        const deckIds = assignment.deckIds || [];
        return `
          <div class="battle-assignment">
            <div class="battle-assignment-main">
              <div class="battle-assignment-head">
                <span class="badge">${escapeHtml(roleDef.role)}</span>
                ${playerAvatarHtml(player, "small")}
                <strong>${escapeHtml(player?.playerName || assignment.playerId || "未選択")}</strong>
              </div>
              ${deckTokenListHtml(deckIds)}
            </div>
          </div>
        `;
      }).join("");
      return `
        <section class="battle-submission">
          <div class="deck-class-group-head">
            <h3>${escapeHtml(label)}</h3>
          </div>
          <div class="battle-assignment-list">${assignments}</div>
        </section>
      `;
    }

    function renderChoiceList(side, round) {
      const candidates = side === "self" ? round.selfCandidateDeckIds : round.opponentCandidateDeckIds;
      const selectedDeckId = side === "self" ? round.selfSelectedDeckId : round.opponentSelectedDeckId;
      const submission = side === "self" ? state.battle.selfSubmission : state.battle.opponentSubmission;
      const used = new Set(usedDeckIdsBeforeRound(side, round.roundNumber));
      if (candidates.length === 0) {
        return `<div class="validation-item warn">候補デッキがありません。</div>`;
      }
      return `
        <div class="choice-list">
          ${candidates.map(deckId => {
            const usedDeck = used.has(deckId);
            const selected = selectedDeckId === deckId;
            const disabled = usedDeck || Boolean(round.result) || state.battle.isComplete;
            const deck = deckById(deckId);
            const player = playerForDeckInSubmission(submission, deckId);
            return `
              <button
                class="choice-button ${deck ? escapeHtml(classCssClass(deck.className)) : ""} ${selected ? "selected" : ""}"
                type="button"
                data-battle-side="${escapeHtml(side)}"
                data-battle-deck-id="${escapeHtml(deckId)}"
                ${disabled ? "disabled" : ""}
              >
                ${deckTokenHtml(deckId, { player })}
                ${usedDeck ? `<span class="badge warn">使用済み</span>` : ""}
              </button>
            `;
          }).join("")}
        </div>
      `;
    }

    function renderSideDeckStatus(side, submission, usedDeckIds, remainingDeckIds) {
      return `
        <section class="battle-list">
          <h3>${escapeHtml(sideLabel(side))} デッキ状況</h3>
          <div class="deck-list-group">
            <div class="deck-class-group-head">
              <strong>使用済みデッキ</strong>
            </div>
            ${deckGroupListHtml(submission, usedDeckIds)}
          </div>
          <div class="deck-list-group">
            <div class="deck-class-group-head">
              <strong>残りデッキ</strong>
            </div>
            ${deckGroupListHtml(submission, remainingDeckIds)}
          </div>
        </section>
      `;
    }

    function renderBattleStatus() {
      const battle = state.battle;
      const active = activeBattleRound();
      const currentBattleLabel = battle.isComplete ? "終了済み" : battleLabel(active?.roundNumber || 1);
      document.getElementById("battle-status-grid").innerHTML = [
        `
          <section class="battle-card ${battle.isComplete ? "ended" : ""}">
            <h3>ラウンドスコア</h3>
            <div class="scoreline">自分側 ${battle.score.self} - ${battle.score.opponent} 相手側</div>
            <div class="source-note">現在バトル: ${escapeHtml(currentBattleLabel)}</div>
          </section>
        `,
        `
          <section class="battle-card ${battle.isComplete ? "ended" : ""}">
            <h3>ラウンド条件</h3>
            <div><strong>3勝先取</strong></div>
            <div class="source-note">最大5バトルで終了します。</div>
          </section>
        `
      ].join("");
    }

    function renderCurrentRound() {
      const battle = state.battle;
      const active = activeBattleRound();
      if (!active) {
        document.getElementById("battle-current-round").innerHTML = `
          <div class="battle-card ended">
            <h3>ラウンド終了</h3>
            <div class="scoreline">最終結果: ${sideLabel(battle.winner)}勝利</div>
          </div>
        `;
        return;
      }
      const canDecide = active.selfSelectedDeckId && active.opponentSelectedDeckId && !active.result;
      const selfPlayer = selectedOrRepresentativePlayer(state.battle.selfSubmission, active.selfSelectedDeckId, active.selfCandidateDeckIds);
      const opponentPlayer = selectedOrRepresentativePlayer(state.battle.opponentSubmission, active.opponentSelectedDeckId, active.opponentCandidateDeckIds);
      document.getElementById("battle-current-round").innerHTML = `
        <div class="deck-class-group-head">
          <div>
            <h3>${escapeHtml(battleLabel(active.roundNumber))} 選出</h3>
            <div class="source-note">暫定勝率: ${formatWinRate(active.selfWinRate)} / ${escapeHtml(active.winRateNote)}</div>
            ${(active.candidateWarnings || []).map(message => (
              `<div class="validation-item warn">${escapeHtml(message)}</div>`
            )).join("")}
          </div>
        </div>
        <div class="battle-round-grid">
          <section class="battle-card">
            <div class="deck-class-group-head">
              <h3>自分側候補</h3>
            </div>
            ${renderChoiceList("self", active)}
          </section>
          <section class="battle-card">
            <div class="deck-class-group-head">
              <h3>相手側候補</h3>
            </div>
            ${renderChoiceList("opponent", active)}
          </section>
        </div>
        <div class="battle-controls">
          <button class="primary" id="roll-round" type="button" ${canDecide ? "" : "disabled"}>抽選</button>
          <button id="manual-self-win" type="button" ${canDecide ? "" : "disabled"}>手動: ${escapeHtml(playerSideText(selfPlayer, "self"))}勝ち</button>
          <button id="manual-opponent-win" type="button" ${canDecide ? "" : "disabled"}>手動: ${escapeHtml(playerSideText(opponentPlayer, "opponent"))}勝ち</button>
        </div>
      `;
    }

    function renderBattleDeckLists() {
      const selfUsed = usedDeckIdsForSide("self");
      const opponentUsed = usedDeckIdsForSide("opponent");
      const selfRemaining = submissionDeckIds(state.battle.selfSubmission).filter(deckId => !selfUsed.includes(deckId));
      const opponentRemaining = submissionDeckIds(state.battle.opponentSubmission).filter(deckId => !opponentUsed.includes(deckId));
      document.getElementById("battle-self-deck-list").innerHTML =
        renderSideDeckStatus("self", state.battle.selfSubmission, selfUsed, selfRemaining);
      document.getElementById("battle-opponent-deck-list").innerHTML =
        renderSideDeckStatus("opponent", state.battle.opponentSubmission, opponentUsed, opponentRemaining);
    }

    function renderBattleProgress() {
      const rows = [1, 2, 3, 4, 5].map(roundNumber => {
        const round = state.battle.rounds.find(item => item.roundNumber === roundNumber);
        const isCurrent = activeBattleRound()?.roundNumber === roundNumber;
        if (!round) {
          return `
            <div class="progress-item">
              <div class="progress-head">
                <strong>${escapeHtml(battleLabel(roundNumber))}</strong>
              </div>
            </div>
          `;
        }
        const className = round.result ? "progress-item done" : isCurrent ? "progress-item current" : "progress-item";
        return `
          <div class="${className}">
            <div class="progress-head">
              <strong>${escapeHtml(battleLabel(roundNumber))}</strong>
            </div>
            <div class="progress-match">
              <span class="progress-side">
                ${selectedProgressDeckHtml(state.battle.selfSubmission, round.selfSelectedDeckId)}
                ${battleSideResultHtml(round.result, "self")}
              </span>
              <span class="side-label">vs</span>
              <span class="progress-side">
                ${selectedProgressDeckHtml(state.battle.opponentSubmission, round.opponentSelectedDeckId)}
                ${battleSideResultHtml(round.result, "opponent")}
              </span>
            </div>
          </div>
        `;
      }).join("");
      document.getElementById("battle-progress").innerHTML = rows;
    }

    function finalResultPayload() {
      if (!state.battle?.isComplete) return null;
      return {
        winner: state.battle.winner,
        result: state.battle.winner === "self" ? "self_win" : "opponent_win",
        selfWins: state.battle.score.self,
        opponentWins: state.battle.score.opponent,
        score: { ...state.battle.score },
        finishedAtRound: state.battle.finishedAtRound
      };
    }

    function buildBattleRoundLog(round) {
      const scoreAfterRound = round.score || scoreFromRounds(
        (state.battle?.rounds || []).filter(item => item.roundNumber <= round.roundNumber)
      );
      return {
        roundNumber: round.roundNumber,
        selfCandidateDeckIds: [...(round.selfCandidateDeckIds || [])],
        opponentCandidateDeckIds: [...(round.opponentCandidateDeckIds || [])],
        candidateDeckIds: {
          self: [...(round.selfCandidateDeckIds || [])],
          opponent: [...(round.opponentCandidateDeckIds || [])]
        },
        selfSelectedDeckId: round.selfSelectedDeckId || "",
        opponentSelectedDeckId: round.opponentSelectedDeckId || "",
        selectedDeckIds: {
          self: round.selfSelectedDeckId || "",
          opponent: round.opponentSelectedDeckId || ""
        },
        selfWinRate: Number(round.selfWinRate),
        winRate: {
          self: Number(round.selfWinRate),
          opponent: 1 - Number(round.selfWinRate)
        },
        winRateSource: cloneJson(round.winRateSource || {
          type: "unknown",
          note: round.winRateNote || ""
        }),
        winRateNote: round.winRateNote || "",
        result: round.result || null,
        resultDecisionMethod: round.result ? (round.resultDecisionMethod || "manual") : null,
        resultDecision: round.result ? cloneJson(round.resultDecision || {
          method: round.resultDecisionMethod || "manual",
          randomValue: null,
          seedInput: "",
          note: ""
        }) : null,
        scoreAfterRound,
        score: scoreAfterRound,
        selfUsedDeckIds: [...(round.selfUsedDeckIds || [])],
        opponentUsedDeckIds: [...(round.opponentUsedDeckIds || [])],
        selfRemainingDeckIds: [...(round.selfRemainingDeckIds || [])],
        opponentRemainingDeckIds: [...(round.opponentRemainingDeckIds || [])],
        usedDeckIdsAfterRound: {
          self: [...(round.selfUsedDeckIds || [])],
          opponent: [...(round.opponentUsedDeckIds || [])]
        },
        remainingDeckIdsAfterRound: {
          self: [...(round.selfRemainingDeckIds || [])],
          opponent: [...(round.opponentRemainingDeckIds || [])]
        },
        candidateWarnings: [...(round.candidateWarnings || [])]
      };
    }

    function buildBattleLog() {
      if (!state.battle) return null;
      return {
        logVersion: "ps-battle-log.v1",
        createdAt: state.battle.createdAt,
        seed: state.battle.seed,
        selfSubmissionId: state.battle.selfSubmission.submissionId,
        opponentSubmissionId: state.battle.opponentSubmission.submissionId,
        selfSubmissionSnapshot: snapshotSubmission(state.battle.selfSubmission, "self"),
        opponentSubmissionSnapshot: snapshotSubmission(state.battle.opponentSubmission, "opponent"),
        rounds: state.battle.rounds.map(buildBattleRoundLog),
        finalResult: finalResultPayload(),
        finishedAtRound: state.battle.finishedAtRound
      };
    }

    function roundCandidateDeckIds(round, side) {
      return round?.candidateDeckIds?.[side] || (
        side === "self" ? round?.selfCandidateDeckIds : round?.opponentCandidateDeckIds
      ) || [];
    }

    function roundSelectedDeckId(round, side) {
      return round?.selectedDeckIds?.[side] || (
        side === "self" ? round?.selfSelectedDeckId : round?.opponentSelectedDeckId
      ) || "";
    }

    function roundScoreAfter(round) {
      return round?.scoreAfterRound || round?.score || null;
    }

    function battleScoreText(score) {
      if (!score) return "-";
      return `${Number(score.self || 0)}-${Number(score.opponent || 0)}`;
    }

    function summaryRoundResultText(result) {
      if (result === "self_win") return "自分勝ち";
      if (result === "opponent_win") return "相手勝ち";
      return "未確定";
    }

    function summaryRoundResultClass(result) {
      if (result === "self_win") return "self-win";
      if (result === "opponent_win") return "opponent-win";
      return "pending";
    }

    function summaryRoundClass(result) {
      if (result === "self_win") return "win";
      if (result === "opponent_win") return "loss";
      return "";
    }

    function logSubmissionSnapshot(battleLog, side) {
      return side === "self" ? battleLog?.selfSubmissionSnapshot : battleLog?.opponentSubmissionSnapshot;
    }

    function logAssignmentForDeck(logSubmission, deckId) {
      return (logSubmission?.assignments || []).find(assignment => (
        (assignment.deckIds || []).includes(deckId)
      )) || null;
    }

    function logDeckSnapshot(logSubmission, deckId) {
      const assignment = logAssignmentForDeck(logSubmission, deckId);
      return (assignment?.deckSnapshots || []).find(deck => deck.deckId === deckId) || deckById(deckId);
    }

    function logPlayerForDeck(logSubmission, deckId) {
      const assignment = logAssignmentForDeck(logSubmission, deckId);
      return assignment?.playerSnapshot || playerById(assignment?.playerId);
    }

    function logDeckTokenHtml(battleLog, side, deckId) {
      if (!deckId) {
        return `<span class="deck-token"><strong class="deck-token-name">未選択</strong></span>`;
      }
      const submission = logSubmissionSnapshot(battleLog, side);
      return deckTokenHtml(deckId, {
        deck: logDeckSnapshot(submission, deckId),
        player: logPlayerForDeck(submission, deckId)
      });
    }

    function logDeckTokenListHtml(battleLog, side, deckIds) {
      const ids = sortDeckIdsByClassOrder(deckIds || []);
      if (!ids.length) {
        return `<span class="source-note">なし</span>`;
      }
      return `
        <div class="deck-token-row">
          ${ids.map(deckId => logDeckTokenHtml(battleLog, side, deckId)).join("")}
        </div>
      `;
    }

    function summaryFinalScore(battleLog) {
      const finalResult = battleLog?.finalResult;
      if (finalResult?.score) return finalResult.score;
      if (Number.isFinite(Number(finalResult?.selfWins)) || Number.isFinite(Number(finalResult?.opponentWins))) {
        return {
          self: Number(finalResult?.selfWins || 0),
          opponent: Number(finalResult?.opponentWins || 0)
        };
      }
      const latestRound = [...(battleLog?.rounds || [])].reverse().find(round => roundScoreAfter(round));
      return roundScoreAfter(latestRound) || { self: 0, opponent: 0 };
    }

    function battleSummaryHeroHtml(battleLog) {
      const finalResult = battleLog?.finalResult;
      const complete = Boolean(finalResult);
      const score = summaryFinalScore(battleLog);
      const title = complete
        ? `${sideLabel(finalResult.winner)} 勝利 ${battleScoreText(score)}`
        : `未完了 ${battleScoreText(score)}`;
      return `
        <section class="battle-summary-result ${complete ? "" : "incomplete"}">
          <div class="battle-summary-titleline">${escapeHtml(title)}</div>
        </section>
      `;
    }

    function summaryRoundCandidatesHtml(battleLog, round) {
      if (!round || round.roundNumber < 4) return "";
      const label = battleLabel(round.roundNumber);
      return `
        <div class="summary-round-candidates">
          <h4>${escapeHtml(label)}開始時候補</h4>
          <div class="summary-candidate-grid">
            <div class="deck-list-group">
              <strong>自分側</strong>
              ${logDeckTokenListHtml(battleLog, "self", roundCandidateDeckIds(round, "self"))}
            </div>
            <div class="deck-list-group">
              <strong>相手側</strong>
              ${logDeckTokenListHtml(battleLog, "opponent", roundCandidateDeckIds(round, "opponent"))}
            </div>
          </div>
        </div>
      `;
    }

    function summaryRoundCardHtml(battleLog, roundNumber) {
      const round = (battleLog?.rounds || []).find(item => item.roundNumber === roundNumber);
      if (!round) {
        return `
          <section class="summary-round-card pending">
            <div class="summary-round-head">
              <strong>${escapeHtml(battleLabel(roundNumber))}</strong>
              <span class="summary-result-badge pending">未到達</span>
            </div>
          </section>
        `;
      }
      const resultClass = summaryRoundClass(round.result);
      return `
        <section class="summary-round-card ${escapeHtml(resultClass)}">
          <div class="summary-round-head">
            <strong>${escapeHtml(battleLabel(round.roundNumber))}</strong>
            <span class="summary-result-badge ${escapeHtml(summaryRoundResultClass(round.result))}">${escapeHtml(summaryRoundResultText(round.result))}</span>
          </div>
          <div class="summary-round-match">
            <div class="summary-side-line">
              <span class="side-label">自分</span>
              ${logDeckTokenHtml(battleLog, "self", roundSelectedDeckId(round, "self"))}
              ${battleSideResultHtml(round.result, "self")}
            </div>
            <div class="summary-side-line">
              <span class="side-label">相手</span>
              ${logDeckTokenHtml(battleLog, "opponent", roundSelectedDeckId(round, "opponent"))}
              ${battleSideResultHtml(round.result, "opponent")}
            </div>
          </div>
          ${summaryRoundCandidatesHtml(battleLog, round)}
        </section>
      `;
    }

    function battleSummaryCardHtml(battleLog) {
      if (!battleLog) {
        return `<div class="validation-item warn">BattleLogを生成できません。</div>`;
      }
      return `
        <div class="battle-summary-card">
          ${battleSummaryHeroHtml(battleLog)}
          <div class="battle-summary-rounds" aria-label="バトル1からバトル5の試合流れ">
            ${[1, 2, 3, 4, 5].map(roundNumber => summaryRoundCardHtml(battleLog, roundNumber)).join("")}
          </div>
        </div>
      `;
    }

    function renderBattleSummaryCard() {
      document.getElementById("battle-summary-card").innerHTML = battleSummaryCardHtml(buildBattleLog());
      updateBattleSummaryPngControls();
    }

    function battlePreviewPayload() {
      return buildBattleLog();
    }

    function renderBattle(validation) {
      if (!state.battle) initializeBattleState();
      const battle = state.battle;
      const currentSubmissionReady = validation.canStartBattle;
      document.getElementById("set-self-submission").disabled = !currentSubmissionReady;
      document.getElementById("set-opponent-submission").disabled = !currentSubmissionReady;
      document.getElementById("set-both-submission").disabled = !currentSubmissionReady;
      document.getElementById("battle-seed").value = battle.seed;
      document.getElementById("battle-submissions").innerHTML = [
        submissionSummaryHtml("自分側提出案", battle.selfSubmission),
        submissionSummaryHtml("相手側提出案", battle.opponentSubmission)
      ].join("");

      const selfReady = canUseBattleSubmission(battle.selfSubmission);
      const opponentReady = canUseBattleSubmission(battle.opponentSubmission);
      if (!selfReady || !opponentReady) {
        document.getElementById("battle-status-grid").innerHTML = `
          <section class="battle-card blocked">
            <h3>ラウンド開始不可</h3>
            <div>自分側・相手側の提出案を3/2/2、7クラスで成立させてください。</div>
          </section>
        `;
        document.getElementById("battle-current-round").innerHTML = "";
        document.getElementById("battle-self-deck-list").innerHTML = "";
        document.getElementById("battle-opponent-deck-list").innerHTML = "";
        document.getElementById("battle-progress").innerHTML = "";
        document.getElementById("battle-summary-card").innerHTML = `
          <div class="validation-item warn">共有用サマリーは、自分側・相手側の提出案が成立すると表示されます。</div>
        `;
        updateBattleSummaryPngControls();
        return;
      }

      renderBattleStatus();
      renderCurrentRound();
      renderBattleDeckLists();
      renderBattleProgress();
      renderBattleSummaryCard();

      document.querySelectorAll("[data-battle-side]").forEach(button => {
        button.addEventListener("click", event => {
          selectBattleDeck(event.currentTarget.dataset.battleSide, event.currentTarget.dataset.battleDeckId);
        });
      });
      document.getElementById("roll-round")?.addEventListener("click", rollBattleRound);
      document.getElementById("manual-self-win")?.addEventListener("click", () => decideBattleRound("self_win"));
      document.getElementById("manual-opponent-win")?.addEventListener("click", () => decideBattleRound("opponent_win"));
    }

    function selectedEntries(submission) {
      return submission.assignments.flatMap(assignment => (
        assignment.deckIds.map(deckId => ({
          role: assignment.role,
          playerId: assignment.playerId,
          deckId,
          player: playerById(assignment.playerId),
          deck: deckById(deckId)
        }))
      ));
    }

    function countBy(values) {
      const counts = new Map();
      values.forEach(value => counts.set(value, (counts.get(value) || 0) + 1));
      return counts;
    }

    function validateSubmission(submission) {
      const errors = [];
      const hardWarnings = [];
      const warnings = [];
      const expectedClasses = (state.dataset?.classDefinitions || []).map(definition => definition.className);
      const entries = selectedEntries(submission);
      let hardCount = 0;
      let trainableCount = 0;
      let missingStatusCount = 0;

      submission.assignments.forEach(assignment => {
        const roleDef = roles.find(role => role.role === assignment.role);
        const expected = roleDef?.expectedDeckCount || 0;
        if (!assignment.playerId) {
          errors.push(`${assignment.role}の担当選手が未選択です。`);
        }
        if (assignment.deckIds.length !== expected) {
          errors.push(`${assignment.role}は${expected}デッキ必要です。現在は${assignment.deckIds.length}デッキです。`);
        }
      });

      const deckCounts = countBy(entries.map(entry => entry.deckId));
      Array.from(deckCounts.entries())
        .filter(([, count]) => count > 1)
        .forEach(([deckId]) => {
          const deck = deckById(deckId);
          errors.push(`同じデッキが複数担当に選ばれています: ${deck?.deckName || deckId}`);
        });

      const classCounts = countBy(entries.map(entry => entry.deck?.className || "").filter(Boolean));
      const missingClasses = expectedClasses.filter(className => !classCounts.has(className));
      const duplicateClasses = Array.from(classCounts.entries())
        .filter(([, count]) => count > 1)
        .map(([className]) => className);
      if (entries.length !== expectedClasses.length) {
        errors.push(`提出案全体は${expectedClasses.length}デッキ必要です。現在は${entries.length}デッキです。`);
      }
      if (missingClasses.length > 0) {
        errors.push(`不足クラス: ${missingClasses.map(classLabel).join("、")}`);
      }
      if (duplicateClasses.length > 0) {
        errors.push(`重複クラス: ${duplicateClasses.map(classLabel).join("、")}`);
      }

      entries.forEach(entry => {
        const playerName = entry.player?.playerName || entry.playerId || "未選択選手";
        const deckName = entry.deck?.deckName || entry.deckId || "未選択デッキ";
        if (!entry.deck) {
          errors.push(`デッキが見つかりません: ${entry.deckId}`);
          return;
        }
        const status = statusFor(entry.playerId, entry.deckId);
        if (!status) {
          missingStatusCount += 1;
          warnings.push(`${entry.role}: ${playerName} / ${deckName} はPlayerDeckStatusがありません。データなし / 要確認です。`);
          return;
        }
        if (status.status === "hard") {
          hardCount += 1;
          hardWarnings.push(`${entry.role}: ${playerName} / ${deckName} はきつそうです。`);
        }
        if (status.status === "trainable") {
          trainableCount += 1;
          warnings.push(`${entry.role}: ${playerName} / ${deckName} は頑張れば可です。`);
        }
      });

      if (trainableCount + missingStatusCount >= 3) {
        warnings.push(`頑張れば可 / データなし が合計${trainableCount + missingStatusCount}件あります。練習負荷・確認負荷が高い提出案です。`);
      }

      return {
        canStartBattle: errors.length === 0,
        errors,
        hardWarnings,
        warnings,
        hardCount,
        trainableCount,
        missingStatusCount,
        selectedDeckCount: entries.length,
        selectedClassCount: classCounts.size,
        missingClasses,
        duplicateClasses
      };
    }

    function previewPayload(submission, validation) {
      return {
        submission,
        battle: battlePreviewPayload(),
        battleLog: buildBattleLog(),
        validation: {
          canStartBattle: validation.canStartBattle,
          errors: validation.errors,
          hardWarnings: validation.hardWarnings,
          warnings: validation.warnings,
          hardCount: validation.hardCount,
          trainableCount: validation.trainableCount,
          missingStatusCount: validation.missingStatusCount,
          selectedDeckCount: validation.selectedDeckCount,
          selectedClassCount: validation.selectedClassCount,
          sourceDataset: datasetUrl
        }
      };
    }

    function safeFilenamePart(value) {
      return String(value || "no-seed").replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "no-seed";
    }

    function battleSummaryCardElement() {
      return document.querySelector("#battle-summary-card .battle-summary-card");
    }

    function setBattleSummaryExportStatus(message, kind = "") {
      const status = document.getElementById("battle-summary-export-status");
      if (!status) return;
      status.textContent = message || "";
      status.className = ["source-note", "battle-summary-export-status", kind].filter(Boolean).join(" ");
    }

    function canRenderBattleSummaryPng(battleLog) {
      return Boolean(battleLog?.finalResult && battleSummaryCardElement() && typeof window.html2canvas === "function");
    }

    function canCopyBattleSummaryPng(battleLog) {
      return Boolean(
        canRenderBattleSummaryPng(battleLog)
        && window.isSecureContext
        && navigator.clipboard?.write
        && typeof window.ClipboardItem === "function"
      );
    }

    function updateBattleSummaryPngControls(message = "", kind = "") {
      const downloadButton = document.getElementById("download-battle-summary-png");
      const copyButton = document.getElementById("copy-battle-summary-png");
      if (!downloadButton || !copyButton) return;
      const battleLog = buildBattleLog();
      const canRender = canRenderBattleSummaryPng(battleLog);
      downloadButton.disabled = isBattleSummaryPngExporting || !canRender;
      copyButton.disabled = isBattleSummaryPngExporting || !canCopyBattleSummaryPng(battleLog);
      if (isBattleSummaryPngExporting) {
        setBattleSummaryExportStatus("PNG生成中です。", "");
        return;
      }
      if (message) {
        setBattleSummaryExportStatus(message, kind);
        return;
      }
      if (!battleLog) {
        setBattleSummaryExportStatus("BattleLogを生成できません。", "warn");
        return;
      }
      if (!battleLog.finalResult) {
        setBattleSummaryExportStatus("完了済みBattleLogでPNG保存できます。", "warn");
        return;
      }
      if (typeof window.html2canvas !== "function") {
        setBattleSummaryExportStatus("PNG保存ライブラリを読み込めません。", "error");
        return;
      }
      setBattleSummaryExportStatus("", "");
    }

    function battleSummaryPngTimestamp(date = new Date()) {
      const pad = value => String(value).padStart(2, "0");
      return [
        date.getFullYear(),
        pad(date.getMonth() + 1),
        pad(date.getDate())
      ].join("") + "-" + [pad(date.getHours()), pad(date.getMinutes()), pad(date.getSeconds())].join("");
    }

    function battleSummaryPngFilename() {
      return `ps-battle-summary-${battleSummaryPngTimestamp()}.png`;
    }

    function canvasToPngBlob(canvas) {
      return new Promise((resolve, reject) => {
        canvas.toBlob(blob => {
          if (blob) {
            resolve(blob);
            return;
          }
          reject(new Error("CanvasからPNGを生成できませんでした。"));
        }, "image/png");
      });
    }

    async function battleSummaryCardToPngBlob(card) {
      if (typeof window.html2canvas !== "function") {
        throw new Error("PNG保存ライブラリを読み込めません。");
      }
      if (!window.Blob || !window.URL || !HTMLCanvasElement.prototype.toBlob) {
        throw new Error("このブラウザはPNG保存に必要なAPIに対応していません。");
      }
      const rect = card.getBoundingClientRect();
      const width = Math.ceil(rect.width);
      const height = Math.ceil(rect.height);
      if (!width || !height) {
        throw new Error("サマリーカードのサイズを取得できませんでした。");
      }

      const scale = Math.max(2, Math.ceil(window.devicePixelRatio || 1));
      const canvas = await window.html2canvas(card, {
        backgroundColor: "#ffffff",
        scale,
        useCORS: true,
        allowTaint: false,
        logging: false,
        imageTimeout: 1000,
        onclone: clonedDocument => {
          const clonedCard = clonedDocument.querySelector("#battle-summary-card .battle-summary-card");
          if (!clonedCard) return;
          clonedCard.style.width = `${width}px`;
          clonedCard.style.margin = "0";
          clonedCard.querySelectorAll("img").forEach(image => image.remove());
        }
      });
      return await canvasToPngBlob(canvas);
    }

    function downloadBlob(filename, blob) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function downloadJson(filename, payload) {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      downloadBlob(filename, blob);
    }

    function downloadBattleLogJson() {
      const battleLog = buildBattleLog();
      if (!battleLog) return;
      downloadJson(`battle-log-${safeFilenamePart(battleLog.seed)}.json`, battleLog);
    }

    async function copyPngBlobToClipboard(blob) {
      if (!window.isSecureContext || !navigator.clipboard?.write || typeof window.ClipboardItem !== "function") {
        throw new Error("このブラウザは画像コピーに対応していません。");
      }
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob })
      ]);
    }

    async function downloadBattleSummaryPng() {
      const battleLog = buildBattleLog();
      const card = battleSummaryCardElement();
      if (!battleLog) {
        updateBattleSummaryPngControls("BattleLogを生成できないためPNG保存できません。", "error");
        return;
      }
      if (!battleLog.finalResult) {
        updateBattleSummaryPngControls("完了済みBattleLogでPNG保存できます。", "warn");
        return;
      }
      if (!card) {
        updateBattleSummaryPngControls("保存対象のサマリーカードが見つかりません。", "error");
        return;
      }
      isBattleSummaryPngExporting = true;
      updateBattleSummaryPngControls();
      try {
        const blob = await battleSummaryCardToPngBlob(card);
        downloadBlob(battleSummaryPngFilename(), blob);
        isBattleSummaryPngExporting = false;
        updateBattleSummaryPngControls("PNGを保存しました。", "ok");
      } catch (error) {
        console.error(error);
        isBattleSummaryPngExporting = false;
        updateBattleSummaryPngControls(`PNG生成に失敗しました。${error.message || "ブラウザの画像化処理を確認してください。"}`, "error");
      }
    }

    async function copyBattleSummaryPng() {
      const battleLog = buildBattleLog();
      const card = battleSummaryCardElement();
      if (!battleLog) {
        updateBattleSummaryPngControls("BattleLogを生成できないため画像コピーできません。", "error");
        return;
      }
      if (!battleLog.finalResult) {
        updateBattleSummaryPngControls("完了済みBattleLogで画像コピーできます。", "warn");
        return;
      }
      if (!card) {
        updateBattleSummaryPngControls("コピー対象のサマリーカードが見つかりません。", "error");
        return;
      }
      isBattleSummaryPngExporting = true;
      updateBattleSummaryPngControls();
      try {
        const blob = await battleSummaryCardToPngBlob(card);
        await copyPngBlobToClipboard(blob);
        isBattleSummaryPngExporting = false;
        updateBattleSummaryPngControls("画像をコピーしました。", "ok");
      } catch (error) {
        console.error(error);
        isBattleSummaryPngExporting = false;
        updateBattleSummaryPngControls(`画像コピーに失敗しました。${error.message || "ブラウザのクリップボード権限を確認してください。"}`, "error");
      }
    }

    function renderDataSummary() {
      const dataset = state.dataset;
      const statuses = dataset?.playerDeckStatuses || [];
      document.getElementById("data-summary").innerHTML = [
        `${dataset?.decks?.length || 0}デッキ`,
        `${dataset?.players?.length || 0}選手`,
        `${statuses.length} status行`
        ].map(label => `<span class="badge">${escapeHtml(label)}</span>`).join("");
        document.getElementById("dataset-meta").textContent = "サンプルデータ読込済み";
        document.getElementById("debug-dataset-meta").textContent =
          `${datasetUrl} を読み込みました。schemaVersion: ${dataset?.schemaVersion || "不明"}`;
    }

    function renderClassCoverage(validation) {
      const classCounts = countBy(selectedEntries(currentSubmission()).map(entry => entry.deck?.className).filter(Boolean));
      document.getElementById("class-coverage").innerHTML = (state.dataset?.classDefinitions || []).map(definition => {
        const count = classCounts.get(definition.className) || 0;
        const stateClass = count === 1 ? "selected" : count === 0 ? "missing" : "duplicate";
        const stateLabel = count === 1 ? "選択済み" : count === 0 ? "未選択" : `重複 ${count}`;
        return `<span class="class-coverage-badge ${escapeHtml(classCssClass(definition.className))} ${stateClass}" title="${escapeHtml(definition.displayName)}: ${escapeHtml(stateLabel)}">${escapeHtml(definition.className)}</span>`;
      }).join("");
    }

    function renderRolePanel(roleDef) {
      const assignment = state.assignments[roleDef.role] || { playerId: "", deckIds: [] };
      const selectedCount = assignment.deckIds.length;
      const invalid = selectedCount !== roleDef.expectedDeckCount;
      const selectedPlayer = playerById(assignment.playerId);
      const playerOptions = (state.dataset?.players || []).map(player => {
        return `
          <option value="${escapeHtml(player.playerId)}"${player.playerId === assignment.playerId ? " selected" : ""}>
            ${escapeHtml(player.playerName)}
          </option>
        `;
      }).join("");
      const deckOptions = (state.dataset?.classDefinitions || [])
        .filter(definition => shouldShowClassForRole(roleDef.role, definition.className))
        .map(definition => {
          const classDecks = decksByClass(definition.className);
          const selectedHere = selectedClassesForRole(roleDef.role).includes(definition.className);
          const [stateKind, stateLabel] = classGroupState(roleDef.role, definition.className);
          const deckRows = classDecks.map(deck => {
            const checked = assignment.deckIds.includes(deck.deckId);
            return `
              <div class="deck-option ${checked ? "selected" : ""} ${escapeHtml(classCssClass(deck.className))}">
                <label class="deck-option-pick">
                  <input type="checkbox" data-role-deck="${escapeHtml(roleDef.role)}" data-deck-id="${escapeHtml(deck.deckId)}"${checked ? " checked" : ""}>
                  <span class="deck-main">
                    <span class="deck-name"><strong>${escapeHtml(deck.deckName)}</strong></span>
                  </span>
                </label>
                ${deckStatusDetailsHtml(deck.deckId, assignment.playerId)}
              </div>
            `;
          }).join("") || `<div class="empty">このクラスの候補はありません。</div>`;
          return `
            <div class="deck-class-group ${selectedHere ? "selected-class" : ""} ${escapeHtml(classCssClass(definition.className))}">
              <div class="deck-class-group-head">
                <div class="badge-row">
                  ${compactClassBadgeHtml(definition.className)}
                  <span class="count">候補 ${classDecks.length}</span>
                </div>
                ${stateLabel ? `<span class="badge ${stateKind}">${escapeHtml(stateLabel)}</span>` : ""}
              </div>
              <div class="deck-options">${deckRows}</div>
            </div>
          `;
        }).join("");

      return `
        <section class="role-panel ${invalid ? "invalid" : ""}">
          <div class="role-title">
            <h3>${escapeHtml(roleDef.role)}担当</h3>
            <span class="badge ${invalid ? "warn" : "ok"}">${selectedCount}/${roleDef.expectedDeckCount}デッキ</span>
          </div>
          <label class="field">担当選手
            <span class="player-select-row">
              ${playerAvatarHtml(selectedPlayer)}
              <select data-role-player="${escapeHtml(roleDef.role)}">
                ${playerOptions}
              </select>
            </span>
          </label>
          ${roleClassSummaryHtml(roleDef)}
          <div class="deck-options">${deckOptions}</div>
        </section>
      `;
    }

    function renderBuilder(validation) {
      document.getElementById("submission-side").value = state.side;
      document.getElementById("role-grid").innerHTML = roles.map(renderRolePanel).join("");
      renderClassCoverage(validation);

      document.querySelectorAll("[data-role-player]").forEach(select => {
        select.addEventListener("change", event => {
          const role = event.target.dataset.rolePlayer;
          state.assignments[role].playerId = event.target.value;
          render();
        });
      });

      document.querySelectorAll("[data-role-deck]").forEach(input => {
        input.addEventListener("change", event => {
          const role = event.target.dataset.roleDeck;
          const deckId = event.target.dataset.deckId;
          const deckIds = new Set(state.assignments[role].deckIds || []);
          if (event.target.checked) {
            deckIds.add(deckId);
          } else {
            deckIds.delete(deckId);
          }
          state.assignments[role].deckIds = Array.from(deckIds).sort(byDeckOrder);
          render();
        });
      });
    }

    function renderValidation(validation) {
      const badge = document.getElementById("validity-badge");
      badge.className = `badge ${validation.canStartBattle ? "ok" : "warn"}`;
      badge.textContent = validation.canStartBattle ? "提出条件OK" : "提出案未成立";

      const ruleItems = validation.errors.map(message => ["error", message]);
      const operationItems = [
        ...validation.hardWarnings.map(message => ["hard", message]),
        ...validation.warnings.map(message => ["warn", message])
      ];

        const sectionHtml = (title, items, emptyText) => `
          <section class="validation-section">
            <div class="validation-section-title">
              <h3>${escapeHtml(title)}</h3>
            </div>
            ${items.length
              ? items.map(([kind, message]) => `<div class="validation-item ${kind}">${escapeHtml(message)}</div>`).join("")
              : `<div class="validation-item ok">${escapeHtml(emptyText)}</div>`}
          </section>
        `;

      document.getElementById("validation-list").innerHTML = [
          sectionHtml(
            "ルール上の制約",
            ruleItems,
            "3/2/2、7クラス、未選択、重複に問題はありません。"
          ),
          sectionHtml(
            "運用上の注意",
            operationItems,
            "きつそう / 頑張れば可 / データなし の確認対象はありません。"
          )
      ].join("");
    }

    function renderDeckReference() {
      const rows = (state.dataset?.decks || []).map(deck => `
          <tr>
            <td>${classBadgeHtml(deck.className)}</td>
            <td><strong>${escapeHtml(deck.deckName)}</strong><div class="source-note">className: ${escapeHtml(deck.className)} / deckId: ${escapeHtml(deck.deckId)}</div></td>
          <td>${escapeHtml(deck.source || "")}</td>
          <td>${escapeHtml(deck.note || "")}</td>
        </tr>
      `).join("");
      document.getElementById("deck-reference").innerHTML = `
        <table>
          <thead><tr><th>クラス</th><th>デッキ</th><th>source</th><th>メモ</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderPlayerReference() {
      const decks = state.dataset?.decks || [];
      const rows = (state.dataset?.players || []).map(player => {
        const playerStatuses = decks.map(deck => statusFor(player.playerId, deck.deckId));
        const hardCount = playerStatuses.filter(status => status?.status === "hard").length;
        const trainableCount = playerStatuses.filter(status => status?.status === "trainable").length;
        const missingCount = playerStatuses.filter(status => !status).length;
        return `
          <tr>
            <td><strong>${escapeHtml(player.playerName)}</strong><div class="source-note">${escapeHtml(player.playerId)}</div></td>
            <td>${escapeHtml(player.team || "")}</td>
            <td>
              <div class="badge-row">
                <span class="badge bad">きつそう ${hardCount}</span>
                <span class="badge warn">頑張れば可 ${trainableCount}</span>
                <span class="badge ${missingCount ? "warn" : "ok"}">データなし ${missingCount}</span>
              </div>
            </td>
            <td>${escapeHtml(player.note || "")}</td>
          </tr>
        `;
      }).join("");
      document.getElementById("player-reference").innerHTML = `
        <table>
          <thead><tr><th>選手</th><th>チーム</th><th>PlayerDeckStatus概況</th><th>メモ</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderReferences() {
      renderDeckReference();
      renderPlayerReference();
    }

    function render() {
      if (!state.dataset) return;
      const submission = currentSubmission();
      const validation = validateSubmission(submission);
      renderDataSummary();
      renderBuilder(validation);
      renderValidation(validation);
      renderBattle(validation);
      renderReferences();
      document.getElementById("json-preview").textContent =
        JSON.stringify(previewPayload(submission, validation), null, 2);
    }

    async function loadDataset() {
      const response = await fetch(datasetUrl);
      if (!response.ok) {
        throw new Error(`sample datasetを読み込めませんでした: HTTP ${response.status}`);
      }
      state.dataset = await response.json();
      loadSampleSubmission();
      initializeBattleState();
      render();
    }

    document.getElementById("submission-side").addEventListener("change", event => {
      state.side = event.target.value;
      render();
    });

    document.getElementById("reset-sample").addEventListener("click", () => {
      loadSampleSubmission();
      render();
    });

    document.getElementById("clear-decks").addEventListener("click", clearDeckSelections);

    document.getElementById("set-self-submission").addEventListener("click", () => {
      setBattleSubmission("self", currentSubmission());
    });

    document.getElementById("set-opponent-submission").addEventListener("click", () => {
      setBattleSubmission("opponent", currentSubmission());
    });

    document.getElementById("set-both-submission").addEventListener("click", () => {
      setBattleSubmissionForBothSides(currentSubmission());
    });

    document.getElementById("reset-battle-progress").addEventListener("click", () => {
      resetBattleProgress();
    });

    document.getElementById("download-battle-log").addEventListener("click", downloadBattleLogJson);
    document.getElementById("download-battle-summary-png").addEventListener("click", downloadBattleSummaryPng);
    document.getElementById("copy-battle-summary-png").addEventListener("click", copyBattleSummaryPng);

    document.getElementById("battle-seed").addEventListener("input", event => {
      if (!state.battle) return;
      state.battle.seed = event.target.value || "sample-seed-001";
      render();
    });

    loadDataset().catch(error => {
      document.getElementById("dataset-meta").textContent = error.message;
      document.getElementById("validity-badge").className = "badge bad";
      document.getElementById("validity-badge").textContent = "読み込み失敗";
      document.getElementById("validation-list").innerHTML =
        `<div class="validation-item hard">${escapeHtml(error.message)}</div>`;
    });
  </script>
</body>
</html>
"""


def read_ps_simulator_sample_dataset(path: Path = PS_SIMULATOR_SAMPLE_DATASET_PATH) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def render_ps_simulator_html() -> str:
    return PS_SIMULATOR_HTML


def write_ps_simulator_assets(
    out_dir: Path,
    dataset_path: Path = PS_SIMULATOR_SAMPLE_DATASET_PATH,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ps-simulator.html").write_text(render_ps_simulator_html(), encoding="utf-8")

    public_vendor_path = out_dir / HTML2CANVAS_PUBLIC_PATH
    public_vendor_path.parent.mkdir(parents=True, exist_ok=True)
    public_vendor_path.write_bytes(HTML2CANVAS_VENDOR_PATH.read_bytes())
    (out_dir / HTML2CANVAS_PUBLIC_LICENSE_PATH).write_text(
        HTML2CANVAS_VENDOR_LICENSE_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    dataset = read_ps_simulator_sample_dataset(dataset_path)
    public_dataset_path = out_dir / PS_SIMULATOR_PUBLIC_DATASET_PATH
    public_dataset_path.parent.mkdir(parents=True, exist_ok=True)
    public_dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
