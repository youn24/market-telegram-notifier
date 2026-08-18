from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from fetch_themes import evaluate_price_pattern, evaluate_price_patterns
from create_report import _render_price_pattern_board


CONFIG = {
    "minimum_history_days": 45,
    "gap_threshold_pct": 2.0,
    "breakout_volume_ratio": 1.5,
    "confirmation_volume_ratio": 1.2,
    "high_zone_distance_pct": 5.0,
    "low_zone_distance_pct": 7.0,
}


def _base_frame() -> pd.DataFrame:
    dates = pd.date_range("2026-05-01", periods=65, freq="B")
    return pd.DataFrame(
        {
            "open": [100.5] * 65,
            "high": [102.0] * 65,
            "low": [100.0] * 65,
            "close": [101.0] * 65,
            "volume": [1_000_000.0] * 65,
        },
        index=dates,
    )


class PricePatternTests(unittest.TestCase):
    def test_gap_breakout_requires_price_volume_and_close_confirmation(self) -> None:
        frame = _base_frame()
        frame.iloc[-2] = [100.0, 101.0, 99.5, 100.0, 1_000_000.0]
        frame.iloc[-1] = [103.0, 107.0, 102.5, 106.5, 2_000_000.0]
        result = evaluate_price_pattern("TEST.T", "テスト株", frame, CONFIG)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["signal"], "上放れ継続確認")
        self.assertGreaterEqual(result["score"], 85)
        self.assertIn("20日高値更新", result["evidence"])

    def test_gap_without_volume_is_not_reported(self) -> None:
        frame = _base_frame()
        frame.iloc[-2] = [100.0, 101.0, 99.5, 100.0, 1_000_000.0]
        frame.iloc[-1] = [103.0, 107.0, 102.5, 106.5, 1_000_000.0]
        result = evaluate_price_pattern("TEST.T", "テスト株", frame, CONFIG)
        self.assertEqual(result["status"], "no_signal")

    def test_hammer_near_low_needs_next_day_confirmation(self) -> None:
        frame = _base_frame()
        frame.iloc[-3] = [101.0, 101.5, 100.0, 100.5, 1_000_000.0]
        frame.iloc[-2] = [100.5, 101.5, 96.0, 101.0, 1_000_000.0]
        frame.iloc[-1] = [101.6, 104.0, 101.5, 103.0, 1_400_000.0]
        result = evaluate_price_pattern("TEST.T", "テスト株", frame, CONFIG)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["signal"], "底打ち反転確認")
        self.assertIn("翌日高値超え", result["evidence"])

    def test_shooting_star_near_high_needs_next_day_breakdown(self) -> None:
        frame = _base_frame()
        frame.iloc[-3] = [100.0, 101.5, 99.8, 101.0, 1_000_000.0]
        frame.iloc[-2] = [101.0, 107.0, 100.0, 100.5, 1_000_000.0]
        frame.iloc[-1] = [100.4, 100.5, 98.0, 98.5, 1_400_000.0]
        result = evaluate_price_pattern("TEST.T", "テスト株", frame, CONFIG)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["signal"], "高値圏反落確認")
        self.assertIn("翌日安値割れ", result["evidence"])

    def test_report_shows_evidence_and_win_rate_limitation(self) -> None:
        html = _render_price_pattern_board(
            {
                "price_patterns": {
                    "candidates": [
                        {
                            "ticker": "TEST.T",
                            "label": "テスト株",
                            "signal": "底打ち反転確認",
                            "direction": "bull",
                            "score": 90,
                            "evidence": ["60日安値圏", "翌日高値超え"],
                            "as_of": "2026-08-18",
                            "source": "test",
                        }
                    ],
                    "note": "単独の足型では通知しません。",
                }
            }
        )
        self.assertIn("底打ち反転確認", html)
        self.assertIn("翌日高値超え", html)
        self.assertIn("勝率ではありません", html)

    def test_stale_pattern_is_not_returned_as_current_candidate(self) -> None:
        frame = _base_frame()
        frame.iloc[-2] = [100.0, 101.0, 99.5, 100.0, 1_000_000.0]
        frame.iloc[-1] = [103.0, 107.0, 102.5, 106.5, 2_000_000.0]
        history = frame.rename(columns={name: name.title() for name in frame.columns})
        result = evaluate_price_patterns(
            history,
            {"TEST.T": "テスト株"},
            {**CONFIG, "enabled": True, "minimum_score": 85, "max_age_days": 4},
            now=datetime(2026, 8, 18, 17, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        )
        self.assertEqual(result["status"], "no_signal")
        self.assertEqual(result["unavailable_count"], 1)


if __name__ == "__main__":
    unittest.main()
