from __future__ import annotations

import unittest

from notification_news import build_notification_news_lines


class NotificationNewsTests(unittest.TestCase):
    def test_uses_one_attributed_confirmed_headline(self) -> None:
        research = {
            "items": [
                {
                    "status": "ok",
                    "title": "企業が通期業績予想を上方修正",
                    "source": "適時開示",
                    "published": "2026-09-10 15:00",
                    "material_categories": ["業績修正"],
                    "matched_keywords": ["上方修正"],
                },
                {"status": "ok", "title": "二つ目のニュース"},
            ]
        }

        self.assertEqual(
            build_notification_news_lines(research),
            [
                "話題: 業績修正",
                "材料ニュース: 企業が通期業績予想を上方修正（適時開示 / 2026-09-10 15:00）",
            ],
        )

    def test_unavailable_research_is_explicitly_unconfirmed(self) -> None:
        self.assertEqual(
            build_notification_news_lines({"status": "unavailable", "items": []}),
            ["話題: 市場材料は未確認", "材料ニュース: 取得できた公開見出しなし"],
        )

    def test_unconfirmed_item_is_not_presented_as_news(self) -> None:
        research = {"items": [{"status": "error", "title": "未検証の見出し"}]}
        self.assertIn("未確認", build_notification_news_lines(research)[0])


if __name__ == "__main__":
    unittest.main()
