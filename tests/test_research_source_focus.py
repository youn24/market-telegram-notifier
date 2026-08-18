from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.modules.setdefault("requests", types.SimpleNamespace())

from fetch_research import _queries_for_task, _source_focus_snapshot  # noqa: E402


class ResearchSourceFocusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {
            "research": {
                "default_queries": {"japan_market": ["日本株 決算"]},
                "headline_direction_keywords": {
                    "positive": ["上方修正", "増配"],
                    "caution": ["下方修正", "減配"],
                },
            }
        }
        self.task_config = {
            "category": "japan_market",
            "additional_research_queries": ["大引け後 決算", "日本株 決算"],
            "source_focus": {
                "label": "大引け後の公開材料",
                "sources": ["日本経済新聞"],
                "query_terms": ["大引け後"],
                "max_items": 5,
                "max_age_hours": 30,
            },
        }

    def test_additional_queries_extend_defaults_without_duplicates(self) -> None:
        self.assertEqual(
            _queries_for_task(self.task_config, self.sources),
            ["日本株 決算", "大引け後 決算"],
        )

    def test_focus_uses_only_fresh_dated_items_from_requested_source(self) -> None:
        ranked_items = [
            {
                "title": "A社が上方修正と増配",
                "source": "日本経済新聞",
                "query": "大引け後 決算",
                "published": "2026-08-18 16:10",
                "age_hours": 1.0,
                "material_categories": ["決算・業績", "配当・資本政策"],
            },
            {
                "title": "B社が下方修正",
                "source": "日本経済新聞",
                "query": "大引け後 決算",
                "published": "日時未確認",
                "material_categories": ["決算・業績"],
            },
            {
                "title": "C社が増配",
                "source": "別媒体",
                "query": "大引け後 決算",
                "published": "2026-08-18 16:20",
                "age_hours": 0.8,
                "material_categories": ["配当・資本政策"],
            },
            {
                "title": "D社の朝の市況記事",
                "source": "日本経済新聞",
                "query": "東京市場 寄り付き",
                "published": "2026-08-18 09:10",
                "age_hours": 8.0,
                "material_categories": ["セクター材料"],
            },
        ]

        result = _source_focus_snapshot(ranked_items, self.task_config, self.sources)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["headline_direction"], "positive")
        self.assertEqual(result["direction_counts"]["positive"], 1)

    def test_focus_marks_unavailable_instead_of_guessing(self) -> None:
        result = _source_focus_snapshot([], self.task_config, self.sources)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["items"], [])
        self.assertIn("未確認", result["note"])


if __name__ == "__main__":
    unittest.main()
