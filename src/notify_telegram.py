from __future__ import annotations

from pathlib import Path
from typing import Iterable

import requests


def _raise_for_status(response: requests.Response) -> None:
    if response.ok:
        return
    raise RuntimeError(f"Telegram API error: status={response.status_code} body={response.text}")


def send_telegram_notification(
    bot_token: str,
    chat_id: str,
    text: str,
    image_paths: Iterable[Path],
) -> None:
    base_url = f"https://api.telegram.org/bot{bot_token}"
    images = [path for path in image_paths if path.exists()]
    first_image = images[0] if images else None

    if first_image is None:
        message_response = requests.post(
            f"{base_url}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        _raise_for_status(message_response)
        return

    with first_image.open("rb") as image_file:
        photo_response = requests.post(
            f"{base_url}/sendPhoto",
            data={
                "chat_id": chat_id,
                "caption": text[:1024],
                "parse_mode": "HTML",
            },
            files={"photo": image_file},
            timeout=60,
        )
    _raise_for_status(photo_response)
