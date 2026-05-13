const MAX_BODY_BYTES = 128 * 1024;
const DECKS_PATH = "data/decks.csv";
const STREAM_SESSION_DECKS_PATH = "data/stream_session_decks.csv";
const DECKS_HEADER = "deck_key,deck_name,class_name,archetype,deck_url,deck_code,notes";
const STREAM_SESSION_DECKS_HEADER = "platform,external_stream_id,deck_key,confidence,source_note,display_order";

export default {
  async fetch(request, env) {
    return handleRequest(request, env);
  }
};

export async function handleRequest(request, env) {
  const origin = request.headers.get("Origin") || "";
  const cors = corsHeaders(origin, env);

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors });
  }

  if (request.method !== "POST") {
    return jsonResponse({ ok: false, error: "Method not allowed." }, 405, cors);
  }

  if (!isOriginAllowed(origin, env)) {
    return jsonResponse({ ok: false, error: "Origin is not allowed." }, 403, cors);
  }

  try {
    const payload = await readJsonBody(request);
    validatePayload(payload, env);
    const commit = await updateCsvFiles(payload, env);
    return jsonResponse({
      ok: true,
      commit_sha: commit.sha,
      commit_url: commit.html_url
    }, 200, cors);
  } catch (error) {
    const status = Number.isInteger(error.status) ? error.status : 500;
    return jsonResponse({ ok: false, error: error.message || "Save failed." }, status, cors);
  }
}

function corsHeaders(origin, env) {
  const headers = {
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin"
  };
  if (origin && isOriginAllowed(origin, env)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Credentials"] = "true";
  }
  return headers;
}

function isOriginAllowed(origin, env) {
  if (!origin) return true;
  const allowed = csvList(env.ALLOWED_ORIGINS);
  return allowed.length === 0 || allowed.includes(origin);
}

function csvList(value) {
  return String(value || "")
    .split(",")
    .map(item => item.trim())
    .filter(Boolean);
}

async function readJsonBody(request) {
  const contentLength = Number(request.headers.get("Content-Length") || 0);
  if (contentLength > MAX_BODY_BYTES) {
    throw httpError(413, "Request body is too large.");
  }

  const text = await request.text();
  if (text.length > MAX_BODY_BYTES) {
    throw httpError(413, "Request body is too large.");
  }

  try {
    return JSON.parse(text);
  } catch {
    throw httpError(400, "Request body must be valid JSON.");
  }
}

function validatePayload(payload, env) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw httpError(400, "Request body must be a JSON object.");
  }

  const repository = requireString(payload.repository, "repository");
  const branch = requireString(payload.branch, "branch");
  const decksCsv = requireString(payload.decks_csv, "decks_csv");
  const streamSessionDecksCsv = requireString(payload.stream_session_decks_csv, "stream_session_decks_csv");

  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
    throw httpError(400, "repository must be owner/repo.");
  }

  if (!/^[A-Za-z0-9._/-]+$/.test(branch) || branch.includes("..") || branch.startsWith("/") || branch.endsWith("/")) {
    throw httpError(400, "branch contains invalid characters.");
  }

  const allowedRepository = String(env.ALLOWED_REPOSITORY || "").trim();
  if (!allowedRepository) {
    throw httpError(500, "ALLOWED_REPOSITORY is not configured.");
  }
  if (repository !== allowedRepository) {
    throw httpError(403, "repository is not allowed.");
  }

  const allowedBranches = csvList(env.ALLOWED_BRANCHES);
  if (allowedBranches.length === 0) {
    throw httpError(500, "ALLOWED_BRANCHES is not configured.");
  }
  if (!allowedBranches.includes(branch)) {
    throw httpError(403, "branch is not allowed.");
  }

  if (!String(env.GITHUB_TOKEN || "").trim()) {
    throw httpError(500, "GITHUB_TOKEN is not configured.");
  }

  assertCsvHeader(decksCsv, DECKS_HEADER, "decks_csv");
  assertCsvHeader(streamSessionDecksCsv, STREAM_SESSION_DECKS_HEADER, "stream_session_decks_csv");
}

function requireString(value, field) {
  if (typeof value !== "string" || value.trim() === "") {
    throw httpError(400, `${field} is required.`);
  }
  return value.trim();
}

function assertCsvHeader(csv, expectedHeader, field) {
  const firstLine = csv.replace(/^\uFEFF/, "").split(/\r?\n/, 1)[0];
  if (firstLine !== expectedHeader) {
    throw httpError(400, `${field} has an invalid CSV header.`);
  }
}

async function updateCsvFiles(payload, env) {
  const { repository, branch, decks_csv: decksCsv, stream_session_decks_csv: streamSessionDecksCsv } = payload;
  const ref = await githubJson(env, repository, `/git/ref/heads/${encodeBranchForRef(branch)}`);
  const baseCommitSha = ref.object.sha;
  const baseCommit = await githubJson(env, repository, `/git/commits/${baseCommitSha}`);

  const [decksBlob, streamSessionDecksBlob] = await Promise.all([
    createBlob(env, repository, decksCsv),
    createBlob(env, repository, streamSessionDecksCsv)
  ]);

  const tree = await githubJson(env, repository, "/git/trees", {
    method: "POST",
    body: JSON.stringify({
      base_tree: baseCommit.tree.sha,
      tree: [
        { path: DECKS_PATH, mode: "100644", type: "blob", sha: decksBlob.sha },
        { path: STREAM_SESSION_DECKS_PATH, mode: "100644", type: "blob", sha: streamSessionDecksBlob.sha }
      ]
    })
  });

  const commit = await githubJson(env, repository, "/git/commits", {
    method: "POST",
    body: JSON.stringify({
      message: "Update deck links from dashboard",
      tree: tree.sha,
      parents: [baseCommitSha]
    })
  });

  await githubJson(env, repository, `/git/refs/heads/${encodeBranchForRef(branch)}`, {
    method: "PATCH",
    body: JSON.stringify({
      sha: commit.sha,
      force: false
    })
  });

  return commit;
}

function encodeBranchForRef(branch) {
  return branch.split("/").map(encodeURIComponent).join("/");
}

async function createBlob(env, repository, content) {
  return githubJson(env, repository, "/git/blobs", {
    method: "POST",
    body: JSON.stringify({
      content,
      encoding: "utf-8"
    })
  });
}

async function githubJson(env, repository, path, options = {}) {
  const response = await fetch(`https://api.github.com/repos/${repository}${path}`, {
    ...options,
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "PS-analyzer-save-deck-links",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(options.headers || {})
    }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.message || `GitHub API request failed with status ${response.status}.`;
    throw httpError(response.status, message);
  }
  return payload;
}

function jsonResponse(payload, status, headers = {}) {
  return new Response(JSON.stringify(payload) + "\n", {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...headers
    }
  });
}

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}
