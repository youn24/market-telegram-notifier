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

    message_response = requests.post(
        f"{base_url}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=30,
    )
    _raise_for_status(message_response)

    for image_path in image_paths:
        with image_path.open("rb") as image_file:
            photo_response = requests.post(
                f"{base_url}/sendPhoto",
                data={"chat_id": chat_id},
                files={"photo": image_file},
                timeout=60,
            )
        _raise_for_status(photo_response)
