from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("yfinance", types.SimpleNamespace())

from fetch_themes import evaluate_theme_groups


CONFIG = {
    "minimum_valid_symbols": 3,
    "alert_average_pct": 1.5,
    "alert_breadth_pct": 75,
    "themes": {
        "sample": {
            "label": "テストテーマ",
            "symbols": [
                {"ticker": "A", "label": "A社"},
                {"ticker": "B", "label": "B社"},
                {"ticker": "C", "label": "C社"},
                {"ticker": "D", "label": "D社"},
            ],
        }
    },
}


def _symbol(change: float) -> dict:
    return {
        "status": "ok",
        "quality_status": "verified",
        "change_pct": change,
        "as_of": "2026-08-17 10:00 JST",
    }


class ThemeTests(unittest.TestCase):
    def test_broad_theme_rally_is_confirmed(self) -> None:
        result = evaluate_theme_groups(
            {"A": _symbol(2.4), "B": _symbol(2.0), "C": _symbol(1.8), "D": _symbol(1.6)},
            CONFIG,
        )
        theme = result["primary"]
        self.assertEqual(theme["signal"], "一斉高")
        self.assertEqual(theme["breadth_up_pct"], 100)
        self.assertGreaterEqual(theme["confirmation_score"], 75)
        self.assertEqual(len(result["alerts"]), 1)

    def test_isolated_spike_is_not_theme_alert(self) -> None:
        result = evaluate_theme_groups(
            {"A": _symbol(6.0), "B": _symbol(-0.5), "C": _symbol(0.0), "D": _symbol(0.2)},
            CONFIG,
        )
        self.assertEqual(result["primary"]["signal"], "監視")
        self.assertEqual(result["alerts"], [])

    def test_insufficient_coverage_is_unconfirmed(self) -> None:
        result = evaluate_theme_groups({"A": _symbol(2.0), "B": _symbol(2.2)}, CONFIG)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["themes"][0]["signal"], "未確認")
        self.assertIsNone(result["primary"])


if __name__ == "__main__":
    unittest.main()
