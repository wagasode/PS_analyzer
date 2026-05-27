from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from ps_simulator_ui import (  # noqa: E402
    PS_SIMULATOR_PUBLIC_DATASET_PATH,
    read_ps_simulator_sample_dataset,
    render_ps_simulator_html,
    write_ps_simulator_assets,
)


class PsSimulatorUiTest(unittest.TestCase):
    def test_rendered_ui_fetches_repo_local_sample_dataset_copy(self) -> None:
        html = render_ps_simulator_html()

        self.assertIn('const datasetUrl = "data/ps_simulator/sample_dataset.json";', html)
        self.assertIn("fetch(datasetUrl)", html)
        self.assertIn("function validateSubmission(submission)", html)
        self.assertIn("PlayerDeckStatus 行なし", html)
        self.assertIn("データなし / 要確認", html)
        self.assertIn("deck-class-group", html)
        self.assertIn("ルール上の制約", html)
        self.assertIn("運用上の注意", html)
        self.assertIn("<details>", html)
        self.assertIn("className:", html)
        self.assertIn("頑張れば可", html)
        self.assertIn("Google Sheets", html)

    def test_sample_dataset_keeps_missing_status_player_supported_by_ui(self) -> None:
        dataset = read_ps_simulator_sample_dataset()
        player_ids = {player["playerId"] for player in dataset["players"]}
        status_player_ids = {status["playerId"] for status in dataset["playerDeckStatuses"]}

        self.assertIn("player-spicies", player_ids)
        self.assertNotIn("player-spicies", status_player_ids)

    def test_write_assets_copies_sample_dataset_for_static_fetch(self) -> None:
        source_dataset = read_ps_simulator_sample_dataset()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)

            write_ps_simulator_assets(out_dir)

            self.assertTrue((out_dir / "ps-simulator.html").exists())
            public_dataset_path = out_dir / PS_SIMULATOR_PUBLIC_DATASET_PATH
            self.assertTrue(public_dataset_path.exists())
            copied_dataset = json.loads(public_dataset_path.read_text(encoding="utf-8"))
            self.assertEqual(copied_dataset, source_dataset)


if __name__ == "__main__":
    unittest.main()
