# PS_analyzer

Shadowverse: Worlds Beyond Premier Series player streaming analysis.

## Development Workflow

All repository changes should be made on an issue-specific branch. See
`CONTRIBUTING.md` for the branch workflow and PR rules.

## Files

- `data/players_channels.csv`: player/channel master.
- `sql/schema.sql`: SQLite schema.
- `scripts/init_db.py`: imports the master CSV into SQLite.
- `scripts/fetch_youtube_archives.py`: fetches recent YouTube upload/archive metadata.
- `scripts/fetch_twitch_vods.py`: fetches Twitch archive VOD metadata.
- `scripts/build_streaming_report.py`: writes aggregate CSV reports.
- `scripts/build_streaming_dashboard.py`: writes a static dashboard for GitHub Pages.

Generated files are ignored:

- `data/streams.sqlite`
- `reports/*.csv`
- `public/`

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

When running in GitHub Actions, the workflow also writes team and player tables
to the run summary, so the latest aggregate result can be checked without
downloading the artifact.

Outputs:

- `reports/streaming_by_player.csv`
- `reports/streaming_by_team.csv`

`streaming_by_player.csv` includes every player from the master CSV, even when
no stream archive was collected. Zero-archive players have `stream_count=0` and
`total_hours=0.0`. Channel collection state is exposed with fields such as
`youtube_channel_status`, `twitch_channel_status`, and `youtube_skipped_reason`
so skipped channels can be distinguished from valid zero-result channels.

## Build Dashboard

```bash
python3 scripts/build_streaming_dashboard.py
```

Outputs:

- `public/index.html`
- `public/data/streaming_by_player.json`
- `public/data/streaming_by_team.json`
- `public/data/streaming_timeline_by_player.json`
- `public/data/metadata.json`

The dashboard is a static table UI for the latest generated reports. It supports
team/player views, filtering, sorting, channel status checks, player-level
archive timelines, and links back to the GitHub Actions run when built in CI.

After the `Collect streaming data` workflow completes successfully, the
`Publish dashboard` workflow publishes the dashboard to GitHub Pages.

The `main` branch dashboard is published at:

- https://wagasode.github.io/PS_analyzer/

Feature branch previews are published under `previews/<branch-slug>/`.
For example, `codex/issue-branch-workflow` is published at:

- https://wagasode.github.io/PS_analyzer/previews/codex-issue-branch-workflow/

For the first deployment, configure the repository's Pages source to
`GitHub Actions` in `Settings` -> `Pages`.

Branch previews require `.github/workflows/publish-dashboard.yml` to exist on
the default branch. The first PR that adds this workflow must be merged before
preview publishing is available for later issue branches.

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
5. Select the branch to collect data for.
6. Keep `youtube_max_pages=1` and `twitch_max_pages=1` for the first run.
7. Wait for `Collect streaming data` to finish.
8. Wait for the automatically triggered `Publish dashboard` workflow to finish.
9. Open the GitHub Pages dashboard or branch preview URL from the workflow summary.

The artifact contains:

- `data/streams.sqlite`
- `reports/streaming_by_player.csv`
- `reports/streaming_by_team.csv`
- `reports/youtube_skipped_channels.csv`
- `public/index.html`
- `public/data/*.json`

The `Publish dashboard` workflow deploys the static dashboard in `public/` to
GitHub Pages. `main` updates the root dashboard, and feature branches update
their own preview directories.
