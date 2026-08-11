from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analyze_rules import build_summary  # noqa: E402


class DataQualitySummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task_config = {
            "category": "japan_market",
            "title": "9:30 寄り後の日本株・海外市場・材料確認",
        }
        self.rules = {
            "thresholds": {
                "strong_up_pct": 1.0,
                "moderate_up_pct": 0.3,
                "moderate_down_pct": -0.3,
                "strong_down_pct": -1.0,
            },
            "messages": {"no_signal": "未確認"},
        }

    def test_quality_badge_counts_only_verified_items(self) -> None:
        raw_data = {
            "items": [
                {
                    "key": "NIKKEI225",
                    "label": "日経225",
                    "current": 40000.0,
                    "previous": 39600.0,
                    "change_pct": 1.01,
                    "status": "ok",
                    "quality_status": "verified",
                    "as_of": "2026-08-11",
                    "comparison_group": "market_return",
                    "series": [
                        {"date": "2026-08-08", "value": 39600.0},
                        {"date": "2026-08-11", "value": 40000.0},
                    ],
                },
                {
                    "key": "TOPIX",
                    "label": "TOPIX近似(ETF)",
                    "current": None,
                    "previous": None,
                    "change_pct": None,
                    "status": "unavailable",
                    "quality_status": "unavailable",
                    "as_of": None,
                    "comparison_group": "market_return",
                    "series": [],
                },
            ],
            "macro_items": [],
            "highlights": {},
            "research": {},
            "nikkei225jp": {"status": "unavailable", "note": "未確認"},
        }

        summary = build_summary("japan_morning", self.task_config, raw_data, self.rules)

        self.assertEqual(summary["data_quality"]["verified"], 1)
        self.assertEqual(summary["data_quality"]["total"], 2)
        self.assertEqual(summary["data_quality"]["badge"], "確認済 1/2")
        self.assertEqual(summary["data_quality"]["latest_as_of"], "2026-08-11")

    def test_rate_levels_are_not_marked_as_market_returns(self) -> None:
        raw_data = {
            "items": [],
            "macro_items": [
                {
                    "key": "US10Y",
                    "label": "米10年債利回り",
                    "current": 4.1,
                    "previous": 4.0,
                    "change_pct": 2.5,
                    "change_bps": 10.0,
                    "status": "ok",
                    "quality_status": "verified",
                    "as_of": "2026-08-11",
                    "comparison_group": "rate_level",
                    "series": [
                        {"date": "2026-08-08", "value": 4.0},
                        {"date": "2026-08-11", "value": 4.1},
                    ],
                }
            ],
            "highlights": {},
            "research": {},
            "nikkei225jp": {"status": "unavailable", "note": "未確認"},
        }

        summary = build_summary("japan_morning", self.task_config, raw_data, self.rules)

        self.assertEqual(summary["visual_items"][0]["comparison_group"], "rate_level")
        self.assertIn("+10.0bp", summary["macro_metrics"][0])


if __name__ == "__main__":
    unittest.main()
