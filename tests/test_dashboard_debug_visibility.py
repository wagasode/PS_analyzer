from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from build_streaming_dashboard import render_html  # noqa: E402


class DashboardDebugVisibilityTest(unittest.TestCase):
    def test_operational_links_are_collapsed_outside_normal_header(self) -> None:
        html = render_html()

        self.assertIn('<details class="debug-info" id="debug-info" hidden>', html)
        self.assertIn('<dl class="debug-list" id="debug-list"></dl>', html)
        self.assertIn('<div class="debug-links" id="debug-links">', html)
        self.assertNotIn('<div class="actions">', html)

    def test_toolbar_links_to_ps_simulator_by_current_page_name(self) -> None:
        html = render_html()

        self.assertIn('<a class="button" href="ps-simulator.html">PSルール戦略シミュレータ</a>', html)
        self.assertNotIn('<a class="button" href="ps-simulator.html">提出案作成</a>', html)

    def test_metadata_keeps_run_number_in_operational_details(self) -> None:
        html = render_html()

        self.assertIn('document.getElementById("metadata").textContent = `更新: ${formatDate(meta.generated_at)}`;', html)
        self.assertIn('["ワークフロー実行", meta.run_number ? `#${meta.run_number}` : "未設定"]', html)

    def test_summary_counts_are_operational_details_only(self) -> None:
        html = render_html()

        self.assertNotIn('<section class="summary" aria-label="概要">', html)
        self.assertNotIn('id="team-count"', html)
        self.assertNotIn('id="player-count"', html)
        self.assertNotIn('id="stream-count"', html)
        self.assertNotIn('id="total-hours"', html)
        self.assertNotIn('id="sv-hours"', html)
        self.assertIn('["チーム数", formatNumber(meta.team_count)]', html)
        self.assertIn('["選手数", formatNumber(meta.player_count)]', html)
        self.assertIn('["配信数", formatNumber(meta.total_streams)]', html)
        self.assertIn('["総配信時間", formatNumber(meta.total_hours)]', html)
        self.assertIn('["SV時間", formatNumber(meta.shadowverse_hours)]', html)

    def test_save_api_debug_detail_is_collapsed(self) -> None:
        html = render_html()

        self.assertIn('summary.textContent = "調査用の詳細";', html)
        self.assertIn('function publicSaveApiMessage(status, payloadMessage)', html)
        self.assertIn('error.name === "TypeError"', html)
        self.assertIn('API message: ${payloadMessage}', html)

    def test_missing_deck_archive_list_uses_latest_timestamp_sort(self) -> None:
        html = render_html()

        self.assertIn("function compareStreamsByLatestTimestampDesc(left, right)", html)
        self.assertIn("state.missingDeckStreams = missingStreams.sort(compareStreamsByLatestTimestampDesc);", html)


if __name__ == "__main__":
    unittest.main()
