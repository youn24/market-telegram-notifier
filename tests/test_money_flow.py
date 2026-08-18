from __future__ import annotations

import unittest

from analyze_rules import build_money_flow_snapshot
from create_report import _render_money_flow_board


THRESHOLDS = {"moderate_up_pct": 0.3, "moderate_down_pct": -0.3}


def _item(key: str, change: float) -> dict:
    return {
        "key": key,
        "label": key,
        "status": "ok",
        "quality_status": "verified",
        "change_pct": change,
        "as_of": "2026-08-18",
    }


class MoneyFlowTests(unittest.TestCase):
    def test_broad_equity_rally_is_price_confirmed(self) -> None:
        raw_data = {
            "items": [
                _item("DOW", 0.8),
                _item("SP500", 1.0),
                _item("NASDAQ", 1.4),
                _item("RUSSELL2000", 0.7),
                _item("USDJPY", 0.2),
            ],
            "macro_items": [_item("VIX", -4.0)],
        }
        result = build_money_flow_snapshot(raw_data, THRESHOLDS)
        self.assertEqual(result["status"], "ok")
        self.assertIn("株式優勢", result["headline"])
        self.assertIn("大型成長株優位", result["headline"])
        self.assertIn("日足", result["rows"][0]["evidence"])

    def test_mixed_market_is_labeled_selective(self) -> None:
        raw_data = {
            "items": [
                _item("DOW", 0.8),
                _item("SP500", -0.7),
                _item("NASDAQ", -0.5),
                _item("RUSSELL2000", 0.4),
            ],
            "macro_items": [],
        }
        result = build_money_flow_snapshot(raw_data, THRESHOLDS)
        self.assertIn("全面移動より選別", result["headline"])
        self.assertNotIn("株式優勢", result["headline"])

    def test_insufficient_market_data_is_unconfirmed(self) -> None:
        result = build_money_flow_snapshot({"items": [_item("SP500", 1.0)], "macro_items": []}, THRESHOLDS)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("未確認", result["headline"])
        self.assertIn("実額は未確認", result["actual_flow_note"])

    def test_mixed_dates_are_shown_as_a_basis_range(self) -> None:
        items = [_item("DOW", 0.8), _item("SP500", 0.9), _item("NASDAQ", 1.1)]
        items[0]["as_of"] = "2026-08-15"
        result = build_money_flow_snapshot({"items": items, "macro_items": []}, THRESHOLDS)
        self.assertIn("基準日2026-08-15〜2026-08-18", result["rows"][0]["evidence"])

    def test_report_board_explains_actual_flow_limitation(self) -> None:
        raw_data = {
            "items": [_item("DOW", 0.8), _item("SP500", 1.0), _item("NASDAQ", 1.4), _item("RUSSELL2000", 0.7)],
            "macro_items": [],
        }
        flow = build_money_flow_snapshot(raw_data, THRESHOLDS)
        html = _render_money_flow_board({"money_flow": flow})
        self.assertIn("価格から見た資金方向", html)
        self.assertIn("実額は未確認", html)
        self.assertIn("flow-card", html)

    def test_after_hours_uses_futures_instead_of_daily_indices(self) -> None:
        raw_data = {
            "series_mode": "intraday",
            "items": [
                _item("DOW_FUT", -1.0),
                _item("SP500_FUT", -1.2),
                _item("NASDAQ100_FUT", -1.6),
                _item("RUSSELL_FUT", -0.8),
                _item("NIKKEI_FUT", -1.4),
            ],
            "macro_items": [],
        }
        result = build_money_flow_snapshot(raw_data, THRESHOLDS)
        self.assertIn("株価先物劣勢", result["headline"])
        self.assertEqual(result["rows"][0]["label"], "株価先物")
        self.assertIn("時間外先物", result["actual_flow_note"])


if __name__ == "__main__":
    unittest.main()
