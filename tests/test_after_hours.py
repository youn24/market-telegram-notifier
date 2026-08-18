from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

sys.modules.setdefault("yfinance", types.SimpleNamespace())

from after_hours_gate import evaluate_after_hours_window
from fetch_after_hours import evaluate_after_hours_signals


JST = ZoneInfo("Asia/Tokyo")


def _item(key: str, change: float, *, kind: str = "equity_future", threshold: float = 1.0, hits: int = 3) -> dict:
    return {
        "key": key,
        "label": key,
        "kind": kind,
        "status": "ok",
        "quality_status": "verified",
        "change_pct": change,
        "threshold_pct": threshold,
        "persistence_hits": hits,
        "as_of": "2026-08-17 20:00 JST",
        "source": "test",
    }


class AfterHoursTests(unittest.TestCase):
    def test_confirmed_equity_selloff_triggers(self) -> None:
        result = evaluate_after_hours_signals(
            [
                _item("NASDAQ100_FUT", -1.5),
                _item("SP500_FUT", -0.8),
                _item("DOW_FUT", -0.6),
                _item("VIX", 6.0, kind="volatility", threshold=5.0),
            ]
        )
        self.assertTrue(result["triggered"])
        self.assertEqual(result["primary"]["key"], "NASDAQ100_FUT")
        self.assertGreaterEqual(result["primary"]["score"], 80)
        self.assertGreaterEqual(result["primary"]["corroboration_count"], 2)

    def test_isolated_move_does_not_trigger(self) -> None:
        result = evaluate_after_hours_signals([_item("NIKKEI_FUT", -1.2, hits=1)])
        self.assertFalse(result["triggered"])
        self.assertEqual(result["primary"]["corroboration_count"], 0)

    def test_high_score_with_only_one_confirmation_does_not_trigger(self) -> None:
        result = evaluate_after_hours_signals(
            [
                _item("NASDAQ100_FUT", -1.5),
                _item("SP500_FUT", -0.8),
            ]
        )
        self.assertGreaterEqual(result["primary"]["score"], 80)
        self.assertEqual(result["primary"]["corroboration_count"], 1)
        self.assertFalse(result["triggered"])

    def test_multiple_confirmations_without_persistence_do_not_trigger(self) -> None:
        result = evaluate_after_hours_signals(
            [
                _item("NASDAQ100_FUT", -1.5, hits=1),
                _item("SP500_FUT", -0.8, hits=1),
                _item("DOW_FUT", -0.6, hits=1),
                _item("VIX", 6.0, kind="volatility", threshold=5.0, hits=1),
            ]
        )
        self.assertGreaterEqual(result["primary"]["corroboration_count"], 2)
        self.assertFalse(result["triggered"])

    def test_below_threshold_does_not_trigger(self) -> None:
        result = evaluate_after_hours_signals([_item("SP500_FUT", 0.8)])
        self.assertFalse(result["triggered"])
        self.assertIsNone(result["primary"])

    def test_after_hours_window_handles_overnight_session(self) -> None:
        evening = evaluate_after_hours_window(datetime(2026, 8, 17, 18, 0, tzinfo=JST), "schedule")
        morning = evaluate_after_hours_window(datetime(2026, 8, 18, 8, 0, tzinfo=JST), "schedule")
        daytime = evaluate_after_hours_window(datetime(2026, 8, 18, 12, 0, tzinfo=JST), "schedule")
        self.assertTrue(evening.ready)
        self.assertTrue(morning.ready)
        self.assertEqual(evening.session_key, morning.session_key)
        self.assertEqual(evening.session_key, "2026-08-17")
        self.assertFalse(daytime.ready)

    def test_saturday_session_is_skipped(self) -> None:
        result = evaluate_after_hours_window(datetime(2026, 8, 15, 20, 0, tzinfo=JST), "schedule")
        self.assertFalse(result.ready)


if __name__ == "__main__":
    unittest.main()
