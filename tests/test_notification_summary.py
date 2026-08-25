from __future__ import annotations

import unittest

from notification_summary import build_notification_analysis_lines


class NotificationSummaryTests(unittest.TestCase):
    def test_ai_summary_prioritizes_evidence_and_watch_item(self) -> None:
        summary = {
            "conclusion_text": "初動だけで決めず確認を優先します。",
            "ai_summary": [
                "結論: 初動だけで決めず確認を優先します。",
                "根拠: 日経平均とTOPIXが同方向です。",
                "注視: 為替と先物の方向一致を確認します。",
                "反証: 為替と先物が逆方向なら判断を弱めます。",
                "未確認: 投資主体別売買動向は未確認。",
            ],
        }

        self.assertEqual(
            build_notification_analysis_lines(summary),
            [
                "根拠: 日経平均とTOPIXが同方向です。",
                "注視: 為替と先物の方向一致を確認します。",
                "反証: 為替と先物が逆方向なら判断を弱めます。",
            ],
        )

    def test_rule_summary_is_used_when_ai_is_unavailable(self) -> None:
        summary = {
            "conclusion_text": "様子見です。",
            "commentary": ["強弱が混在しています。", "押し目の質を確認します。"],
            "scenarios": ["反証: 日経平均とTOPIXが逆方向なら判断を弱めます。"],
        }

        self.assertEqual(
            build_notification_analysis_lines(summary),
            [
                "根拠: 強弱が混在しています。",
                "注視: 押し目の質を確認します。",
                "反証: 日経平均とTOPIXが逆方向なら判断を弱めます。",
            ],
        )

    def test_duplicate_and_long_lines_are_cleaned(self) -> None:
        summary = {
            "conclusion_text": "同じ文章です。",
            "commentary": ["同じ文章です。", "  ・有効な分析です。  ", "有効な分析です。"],
        }

        self.assertEqual(build_notification_analysis_lines(summary), ["根拠: 有効な分析です。"])


if __name__ == "__main__":
    unittest.main()
