from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests


JST = ZoneInfo("Asia/Tokyo")
ATOM = "http://www.w3.org/2005/Atom"
YOUTUBE = "http://www.youtube.com/xml/schemas/2015"
CHANNEL_ID_PATTERN = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


def _published_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("公開日時のタイムゾーンを確認できません")
    return parsed.astimezone(JST)


def parse_youtube_feed(
    xml_text: str,
    channel_label: str,
    now: datetime | None = None,
    max_age_hours: float = 72.0,
) -> list[dict[str, Any]]:
    now = now or datetime.now(JST)
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        title = (entry.findtext(f"{{{ATOM}}}title") or "").strip()
        video_id = (entry.findtext(f"{{{YOUTUBE}}}videoId") or "").strip()
        published_text = (entry.findtext(f"{{{ATOM}}}published") or "").strip()
        link_element = entry.find(f"{{{ATOM}}}link[@rel='alternate']")
        url = (link_element.get("href") if link_element is not None else "") or ""
        if not title or not video_id or not published_text or not url.startswith("https://www.youtube.com/"):
            continue
        published = _published_at(published_text)
        age_hours = (now - published).total_seconds() / 3600
        if age_hours < 0 or age_hours > max_age_hours:
            continue
        items.append(
            {
                "status": "ok",
                "quality_status": "verified",
                "channel": channel_label,
                "title": title,
                "video_id": video_id,
                "url": url,
                "published": published.strftime("%Y-%m-%d %H:%M JST"),
                "age_hours": round(age_hours, 1),
                "source": "YouTube 公開Atomフィード",
            }
        )
    items.sort(key=lambda item: item["published"], reverse=True)
    return items


def fetch_youtube_snapshot(sources: dict[str, Any]) -> dict[str, Any]:
    config = sources.get("youtube", {}) or {}
    if not config.get("enabled", False):
        return {"status": "disabled", "items": [], "note": "YouTube新着確認は無効です"}

    timeout = float(config.get("timeout_seconds", 15))
    max_age_hours = float(config.get("max_age_hours", 72))
    max_items = int(config.get("max_items", 3))
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for channel in config.get("channels", []):
        channel_id = str(channel.get("channel_id", "")).strip()
        label = str(channel.get("label", channel_id)).strip()
        if not CHANNEL_ID_PATTERN.fullmatch(channel_id):
            errors.append(f"{label}: チャンネルID未確認")
            continue
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            response = requests.get(
                feed_url,
                timeout=timeout,
                headers={"User-Agent": "market-telegram-notifier/1.0"},
            )
            response.raise_for_status()
            items.extend(parse_youtube_feed(response.text, label, max_age_hours=max_age_hours))
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    items.sort(key=lambda item: item["published"], reverse=True)
    items = items[:max_items]
    if items:
        status = "ok"
        note = "公開フィードのタイトル・公開日時・動画URLだけを取得しました。動画内の予想は事実認定しません。"
    elif errors:
        status = "unavailable"
        note = "未確認: " + " / ".join(errors[:3])
    else:
        status = "no_recent_items"
        note = f"直近{max_age_hours:.0f}時間の新着動画は確認されませんでした。"
    return {
        "status": status,
        "items": items,
        "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "source": "YouTube 公開Atomフィード",
        "note": note,
    }
