# PS_analyzer

Shadowverse: Worlds Beyond Premier Series player streaming analysis.

## Files

- `data/players_channels.csv`: player/channel master.
- `sql/schema.sql`: SQLite schema.
- `scripts/init_db.py`: imports the master CSV into SQLite.
- `scripts/fetch_youtube_archives.py`: fetches recent YouTube upload/archive metadata.
- `scripts/fetch_twitch_vods.py`: fetches Twitch archive VOD metadata.
- `scripts/build_streaming_report.py`: writes aggregate CSV reports.

Generated files are ignored:

- `data/streams.sqlite`
- `reports/*.csv`

## Setup

This MVP uses only the Python standard library.

```bash
python3 scripts/init_db.py
```

For API fetching, set credentials in your shell:

```bash
export YOUTUBE_API_KEY="..."
export TWITCH_CLIENT_ID="..."
export TWITCH_CLIENT_SECRET="..."
```

## Fetch Archives

Fetch one page per YouTube channel, up to 50 recent uploads each.
Normal uploads are skipped by default; only videos with YouTube `liveStreamingDetails`
are stored for streaming-time analysis.
If a channel's uploads playlist cannot be read by YouTube Data API, that channel
is skipped and reported as a GitHub Actions warning and in
`reports/youtube_skipped_channels.csv`.

```bash
python3 scripts/fetch_youtube_archives.py --max-pages 1
```

Fetch one page per Twitch channel, up to 100 recent archive VODs each:

```bash
python3 scripts/fetch_twitch_vods.py --max-pages 1
```

Limit to one player while testing:

```bash
python3 scripts/fetch_youtube_archives.py --player Toby --max-pages 1
python3 scripts/fetch_twitch_vods.py --player Toby --max-pages 1
```

## Build Reports

```bash
python3 scripts/build_streaming_report.py
```

Outputs:

- `reports/streaming_by_player.csv`
- `reports/streaming_by_team.csv`

## GitHub Actions

Repository secrets required:

- `YOUTUBE_API_KEY`
- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`

Manual run:

1. Open the repository on GitHub.
2. Go to `Actions`.
3. Select `Collect streaming data`.
4. Click `Run workflow`.
5. Keep `youtube_max_pages=1` and `twitch_max_pages=1` for the first run.
6. Download the `streaming-data` artifact from the completed workflow run.

The artifact contains:

- `data/streams.sqlite`
- `reports/streaming_by_player.csv`
- `reports/streaming_by_team.csv`
- `reports/youtube_skipped_channels.csv`
