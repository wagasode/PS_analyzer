const DEFAULT_SHEET_RANGE = "'相性表'!A1:Z100";
const GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token";
const GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly";
const GOOGLE_SHEETS_VALUES_BASE = "https://sheets.googleapis.com/v4/spreadsheets";
const FALLBACK_WIN_RATE = 0.5;
const PROVISIONAL_DECK_ID_PREFIX = "sheet-deck-";
const CLASS_SUFFIXES = ["Nm", "Ni", "E", "R", "W", "D", "B"];

const DEFAULT_DECKS = [
  {
    deckId: "deck-e-1779172826463",
    deckName: "進化E",
    sourceDeckKey: "deck-e-1779172826463"
  },
  {
    deckId: "deck-r-1778681117704",
    deckName: "連携R",
    sourceDeckKey: "deck-r-1778681117704"
  },
  {
    deckId: "ps-w-earth-rite",
    deckName: "秘術W"
  },
  {
    deckId: "ps-d-ramp",
    deckName: "ランプD"
  },
  {
    deckId: "deck-1778742968583",
    deckName: "ミルティオNi",
    sourceDeckKey: "deck-1778742968583"
  },
  {
    deckId: "deck-b-1778743160748",
    deckName: "アミュB",
    sourceDeckKey: "deck-b-1778743160748"
  },
  {
    deckId: "ps-nm-destruction",
    deckName: "破壊Nm"
  }
];

export async function onRequestGet(context) {
  return handleRequest(context.env || {}, {
    fetchImpl: fetch,
    now: () => new Date()
  });
}

export async function handleRequest(env, options = {}) {
  const fetchImpl = options.fetchImpl || fetch;
  const now = options.now || (() => new Date());
  const range = normalizeRange(env.PS_MATCHUP_SHEET_RANGE);

  if (!hasRequiredEnv(env)) {
    return errorResponse(
      "google_sheets_env_missing",
      "Google Sheets相性表の接続設定が不足しています",
      500
    );
  }

  let token;
  try {
    token = await fetchAccessToken(env, fetchImpl, now);
  } catch {
    return errorResponse(
      "google_sheets_auth_failed",
      "Google Sheets相性表の認証に失敗しました",
      502
    );
  }

  let values;
  try {
    values = await fetchSheetValues(env.PS_MATCHUP_SPREADSHEET_ID, range, token, fetchImpl);
  } catch {
    return errorResponse(
      "google_sheets_fetch_failed",
      "Google Sheets相性表の読み込みに失敗しました",
      502
    );
  }

  const payload = parseMatchupMatrix(values, {
    decks: DEFAULT_DECKS,
    range,
    fetchedAt: now().toISOString()
  });
  return jsonResponse(payload, 200);
}

function hasRequiredEnv(env) {
  return [
    env.PS_MATCHUP_SPREADSHEET_ID,
    env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
    env.GOOGLE_PRIVATE_KEY
  ].every(value => typeof value === "string" && value.trim() !== "");
}

function normalizeRange(value) {
  const range = String(value || "").trim();
  return range || DEFAULT_SHEET_RANGE;
}

async function fetchAccessToken(env, fetchImpl, now) {
  const assertion = await createServiceAccountJwt({
    serviceAccountEmail: String(env.GOOGLE_SERVICE_ACCOUNT_EMAIL || "").trim(),
    privateKey: String(env.GOOGLE_PRIVATE_KEY || ""),
    now
  });
  const body = new URLSearchParams({
    grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
    assertion
  });
  const response = await fetchImpl(GOOGLE_TOKEN_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body
  });
  if (!response.ok) {
    throw new Error("google_sheets_auth_failed");
  }
  const payload = await response.json().catch(() => ({}));
  if (!payload || typeof payload.access_token !== "string" || payload.access_token.trim() === "") {
    throw new Error("google_sheets_auth_failed");
  }
  return payload.access_token;
}

async function fetchSheetValues(spreadsheetId, range, accessToken, fetchImpl) {
  const url = `${GOOGLE_SHEETS_VALUES_BASE}/${encodeURIComponent(spreadsheetId)}/values/${encodeURIComponent(range)}?majorDimension=ROWS`;
  const response = await fetchImpl(url, {
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Accept": "application/json"
    }
  });
  if (!response.ok) {
    throw new Error("google_sheets_fetch_failed");
  }
  const payload = await response.json().catch(() => ({}));
  return Array.isArray(payload.values) ? payload.values : [];
}

