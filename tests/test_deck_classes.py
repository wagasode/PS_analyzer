from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from build_streaming_dashboard import (  # noqa: E402
    DECK_CLASS_DEFINITIONS,
    DECK_CLASS_VALUES,
    render_html,
)


class DeckClassDefinitionTest(unittest.TestCase):
    def test_deck_class_values_are_issue32_seven_classes(self) -> None:
        self.assertEqual(DECK_CLASS_VALUES, ("E", "R", "W", "D", "Ni", "B", "Nm"))
        self.assertEqual(len(set(DECK_CLASS_VALUES)), 7)

    def test_ni_and_nm_are_distinct_classes(self) -> None:
        definitions = {definition["value"]: definition for definition in DECK_CLASS_DEFINITIONS}

        self.assertEqual(definitions["Ni"]["display_name"], "ナイトメア")
        self.assertIn("NIGHTMARE", definitions["Ni"]["aliases"])
        self.assertNotIn("NM", definitions["Ni"]["aliases"])

        self.assertEqual(definitions["Nm"]["display_name"], "ネメシス")
        self.assertIn("NEMESIS", definitions["Nm"]["aliases"])
        self.assertIn("NM", definitions["Nm"]["aliases"])

    def test_legacy_values_are_aliases_not_saved_values(self) -> None:
        self.assertNotIn("Nc", DECK_CLASS_VALUES)
        self.assertNotIn("V", DECK_CLASS_VALUES)

        definitions = {definition["value"]: definition for definition in DECK_CLASS_DEFINITIONS}
        self.assertIn("Nc", definitions["Ni"]["aliases"])
        self.assertIn("V", definitions["Ni"]["aliases"])

    def test_deck_class_definitions_include_issue33_display_colors(self) -> None:
        expected_colors = {
            "E": "緑",
            "R": "黄色",
            "W": "青",
            "D": "オレンジ",
            "Ni": "茶色",
            "B": "灰色",
            "Nm": "水色",
        }

        definitions = {definition["value"]: definition for definition in DECK_CLASS_DEFINITIONS}
        self.assertEqual(set(definitions), set(expected_colors))
        for value, color_name in expected_colors.items():
            self.assertEqual(definitions[value]["color_name"], color_name)
            self.assertEqual(definitions[value]["css_class"], f"deck-class-{value.lower()}")

    def test_rendered_html_contains_deck_class_definitions(self) -> None:
        html = render_html()

        self.assertNotIn("__DECK_CLASS_DEFINITIONS__", html)
        self.assertIn('"value": "Ni"', html)
        self.assertIn('"display_name": "ネメシス"', html)
        self.assertIn("deck-class-legend", html)
        self.assertNotIn('["class_name", "クラス"]', html)
        self.assertNotIn('["archetype", "アーキタイプ"]', html)


if __name__ == "__main__":
    unittest.main()
