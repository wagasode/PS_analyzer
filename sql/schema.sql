PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    team TEXT NOT NULL,
    player_name TEXT NOT NULL,
    roster_status TEXT NOT NULL,
    x_handle TEXT NOT NULL,
    confidence TEXT NOT NULL,
    source_url TEXT NOT NULL,
    notes TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (player_name, x_handle)
);

CREATE TABLE IF NOT EXISTS channels (
    channel_id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    channel_url TEXT NOT NULL,
    platform_identifier TEXT NOT NULL,
    external_channel_id TEXT,
    uploads_playlist_id TEXT,
    image_url TEXT NOT NULL DEFAULT '',
    is_owned INTEGER NOT NULL CHECK (is_owned IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (platform, platform_identifier)
);

CREATE TABLE IF NOT EXISTS stream_sessions (
    stream_session_id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    external_stream_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    published_at TEXT,
    duration_sec INTEGER NOT NULL DEFAULT 0,
    game_or_category TEXT,
    is_live_archive INTEGER NOT NULL DEFAULT 0 CHECK (is_live_archive IN (0, 1)),
    is_shadowverse_related INTEGER NOT NULL DEFAULT 0 CHECK (is_shadowverse_related IN (0, 1)),
    shadowverse_match_reason TEXT,
    raw_json TEXT NOT NULL,
    collected_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (platform, external_stream_id)
);

CREATE TABLE IF NOT EXISTS collection_runs (
    collection_run_id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch', 'local')),
    script_name TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    channels_checked INTEGER NOT NULL DEFAULT 0,
    items_seen INTEGER NOT NULL DEFAULT 0,
    items_upserted INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS channel_collection_status (
    channel_id INTEGER PRIMARY KEY REFERENCES channels(channel_id) ON DELETE CASCADE,
    last_checked_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_status TEXT NOT NULL CHECK (last_status IN ('ok', 'skipped', 'failed')),
    last_reason TEXT,
    last_detail TEXT,
    last_items_seen INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_channels_player_platform
    ON channels(player_id, platform);

CREATE INDEX IF NOT EXISTS idx_stream_sessions_player_started
    ON stream_sessions(player_id, started_at);

CREATE INDEX IF NOT EXISTS idx_stream_sessions_platform_started
    ON stream_sessions(platform, started_at);
