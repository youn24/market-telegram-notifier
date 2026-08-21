from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

sys.modules.setdefault("yfinance", types.SimpleNamespace())

from fetch_after_hours import evaluate_after_hours_signals
from us_session_gate import evaluate_us_session_window


UTC = ZoneInfo("UTC")


def _item(key: str, change: float, *, kind: str, threshold: float, group: str | None = None) -> dict:
    return {
        "key": key,
        "label": key,
        "kind": kind,
        "group": group,
        "status": "ok",
        "change_pct": change,
        "threshold_pct": threshold,
        "persistence_hits": 3,
    }


class UsSessionTests(unittest.TestCase):
    def test_large_stock_move_with_sector_and_index_confirmation_triggers(self) -> None:
        result = evaluate_after_hours_signals(
            [
                _item("NVDA", -5.0, kind="us_stock", threshold=4.0, group="semiconductor"),
                _item("AMD", -2.0, kind="us_stock", threshold=4.5, group="semiconductor"),
                _item("SOXX", -1.8, kind="us_sector", threshold=2.0),
                _item("NASDAQ", -0.8, kind="us_index", threshold=1.5),
                _item("NIKKEI_FUT", -0.6, kind="equity_future", threshold=1.0),
            ],
            minimum_score=85,
            minimum_corroborations=2,
            minimum_persistence_hits=3,
        )
        self.assertTrue(result["triggered"])
        self.assertEqual(result["primary"]["key"], "NVDA")

    def test_isolated_large_stock_move_is_suppressed(self) -> None:
        result = evaluate_after_hours_signals(
            [_item("TSLA", 7.0, kind="us_stock", threshold=5.0, group="auto")],
            minimum_score=85,
            minimum_corroborations=2,
            minimum_persistence_hits=3,
        )
        self.assertFalse(result["triggered"])

    def test_us_session_gate_handles_daylight_saving_time(self) -> None:
        summer = evaluate_us_session_window(datetime(2026, 8, 21, 14, 0, tzinfo=UTC), "schedule")
        winter = evaluate_us_session_window(datetime(2026, 12, 21, 15, 0, tzinfo=UTC), "schedule")
        before_open = evaluate_us_session_window(datetime(2026, 8, 21, 13, 0, tzinfo=UTC), "schedule")
        self.assertTrue(summer.ready)
        self.assertTrue(winter.ready)
        self.assertFalse(before_open.ready)


if __name__ == "__main__":
    unittest.main()