async function createServiceAccountJwt({ serviceAccountEmail, privateKey, now }) {
  const issuedAt = Math.floor(now().getTime() / 1000);
  const header = {
    alg: "RS256",
    typ: "JWT"
  };
  const claims = {
    iss: serviceAccountEmail,
    scope: GOOGLE_SHEETS_SCOPE,
    aud: GOOGLE_TOKEN_ENDPOINT,
    exp: issuedAt + 3600,
    iat: issuedAt
  };
  const encodedHeader = base64UrlEncode(JSON.stringify(header));
  const encodedClaims = base64UrlEncode(JSON.stringify(claims));
  const signingInput = `${encodedHeader}.${encodedClaims}`;
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToArrayBuffer(privateKey),
    {
      name: "RSASSA-PKCS1-v1_5",
      hash: "SHA-256"
    },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(signingInput)
  );
  return `${signingInput}.${base64UrlFromBytes(new Uint8Array(signature))}`;
}

function pemToArrayBuffer(privateKey) {
  const restored = String(privateKey || "").replace(/\\n/g, "\n");
  const base64 = restored
    .replace(/-----BEGIN PRIVATE KEY-----/g, "")
    .replace(/-----END PRIVATE KEY-----/g, "")
    .replace(/\s+/g, "");
  if (!base64) {
    throw new Error("google_private_key_invalid");
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

function parseMatchupMatrix(values, options = {}) {
  const range = normalizeRange(options.range);
  const fetchedAt = options.fetchedAt || new Date().toISOString();
  const rangeInfo = parseA1Range(range);
  const rows = Array.isArray(values) ? values : [];
  const baseDecks = options.decks || DEFAULT_DECKS;
  const { lookup: officialLookup, ambiguous: officialAmbiguous } = buildDeckLookup(baseDecks);
  const provisionalDecks = buildProvisionalDecks(
    collectMatchupDeckCandidates(rows, rangeInfo),
    officialLookup,
    officialAmbiguous,
    baseDecks
  );
  const { lookup, ambiguous } = buildDeckLookup([...baseDecks, ...provisionalDecks]);
  const warnings = provisionalDecks.flatMap(deck => (
    (deck.warnings || []).map(warning => `仮デッキ候補 ${deck.deckName}: ${warning}`)
  ));
  const matchups = [];
  const seen = new Set();
  const headerRow = Array.isArray(rows[0]) ? rows[0] : [];
  const targetColumns = [];
  const maxColumnCount = rows.reduce(
    (max, row) => Math.max(max, Array.isArray(row) ? row.length : 0),
    headerRow.length
  );

  for (let columnIndex = 2; columnIndex < maxColumnCount; columnIndex += 1) {
    const headerValue = cleanCell(headerRow[columnIndex]);
    const headerCell = sourceCell(rangeInfo, 0, columnIndex);
    const columnHasValues = rows.slice(2).some(row => cleanCell(row?.[columnIndex]) !== "");
    if (!headerValue) {
      if (columnHasValues) {
        warnings.push(`列デッキ名が空のためmatchupを採用しません: ${headerCell}`);
      }
      targetColumns[columnIndex] = null;
      continue;
    }
    const resolved = resolveDeckId(headerValue, lookup, ambiguous);
    if (!resolved) {
      warnings.push(`列デッキをdeckIdへ解決できません: ${headerValue} (${headerCell})`);
      targetColumns[columnIndex] = null;
      continue;
    }
    targetColumns[columnIndex] = {
      deckId: resolved,
      name: headerValue
    };
  }

  for (let rowIndex = 2; rowIndex < rows.length; rowIndex += 1) {
    const row = Array.isArray(rows[rowIndex]) ? rows[rowIndex] : [];
    const rowDeckName = cleanCell(row[1]);
    const rowCell = sourceCell(rangeInfo, rowIndex, 1);
    const rowHasValues = row.slice(2).some(value => cleanCell(value) !== "");
    if (!rowDeckName) {
      if (rowHasValues) {
        warnings.push(`行デッキ名が空のためmatchupを採用しません: ${rowCell}`);
      }
      continue;
    }
    const sourceDeckId = resolveDeckId(rowDeckName, lookup, ambiguous);
    if (!sourceDeckId) {
      warnings.push(`行デッキをdeckIdへ解決できません: ${rowDeckName} (${rowCell})`);
      continue;
    }

    for (let columnIndex = 2; columnIndex < targetColumns.length; columnIndex += 1) {
      const target = targetColumns[columnIndex];
      if (!target) {
        continue;
      }
      const rawWinRate = row[columnIndex];
      const cell = sourceCell(rangeInfo, rowIndex, columnIndex);
      const normalized = normalizeWinRate(rawWinRate);
      if (normalized.missing) {
        continue;
      }
      if (normalized.warning) {
        warnings.push(`${sourceDeckId} vs ${target.deckId} (${cell}): ${normalized.warning}`);
        continue;
      }
      const key = `${sourceDeckId}\u0000${target.deckId}`;
      if (seen.has(key)) {
        warnings.push(`重複matchupを検出しました: ${sourceDeckId} vs ${target.deckId} (${cell})`);
        continue;
      }
      seen.add(key);
      if (sourceDeckId === target.deckId && normalized.value !== FALLBACK_WIN_RATE) {
        warnings.push(`自己対面は0.5が原則です: ${sourceDeckId} = ${normalized.value} (${cell})`);
      }
      matchups.push({
        sourceDeckId,
        targetDeckId: target.deckId,
        winRate: normalized.value,
        sourceCell: cell,
        perspective: "rowDeck"
      });
    }
  }

  return {
    source: {
      type: "google_sheets",
      spreadsheetIdSource: "env",
      range,
      fetchedAt
    },
    provisionalDecks,
    deckCandidates: provisionalDecks,
    unresolvedDecks: provisionalDecks,
    matchups,
    warnings
  };
}

function collectMatchupDeckCandidates(rows, rangeInfo) {
  const candidates = new Map();
  const headerRow = Array.isArray(rows[0]) ? rows[0] : [];
  const maxColumnCount = rows.reduce(
    (max, row) => Math.max(max, Array.isArray(row) ? row.length : 0),
    headerRow.length
  );

  for (let columnIndex = 2; columnIndex < maxColumnCount; columnIndex += 1) {
    addMatchupDeckCandidate(
      candidates,
      headerRow[columnIndex],
      sourceCell(rangeInfo, 0, columnIndex),
      "column"
    );
  }

  for (let rowIndex = 2; rowIndex < rows.length; rowIndex += 1) {
    const row = Array.isArray(rows[rowIndex]) ? rows[rowIndex] : [];
    addMatchupDeckCandidate(
      candidates,
      row[1],
      sourceCell(rangeInfo, rowIndex, 1),
      "row"
    );
  }

  return candidates;
}

function addMatchupDeckCandidate(candidates, value, sourceCellValue, role) {
  const deckName = cleanCell(value);
  const normalizedName = normalizeDeckName(deckName);
  if (!normalizedName) {
    return;
  }
  const existing = candidates.get(normalizedName) || {
    deckName,
    normalizedName,
    sourceCells: [],
    roles: new Set()
  };
  if (!existing.sourceCells.includes(sourceCellValue)) {
    existing.sourceCells.push(sourceCellValue);
  }
  existing.roles.add(role);
  candidates.set(normalizedName, existing);
}

function buildProvisionalDecks(candidates, officialLookup, officialAmbiguous, officialDecks) {
  const usedDeckIds = new Set((officialDecks || []).map(deck => cleanCell(deck?.deckId)).filter(Boolean));
  return Array.from(candidates.values())
    .filter(candidate => !officialLookup.has(candidate.normalizedName) && !officialAmbiguous.has(candidate.normalizedName))
    .map(candidate => {
      const deckId = provisionalDeckId(candidate.normalizedName, usedDeckIds);
      usedDeckIds.add(deckId);
      const className = inferClassName(candidate.normalizedName);
      const warnings = [];
      if (!className) {
        warnings.push("classNameを推定できないため、提出案ではクラス不明として扱います。");
      }
      return {
        deckId,
        deckName: candidate.deckName,
        displayName: candidate.deckName,
        normalizedDeckName: candidate.normalizedName,
        className,
        weaknessTags: [],
        note: "相性表由来の仮デッキ候補。正式deck定義には未登録。",
        source: "matchup_matrix",
        sourceType: "google_sheets_matchup",
        sourceCells: candidate.sourceCells,
        candidateRoles: Array.from(candidate.roles),
        provisional: true,
        temporary: true,
        deckKind: "provisional",
        warnings
      };
    });
}

function provisionalDeckId(normalizedName, usedDeckIds = new Set()) {
  const baseId = `${PROVISIONAL_DECK_ID_PREFIX}${hashDeckName(normalizedName)}`;
  if (!usedDeckIds.has(baseId)) {
    return baseId;
  }
  let suffix = 2;
  while (usedDeckIds.has(`${baseId}-${suffix}`)) {
    suffix += 1;
  }
  return `${baseId}-${suffix}`;
}

function inferClassName(deckName) {
  const normalized = normalizeDeckName(deckName);
  return CLASS_SUFFIXES.find(suffix => normalized.endsWith(suffix)) || "";
}

function buildDeckLookup(decks) {
  const lookup = new Map();
  const ambiguous = new Set();
  for (const deck of decks || []) {
    const deckId = cleanCell(deck?.deckId);
    if (!deckId) {
      continue;
    }
    for (const value of [deckId, deck?.deckName, deck?.displayName, deck?.sourceDeckKey, deck?.normalizedDeckName]) {
      const key = normalizeDeckName(value);
      if (!key) {
        continue;
      }
      const current = lookup.get(key);
      if (current && current !== deckId) {
        ambiguous.add(key);
      } else {
        lookup.set(key, deckId);
      }
    }
  }
  return { lookup, ambiguous };
}

function resolveDeckId(value, lookup, ambiguous) {
  const key = normalizeDeckName(value);
  if (!key || ambiguous.has(key)) {
    return null;
  }
  return lookup.get(key) || null;
}

function normalizeWinRate(rawValue) {
  if (rawValue === null || rawValue === undefined) {
    return { value: null, warning: null, missing: true };
  }
  if (typeof rawValue === "string" && rawValue.trim() === "") {
    return { value: null, warning: null, missing: true };
  }

  const rawText = String(rawValue).trim();
  let value;
  if (typeof rawValue === "string" && rawText.endsWith("%")) {
    value = Number(rawText.slice(0, -1).trim()) / 100;
  } else {
    value = Number(rawText);
    if (value > 1 && value <= 100) {
      value /= 100;
    }
  }

  if (!Number.isFinite(value)) {
    return {
      value: null,
      warning: `winRateを数値として読めません: ${rawText}`,
      missing: false
    };
  }
  if (value < 0 || value > 1) {
    return {
      value: null,
      warning: `winRateが範囲外です: ${rawText}`,
      missing: false
    };
  }
  return { value, warning: null, missing: false };
}

function parseA1Range(range) {
  const normalized = normalizeRange(range);
  const bangIndex = normalized.lastIndexOf("!");
  const sheetName = bangIndex >= 0 ? normalized.slice(0, bangIndex) : "";
  const cellRange = bangIndex >= 0 ? normalized.slice(bangIndex + 1) : normalized;
  const startCell = cellRange.split(":", 1)[0] || "A1";
  const match = /^([A-Za-z]+)(\d+)$/.exec(startCell.trim());
  if (!match) {
    return {
      sheetName,
      startColumn: 1,
      startRow: 1
    };
  }
  return {
    sheetName,
    startColumn: columnLettersToNumber(match[1]),
    startRow: Number(match[2])
  };
}

function sourceCell(rangeInfo, rowOffset, columnOffset) {
  const column = columnNumberToLetters(rangeInfo.startColumn + columnOffset);
  const row = rangeInfo.startRow + rowOffset;
  const cell = `${column}${row}`;
  return rangeInfo.sheetName ? `${rangeInfo.sheetName}!${cell}` : cell;
}

function columnLettersToNumber(value) {
  return String(value || "")
    .toUpperCase()
    .split("")
    .reduce((total, char) => total * 26 + char.charCodeAt(0) - 64, 0);
}

function columnNumberToLetters(value) {
  let number = value;
  let letters = "";
  while (number > 0) {
    const remainder = (number - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    number = Math.floor((number - 1) / 26);
  }
  return letters || "A";
}

function cleanCell(value) {
  return String(value ?? "").trim();
}

function normalizeDeckName(value) {
  return String(value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function hashDeckName(value) {
  let hash = 2166136261;
  for (const char of normalizeDeckName(value)) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function jsonResponse(payload, status) {
  return new Response(JSON.stringify(payload) + "\n", {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    }
  });
}

function errorResponse(code, message, status) {
  return jsonResponse({ error: { code, message } }, status);
}

function base64UrlEncode(value) {
  return base64UrlFromBytes(new TextEncoder().encode(value));
}

function base64UrlFromBytes(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

export const __test = {
  DEFAULT_DECKS,
  DEFAULT_SHEET_RANGE,
  buildDeckLookup,
  buildProvisionalDecks,
  handleRequest,
  normalizeWinRate,
  parseMatchupMatrix
};
