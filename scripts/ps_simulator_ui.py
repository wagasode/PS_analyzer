from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
PS_SIMULATOR_SAMPLE_DATASET_PATH = ROOT_DIR / "data" / "ps_simulator" / "sample_dataset.json"
PS_SIMULATOR_PUBLIC_DATASET_PATH = Path("data") / "ps_simulator" / "sample_dataset.json"
ROUND_ROLE_BY_NUMBER = {1: "A", 2: "B", 3: "C"}


def submission_deck_ids(submission: dict[str, Any]) -> list[str]:
    deck_ids: list[str] = []
    for assignment in submission.get("assignments", []):
        deck_ids.extend(assignment.get("deckIds", []))
    return deck_ids


def battle_candidate_deck_ids_for_round(
    submission: dict[str, Any],
    round_number: int,
    used_deck_ids: set[str],
) -> list[str]:
    if round_number in ROUND_ROLE_BY_NUMBER:
        role = ROUND_ROLE_BY_NUMBER[round_number]
        for assignment in submission.get("assignments", []):
            if assignment.get("role") == role:
                return [deck_id for deck_id in assignment.get("deckIds", []) if deck_id not in used_deck_ids]
        return []
    if round_number in {4, 5}:
        return [deck_id for deck_id in submission_deck_ids(submission) if deck_id not in used_deck_ids]
    raise ValueError(f"unsupported round_number: {round_number}")


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
    h3 {
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

    .meta,
    .hint,
    .count {
      color: var(--muted);
      font-size: 14px;
    }

    .meta {
      margin-top: 8px;
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
      grid-template-columns: auto minmax(0, 1fr);
      gap: 9px;
      align-items: start;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px;
      background: var(--panel);
    }

    .deck-option.selected {
      border-color: var(--deck-class-border, var(--accent));
      background: linear-gradient(90deg, var(--deck-class-border, var(--accent)) 0 5px, var(--deck-class-row, var(--accent-soft)) 5px);
    }

    .deck-option input {
      width: 16px;
      height: 16px;
      margin-top: 3px;
      accent-color: var(--accent);
    }

    .deck-main {
      display: grid;
      gap: 5px;
      min-width: 0;
    }

    .deck-name {
      display: flex;
      align-items: center;
      gap: 7px;
      flex-wrap: wrap;
      overflow-wrap: anywhere;
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

    .status-badge.confident,
    .status-badge.available {
      background: var(--accent-soft);
      color: var(--accent);
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
    .battle-deck-lists {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .battle-main-grid {
      display: grid;
      grid-template-columns: minmax(420px, 1.15fr) minmax(230px, 0.55fr) minmax(330px, 0.8fr);
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
      grid-template-columns: auto minmax(0, 1fr);
      gap: 8px;
      align-items: center;
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
      gap: 7px;
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
      gap: 6px;
      max-width: 100%;
      min-width: 0;
      min-height: 26px;
      border: 1px solid var(--deck-class-border, var(--border));
      border-radius: 7px;
      padding: 3px 7px;
      background: var(--deck-class-soft, #fff);
      color: var(--deck-class-color, var(--text));
      font-size: 12px;
      line-height: 1.25;
      white-space: normal;
      overflow-wrap: anywhere;
    }

    .deck-token strong {
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

    .deck-token-class {
      color: var(--deck-class-color, var(--muted));
      font-weight: 700;
      min-width: 0;
      overflow-wrap: anywhere;
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
      justify-content: flex-start;
      min-height: 0;
      width: 100%;
      padding: 10px;
      border-color: var(--deck-class-border, var(--border));
      background: linear-gradient(90deg, var(--deck-class-border, var(--border)) 0 5px, #fff 5px);
      text-align: left;
      white-space: normal;
    }

    .choice-button.selected {
      border-color: var(--deck-class-color, var(--accent));
      background: linear-gradient(90deg, var(--deck-class-color, var(--accent)) 0 5px, var(--deck-class-row, var(--accent-soft)) 5px);
      color: var(--text);
      font-weight: 700;
    }

    .choice-button:disabled {
      cursor: not-allowed;
      opacity: 0.62;
      box-shadow: none;
    }

    .progress-item {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
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
      margin-top: 6px;
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
      .battle-deck-lists {
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
      <a class="button" href="index.html">配信レポートへ戻る</a>
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
            <h2 id="battle-title">バトル進行シミュレータ</h2>
          </div>
          <span class="badge" id="battle-state-badge">未開始</span>
        </div>
        <div class="panel-body stack">
          <div class="battle-controls">
            <button class="primary" id="set-self-submission" type="button">現在の提出案を自分側にセット</button>
            <button id="set-opponent-submission" type="button">現在の提出案を相手側にセット</button>
            <button id="reset-battle-sample" type="button">サンプルで両側リセット</button>
            <button id="reset-battle-progress" type="button">バトルをやり直す</button>
          </div>
          <div class="battle-submissions" id="battle-submissions"></div>
          <div class="battle-main-grid">
            <div class="battle-main-column">
              <div class="battle-status-grid" id="battle-status-grid"></div>
              <div class="battle-round" id="battle-current-round"></div>
            </div>
            <div class="battle-main-column">
              <div class="battle-progress" id="battle-progress"></div>
            </div>
            <div class="battle-main-column">
              <div class="battle-deck-lists" id="battle-deck-lists"></div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>

  <script>
    const roles = [
      { role: "A", expectedDeckCount: 3 },
      { role: "B", expectedDeckCount: 2 },
      { role: "C", expectedDeckCount: 2 }
    ];
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

    function avatarHtml(name, imageUrl) {
      const fallback = escapeHtml(initials(name));
      const image = imageUrl
        ? `<img src="${escapeHtml(imageUrl)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`
        : "";
      return `<span class="player-avatar" aria-hidden="true">${image}<span>${fallback}</span></span>`;
    }

    function playerAvatarHtml(player) {
      return avatarHtml(player?.playerName || "?", playerIconUrl(player));
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

    function roleClassSummaryHtml(role) {
      const selectedDecks = (assignmentForRole(role).deckIds || []).map(deckById).filter(Boolean);
      if (selectedDecks.length === 0) {
        return `<div class="role-class-summary">選択クラスなし</div>`;
      }
      return `
          <div class="role-class-summary">
            選択中:
            ${selectedDecks.map(deck => `${escapeHtml(deck.deckName)} ${classBadgeHtml(deck.className)}`).join(" ")}
          </div>
      `;
    }

    function classGroupState(role, className) {
      const selectedRoles = selectedRolesForClass(className);
      const selectedHere = selectedRoles.includes(role);
      if (selectedHere && selectedRoles.length > 1) {
        return ["bad", `重複: ${selectedRoles.join("/")}`];
      }
      if (selectedHere) {
        return ["ok", "この担当で選択中"];
      }
      return ["", "未選択"];
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

    function statusNoteHtml(status) {
      if (!status) {
        return `<div class="status-note">PlayerDeckStatus 行なし。データなし / 要確認として扱います。</div>`;
      }
      const parts = [`練習負荷 ${Number(status.practiceCost || 0)}`];
      if (status.note) parts.push(status.note);
      return `<div class="status-note">${escapeHtml(parts.join(" / "))}</div>`;
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

    function initializeBattleState() {
      state.battle = {
        seed: "sample-seed-001",
        selfSubmission: sampleSubmissionForSide("self"),
        opponentSubmission: sampleSubmissionForSide("opponent"),
        rounds: [],
        score: { self: 0, opponent: 0 },
        isComplete: false,
        winner: ""
      };
      resetBattleProgress(false);
    }

    function assignmentByRole(submission, role) {
      return (submission?.assignments || []).find(assignment => assignment.role === role) || null;
    }

    function submissionDeckIds(submission) {
      return (submission?.assignments || []).flatMap(assignment => assignment.deckIds || []);
    }

    function candidateDeckIdsForRound(submission, roundNumber, usedDeckIds) {
      const used = new Set(usedDeckIds || []);
      if (roundNumber === 1) {
        return [...(assignmentByRole(submission, "A")?.deckIds || [])].filter(deckId => !used.has(deckId));
      }
      if (roundNumber === 2) {
        return [...(assignmentByRole(submission, "B")?.deckIds || [])].filter(deckId => !used.has(deckId));
      }
      if (roundNumber === 3) {
        return [...(assignmentByRole(submission, "C")?.deckIds || [])].filter(deckId => !used.has(deckId));
      }
      if (roundNumber === 4 || roundNumber === 5) {
        return submissionDeckIds(submission).filter(deckId => !used.has(deckId));
      }
      return [];
    }

    function scoreFromRounds(rounds) {
      return rounds.reduce((score, round) => {
        if (round.result === "self_win") score.self += 1;
        if (round.result === "opponent_win") score.opponent += 1;
        return score;
      }, { self: 0, opponent: 0 });
    }

    function usedDeckIdsForSide(side) {
      return (state.battle?.rounds || [])
        .filter(round => round.result)
        .map(round => side === "self" ? round.selfSelectedDeckId : round.opponentSelectedDeckId)
        .filter(Boolean);
    }

    function createBattleRound(roundNumber) {
      const selfUsed = usedDeckIdsForSide("self");
      const opponentUsed = usedDeckIdsForSide("opponent");
      return {
        roundNumber,
        selfCandidateDeckIds: candidateDeckIdsForRound(state.battle.selfSubmission, roundNumber, selfUsed),
        opponentCandidateDeckIds: candidateDeckIdsForRound(state.battle.opponentSubmission, roundNumber, opponentUsed),
        selfSelectedDeckId: "",
        opponentSelectedDeckId: "",
        selfWinRate: 0.5,
        winRateNote: "選択前です。",
        result: "",
        selfUsedDeckIds: [...selfUsed],
        opponentUsedDeckIds: [...opponentUsed],
        score: { ...state.battle.score }
      };
    }

    function resetBattleProgress(shouldRender = true) {
      if (!state.battle) return;
      state.battle.rounds = [];
      state.battle.score = { self: 0, opponent: 0 };
      state.battle.isComplete = false;
      state.battle.winner = "";
      state.battle.rounds.push(createBattleRound(1));
      if (shouldRender) render();
    }

    function resetBattleToSamples() {
      if (!state.dataset) return;
      const seed = state.battle?.seed || "sample-seed-001";
      state.battle = {
        seed,
        selfSubmission: sampleSubmissionForSide("self"),
        opponentSubmission: sampleSubmissionForSide("opponent"),
        rounds: [],
        score: { self: 0, opponent: 0 },
        isComplete: false,
        winner: ""
      };
      resetBattleProgress();
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
          note: "sampleMatchupsの暫定値を使用しています。"
        };
      }
      const reverseMatchup = (state.dataset?.sampleMatchups || []).find(item => (
        item.deckIdA === opponentDeckId && item.deckIdB === selfDeckId
      ));
      if (reverseMatchup) {
        return {
          winRate: 1 - Number(reverseMatchup.winRateForA),
          note: "sampleMatchupsの逆向き暫定値を使用しています。"
        };
      }
      return {
        winRate: 0.5,
        note: "相性表未接続のため暫定0.5を使用しています。"
      };
    }

    function updateRoundWinRate(round) {
      if (!round.selfSelectedDeckId || !round.opponentSelectedDeckId) {
        round.selfWinRate = 0.5;
        round.winRateNote = "選択前です。";
        return;
      }
      const lookup = lookupSelfWinRate(round.selfSelectedDeckId, round.opponentSelectedDeckId);
      round.selfWinRate = lookup.winRate;
      round.winRateNote = lookup.note;
    }

    function setBattleSubmission(side, submission) {
      if (!state.battle) initializeBattleState();
      state.battle[side === "self" ? "selfSubmission" : "opponentSubmission"] =
        normalizeSubmissionForSide(submission, side);
      resetBattleProgress();
    }

    function canUseBattleSubmission(submission) {
      return validateSubmission(submission).canStartBattle;
    }

    function selectBattleDeck(side, deckId) {
      const round = activeBattleRound();
      if (!round) return;
      const candidates = side === "self" ? round.selfCandidateDeckIds : round.opponentCandidateDeckIds;
      const used = new Set(usedDeckIdsForSide(side));
      if (!candidates.includes(deckId) || used.has(deckId)) return;
      if (side === "self") {
        round.selfSelectedDeckId = deckId;
      } else {
        round.opponentSelectedDeckId = deckId;
      }
      updateRoundWinRate(round);
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
      const roll = deterministicUnitInterval([
        state.battle.seed,
        round.roundNumber,
        round.selfSelectedDeckId,
        round.opponentSelectedDeckId
      ].join("|"));
      decideBattleRound(roll < round.selfWinRate ? "self_win" : "opponent_win");
    }

    function decideBattleRound(result) {
      const round = activeBattleRound();
      if (!round || !round.selfSelectedDeckId || !round.opponentSelectedDeckId) return;
      updateRoundWinRate(round);
      round.result = result;
      state.battle.score = scoreFromRounds(state.battle.rounds);
      round.selfUsedDeckIds = usedDeckIdsForSide("self");
      round.opponentUsedDeckIds = usedDeckIdsForSide("opponent");
      round.score = { ...state.battle.score };

      if (state.battle.score.self >= 3 || state.battle.score.opponent >= 3 || round.roundNumber >= 5) {
        state.battle.isComplete = true;
        state.battle.winner = state.battle.score.self > state.battle.score.opponent ? "self" : "opponent";
      } else {
        state.battle.rounds.push(createBattleRound(round.roundNumber + 1));
      }
      render();
    }

    function formatWinRate(value) {
      return `${Math.round(Number(value) * 100)}%`;
    }

    function resultLabel(result) {
      if (result === "self_win") return "自分勝ち";
      if (result === "opponent_win") return "相手勝ち";
      return "未決定";
    }

    function deckLabel(deckId) {
      const deck = deckById(deckId);
      return deck ? deck.deckName : deckId || "未選択";
    }

    function deckTokenHtml(deckId) {
      const deck = deckById(deckId);
      if (!deck) {
        return `<span class="deck-token"><strong>${escapeHtml(deckId || "未選択")}</strong></span>`;
      }
      const definition = classDefinition(deck.className);
      const className = definition?.displayName || deck.className || "不明";
      const classCode = definition?.className || deck.className || "?";
      return `
        <span class="deck-token ${escapeHtml(classCssClass(deck.className))}" title="deckId: ${escapeHtml(deck.deckId)}">
          <span class="deck-token-code" aria-hidden="true">${escapeHtml(classCode)}</span>
          <strong>${escapeHtml(deck.deckName)}</strong>
          <span class="deck-token-class">${escapeHtml(className)}</span>
        </span>
      `;
    }

    function deckTokenListHtml(deckIds) {
      if (!deckIds.length) {
        return `<span class="source-note">なし</span>`;
      }
      return `<div class="deck-token-row">${deckIds.map(deckTokenHtml).join("")}</div>`;
    }

    function submissionSummaryHtml(label, submission) {
      const validation = validateSubmission(submission);
      const assignments = roles.map(roleDef => {
        const assignment = assignmentByRole(submission, roleDef.role) || {};
        const player = playerById(assignment.playerId);
        const deckIds = assignment.deckIds || [];
        return `
          <div class="battle-assignment">
            ${playerAvatarHtml(player)}
            <div class="battle-assignment-main">
              <div class="battle-assignment-head">
                <span class="badge">${escapeHtml(roleDef.role)}</span>
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
            <span class="badge ${validation.canStartBattle ? "ok" : "warn"}">
              ${validation.canStartBattle ? "使用可能" : "提出案未成立"}
            </span>
          </div>
          <div class="battle-assignment-list">${assignments}</div>
        </section>
      `;
    }

    function renderChoiceList(side, round) {
      const candidates = side === "self" ? round.selfCandidateDeckIds : round.opponentCandidateDeckIds;
      const selectedDeckId = side === "self" ? round.selfSelectedDeckId : round.opponentSelectedDeckId;
      const used = new Set(usedDeckIdsForSide(side));
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
            return `
              <button
                class="choice-button ${deck ? escapeHtml(classCssClass(deck.className)) : ""} ${selected ? "selected" : ""}"
                type="button"
                data-battle-side="${escapeHtml(side)}"
                data-battle-deck-id="${escapeHtml(deckId)}"
                ${disabled ? "disabled" : ""}
              >
                ${deckTokenHtml(deckId)}
                ${usedDeck ? `<span class="badge warn">使用済み</span>` : ""}
              </button>
            `;
          }).join("")}
        </div>
      `;
    }

    function renderSideDeckStatus(title, usedDeckIds, remainingDeckIds) {
      return `
        <section class="battle-list">
          <h3>${escapeHtml(title)}</h3>
          <div class="deck-list-group">
            <div class="deck-class-group-head">
              <strong>使用済みデッキ</strong>
              <span class="badge">${usedDeckIds.length}デッキ</span>
            </div>
            ${deckTokenListHtml(usedDeckIds)}
          </div>
          <div class="deck-list-group">
            <div class="deck-class-group-head">
              <strong>残りデッキ</strong>
              <span class="badge">${remainingDeckIds.length}デッキ</span>
            </div>
            ${deckTokenListHtml(remainingDeckIds)}
          </div>
        </section>
      `;
    }

    function renderBattleStatus() {
      const battle = state.battle;
      const active = activeBattleRound();
      const currentRoundLabel = battle.isComplete ? "終了済み" : `R${active?.roundNumber || 1}`;
      const resultText = battle.isComplete
        ? `最終結果: ${battle.winner === "self" ? "自分勝利" : "相手勝利"}`
        : "進行中";
      document.getElementById("battle-state-badge").className = `badge ${battle.isComplete ? "ok" : "warn"}`;
      document.getElementById("battle-state-badge").textContent = battle.isComplete ? "マッチ終了" : "進行中";
      document.getElementById("battle-status-grid").innerHTML = [
        `
          <section class="battle-card ${battle.isComplete ? "ended" : ""}">
            <h3>現在スコア</h3>
            <div class="scoreline">自分 ${battle.score.self} - ${battle.score.opponent} 相手</div>
            <div class="source-note">現在ラウンド: ${escapeHtml(currentRoundLabel)}</div>
          </section>
        `,
        `
          <section class="battle-card ${battle.isComplete ? "ended" : ""}">
            <h3>マッチ状態</h3>
            <div><strong>${escapeHtml(resultText)}</strong></div>
            <div class="source-note">3勝先取で終了します。</div>
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
            <h3>マッチ終了</h3>
            <div class="scoreline">最終結果: ${battle.winner === "self" ? "自分勝利" : "相手勝利"}</div>
          </div>
        `;
        return;
      }
      const canDecide = active.selfSelectedDeckId && active.opponentSelectedDeckId && !active.result;
      document.getElementById("battle-current-round").innerHTML = `
        <div class="deck-class-group-head">
          <div>
            <h3>R${active.roundNumber} 選出</h3>
            <div class="source-note">暫定勝率: ${formatWinRate(active.selfWinRate)} / ${escapeHtml(active.winRateNote)}</div>
          </div>
          <span class="badge">${escapeHtml(resultLabel(active.result))}</span>
        </div>
        <div class="battle-round-grid">
          <section class="battle-card">
            <div class="deck-class-group-head">
              <h3>自分側候補</h3>
              <span class="badge">${active.selfCandidateDeckIds.length}デッキ</span>
            </div>
            ${renderChoiceList("self", active)}
          </section>
          <section class="battle-card">
            <div class="deck-class-group-head">
              <h3>相手側候補</h3>
              <span class="badge">${active.opponentCandidateDeckIds.length}デッキ</span>
            </div>
            ${renderChoiceList("opponent", active)}
          </section>
        </div>
        <div class="battle-controls">
          <button class="primary" id="roll-round" type="button" ${canDecide ? "" : "disabled"}>抽選</button>
          <button id="manual-self-win" type="button" ${canDecide ? "" : "disabled"}>手動: 自分勝ち</button>
          <button id="manual-opponent-win" type="button" ${canDecide ? "" : "disabled"}>手動: 相手勝ち</button>
        </div>
      `;
    }

    function renderBattleDeckLists() {
      const selfUsed = usedDeckIdsForSide("self");
      const opponentUsed = usedDeckIdsForSide("opponent");
      const selfRemaining = submissionDeckIds(state.battle.selfSubmission).filter(deckId => !selfUsed.includes(deckId));
      const opponentRemaining = submissionDeckIds(state.battle.opponentSubmission).filter(deckId => !opponentUsed.includes(deckId));
      document.getElementById("battle-deck-lists").innerHTML = [
        renderSideDeckStatus("自分側 デッキ状況", selfUsed, selfRemaining),
        renderSideDeckStatus("相手側 デッキ状況", opponentUsed, opponentRemaining)
      ].join("");
    }

    function renderBattleProgress() {
      const rows = [1, 2, 3, 4, 5].map(roundNumber => {
        const round = state.battle.rounds.find(item => item.roundNumber === roundNumber);
        const isCurrent = activeBattleRound()?.roundNumber === roundNumber;
        if (!round) {
          return `<div class="progress-item"><strong>R${roundNumber}</strong>: 未選択</div>`;
        }
        const className = round.result ? "progress-item done" : isCurrent ? "progress-item current" : "progress-item";
        return `
          <div class="${className}">
            <strong>R${roundNumber}</strong>
            <div class="progress-match">
              <span>自分</span>
              ${deckTokenHtml(round.selfSelectedDeckId)}
              <span>vs 相手</span>
              ${deckTokenHtml(round.opponentSelectedDeckId)}
              <span class="badge">${escapeHtml(resultLabel(round.result))}</span>
            </div>
          </div>
        `;
      }).join("");
      document.getElementById("battle-progress").innerHTML = rows;
    }

    function battlePreviewPayload() {
      if (!state.battle) return null;
      return {
        seed: state.battle.seed,
        selfSubmissionId: state.battle.selfSubmission.submissionId,
        opponentSubmissionId: state.battle.opponentSubmission.submissionId,
        rounds: state.battle.rounds.map(round => ({
          roundNumber: round.roundNumber,
          selfCandidateDeckIds: round.selfCandidateDeckIds,
          opponentCandidateDeckIds: round.opponentCandidateDeckIds,
          selfSelectedDeckId: round.selfSelectedDeckId,
          opponentSelectedDeckId: round.opponentSelectedDeckId,
          selfWinRate: round.selfWinRate,
          result: round.result,
          selfUsedDeckIds: round.selfUsedDeckIds,
          opponentUsedDeckIds: round.opponentUsedDeckIds,
          score: round.score
        })),
        finalResult: state.battle.isComplete ? {
          winner: state.battle.winner,
          selfWins: state.battle.score.self,
          opponentWins: state.battle.score.opponent
        } : null
      };
    }

    function renderBattle(validation) {
      if (!state.battle) initializeBattleState();
      const battle = state.battle;
      const currentSubmissionReady = validation.canStartBattle;
      document.getElementById("set-self-submission").disabled = !currentSubmissionReady;
      document.getElementById("set-opponent-submission").disabled = !currentSubmissionReady;
      document.getElementById("battle-seed").value = battle.seed;
      document.getElementById("battle-submissions").innerHTML = [
        submissionSummaryHtml("自分側提出案", battle.selfSubmission),
        submissionSummaryHtml("相手側提出案", battle.opponentSubmission)
      ].join("");

      const selfReady = canUseBattleSubmission(battle.selfSubmission);
      const opponentReady = canUseBattleSubmission(battle.opponentSubmission);
      if (!selfReady || !opponentReady) {
        document.getElementById("battle-state-badge").className = "badge warn";
        document.getElementById("battle-state-badge").textContent = "提出案未成立";
        document.getElementById("battle-status-grid").innerHTML = `
          <section class="battle-card blocked">
            <h3>バトル開始不可</h3>
            <div>自分側・相手側の提出案を3/2/2、7クラスで成立させてください。</div>
          </section>
        `;
        document.getElementById("battle-current-round").innerHTML = "";
        document.getElementById("battle-deck-lists").innerHTML = "";
        document.getElementById("battle-progress").innerHTML = "";
        return;
      }

      renderBattleStatus();
      renderCurrentRound();
      renderBattleDeckLists();
      renderBattleProgress();

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
          hardWarnings.push(`${entry.role}: ${playerName} / ${deckName} はhardです。強い警告として扱います。`);
        }
        if (status.status === "trainable") {
          trainableCount += 1;
          warnings.push(`${entry.role}: ${playerName} / ${deckName} はtrainableです。練習負荷を確認してください。`);
        }
      });

      if (trainableCount + missingStatusCount >= 3) {
        warnings.push(`trainable / データなし が合計${trainableCount + missingStatusCount}件あります。練習負荷・確認負荷が高い提出案です。`);
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
        const badgeClass = count === 1 ? "badge ok" : count === 0 ? "badge warn" : "badge bad";
        const stateLabel = count === 1 ? "選択済み" : count === 0 ? "未選択" : `重複 ${count}`;
        return `<span class="${badgeClass}">${escapeHtml(definition.displayName)} ${stateLabel}</span>`;
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
            const status = statusFor(assignment.playerId, deck.deckId);
            return `
              <label class="deck-option ${checked ? "selected" : ""} ${escapeHtml(classCssClass(deck.className))}">
                <input type="checkbox" data-role-deck="${escapeHtml(roleDef.role)}" data-deck-id="${escapeHtml(deck.deckId)}"${checked ? " checked" : ""}>
                <span class="deck-main">
                  <span class="deck-name">
                    <strong>${escapeHtml(deck.deckName)}</strong>
                    ${statusBadgeHtml(status)}
                  </span>
                  ${statusNoteHtml(status)}
                </span>
              </label>
            `;
          }).join("") || `<div class="empty">このクラスの候補はありません。</div>`;
          return `
            <div class="deck-class-group ${selectedHere ? "selected-class" : ""} ${escapeHtml(classCssClass(definition.className))}">
              <div class="deck-class-group-head">
                <div class="badge-row">
                  ${classBadgeHtml(definition.className)}
                  <span class="count">候補 ${classDecks.length}</span>
                </div>
                <span class="badge ${stateKind}">${escapeHtml(stateLabel)}</span>
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
          ${roleClassSummaryHtml(roleDef.role)}
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
            "hard / trainable / データなし の確認対象はありません。"
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
                <span class="badge bad">hard ${hardCount}</span>
                <span class="badge warn">trainable ${trainableCount}</span>
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

    document.getElementById("reset-battle-sample").addEventListener("click", resetBattleToSamples);

    document.getElementById("reset-battle-progress").addEventListener("click", () => {
      resetBattleProgress();
    });

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

    dataset = read_ps_simulator_sample_dataset(dataset_path)
    public_dataset_path = out_dir / PS_SIMULATOR_PUBLIC_DATASET_PATH
    public_dataset_path.parent.mkdir(parents=True, exist_ok=True)
    public_dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
