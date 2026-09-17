from __future__ import annotations

import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("requests", types.SimpleNamespace(Response=object, post=None))

from notify_telegram import send_telegram_notification


class TelegramNotificationTests(unittest.TestCase):
    def test_photo_caption_keeps_detail_link_intact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "card.png"
            image.write_bytes(b"image")
            caption = '<b>話題: 決算</b>\n<a href="https://example.com/">詳細はこちら</a>'
            with patch("notify_telegram.requests.post") as post:
                post.return_value.ok = True
                send_telegram_notification("test-token", "test-chat", caption, [image])
            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.kwargs["data"]["caption"], caption)

    def test_long_caption_fails_before_sending_instead_of_truncating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "card.png"
            image.write_bytes(b"image")
            with patch("notify_telegram.requests.post") as post:
                with self.assertRaises(ValueError):
                    send_telegram_notification("test-token", "test-chat", "a" * 1025, [image])
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
