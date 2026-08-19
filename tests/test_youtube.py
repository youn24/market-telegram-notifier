from __future__ import annotations

import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from create_report import _render_youtube_reference
from fetch_youtube import classify_youtube_topics, parse_youtube_channel_page, parse_youtube_feed


JST = ZoneInfo("Asia/Tokyo")


def _feed(published: str = "2026-08-19T06:00:00+00:00") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <entry>
        <yt:videoId>abc123xyz00</yt:videoId>
        <title>大引け後の日本株材料を確認</title>
        <link rel="alternate" href="https://www.youtube.com/watch?v=abc123xyz00" />
        <published>{published}</published>
      </entry>
    </feed>"""


def _channel_page(relative_published: str = "16 時間前") -> str:
    initial_data = {
        "contents": {
            "richGridRenderer": {
                "contents": [
                    {
                        "lockupViewModel": {
                            "contentId": "abc123xyz00",
                            "metadata": {
                                "lockupMetadataViewModel": {
                                    "title": {"content": "日本株とドル円を確認"},
                                    "metadata": {
                                        "contentMetadataViewModel": {
                                            "metadataRows": [
                                                {
                                                    "metadataParts": [
                                                        {"text": {"content": "1万回視聴"}},
                                                        {"text": {"content": relative_published}},
                                                    ]
                                                }
                                            ]
                                        }
                                    },
                                }
                            },
                        }
                    }
                ]
            }
        }
    }
    return "<script>var ytInitialData = " + json.dumps(initial_data, ensure_ascii=False) + ";</script>"


class YouTubeFeedTests(unittest.TestCase):
    def test_feed_uses_only_public_metadata(self) -> None:
        items = parse_youtube_feed(
            _feed(),
            "株リアルライブ（あす上がる株）",
            now=datetime(2026, 8, 19, 16, 0, tzinfo=JST),
            max_age_hours=24,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "大引け後の日本株材料を確認")
        self.assertEqual(items[0]["quality_status"], "verified")
        self.assertNotIn("summary", items[0])

    def test_stale_video_is_not_shown_as_new(self) -> None:
        items = parse_youtube_feed(
            _feed("2026-08-10T06:00:00+00:00"),
            "テスト",
            now=datetime(2026, 8, 19, 16, 0, tzinfo=JST),
            max_age_hours=72,
        )
        self.assertEqual(items, [])

    def test_title_topics_are_limited_to_public_title_words(self) -> None:
        topics = classify_youtube_topics(
            "日本株とドル円、FOMC後の動きを確認",
            {
                "日本株": ["日本株", "日経"],
                "為替": ["ドル円", "FX"],
                "金利・金融政策": ["FOMC", "日銀"],
                "決算": ["決算"],
            },
        )
        self.assertEqual(topics, ["日本株", "為替", "金利・金融政策"])

    def test_channel_page_fallback_uses_relative_publication_label(self) -> None:
        items = parse_youtube_channel_page(
            _channel_page(),
            "NOBU塾",
            max_age_hours=72,
            topic_keywords={"日本株": ["日本株"], "為替": ["ドル円"]},
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["published"], "16 時間前（取得時点）")
        self.assertFalse(items[0]["published_exact"])
        self.assertEqual(items[0]["age_hours_upper_bound"], 17)
        self.assertEqual(items[0]["topics"], ["日本株", "為替"])

    def test_channel_page_fallback_rejects_stale_relative_label(self) -> None:
        items = parse_youtube_channel_page(
            _channel_page("4 日前"),
            "NOBU塾",
            max_age_hours=72,
        )
        self.assertEqual(items, [])

    def test_report_marks_video_as_external_view(self) -> None:
        html = _render_youtube_reference(
            {
                "youtube": {
                    "status": "ok",
                    "items": [
                        {
                            "title": "大引け後の日本株材料を確認",
                            "channel": "テストチャンネル",
                            "published": "2026-08-19 15:00 JST",
                            "url": "https://www.youtube.com/watch?v=abc123xyz00",
                            "topics": ["日本株", "決算・企業材料"],
                        }
                    ],
                    "note": "公開フィードのみ",
                }
            }
        )
        self.assertIn("外部見解", html)
        self.assertIn("売買根拠には未採用", html)
        self.assertIn("大引け後の日本株材料を確認", html)
        self.assertIn("参考観点: 日本株 / 決算・企業材料", html)


if __name__ == "__main__":
    unittest.main()
